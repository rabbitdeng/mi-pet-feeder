"""
FastAPI 入口 — 米家智能宠物喂食器 Web 控制台
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.cloud import MiCloudClient
from app.feeder import FeederController, parse_schedule, encode_schedule
from app.sensor import SensorController
from app.feed_history import FeedHistory
from app.cat_profile import CatProfileStore
from app.nutrition import calculate_from_profile
from app.food_db import get_brands, get_by_brand, get_by_id as get_food_by_id
from app.feed_calculator import generate_plan

load_dotenv()

# ---- 全局状态 ----
cloud: MiCloudClient | None = None
feeder: FeederController | None = None
sensor: SensorController | None = None
history: FeedHistory = FeedHistory()
cat_profile: CatProfileStore = CatProfileStore()
init_error: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cloud, feeder, sensor, init_error
    username = os.getenv("MI_USER", "")
    password = os.getenv("MI_PASS", "")
    user_id = os.getenv("MI_USER_ID", "")
    pass_token = os.getenv("MI_PASS_TOKEN", "")
    feeder_did = os.getenv("FEEDER_DID", "")
    sensor_did = os.getenv("SENSOR_DID", "")

    if not feeder_did:
        init_error = "未配置喂食器 DID。获取设备 DID 后填入 .env 的 FEEDER_DID"
    elif not ((username and password) or (user_id and pass_token)):
        init_error = "请配置 .env：\n  方式1（推荐）: MI_USER_ID + MI_PASS_TOKEN\n  方式2: MI_USER + MI_PASS"
    else:
        try:
            cloud = MiCloudClient(
                username=username,
                password=password,
                user_id=user_id,
                pass_token=pass_token,
            )
            await cloud.login()
            feeder = FeederController(cloud, feeder_did)
            ok = await feeder.init()
            if not ok:
                init_error = f"未找到设备 DID={feeder_did}，请检查 .env 中的 FEEDER_DID"
                await cloud.close()
                cloud = None
                feeder = None
            elif sensor_did:
                sensor = SensorController(cloud, sensor_did)
                s_ok = await sensor.init()
                if not s_ok:
                    print(f"警告: 未找到温湿度计 DID={sensor_did}")
        except Exception as e:
            init_error = f"登录失败: {e}"
            cloud = None
            feeder = None

    yield

    if cloud:
        await cloud.close()


app = FastAPI(
    title="米家喂食器控制台",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ---- 页面 ----

@app.get("/")
async def dashboard(request: Request):
    """仪表盘首页"""
    return templates.TemplateResponse(request, "dashboard.html", {"error": init_error})


# ---- API ----

@app.get("/api/status")
async def get_status():
    """获取喂食器当前状态"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    try:
        state = await feeder.get_state()
        return {"ok": True, "data": state.to_dict()}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/dashboard")
async def get_dashboard():
    """获取仪表盘聚合数据"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    try:
        # 喂食器状态
        feeder_state = (await feeder.get_state()).to_dict()

        # 温湿度
        temperature = None
        humidity = None
        battery = None
        if sensor:
            try:
                s_state = await sensor.get_state()
                temperature = s_state.temperature
                humidity = s_state.humidity
                battery = s_state.battery
            except Exception:
                pass

        # 营养计算
        nutrition = calculate_from_profile(cat_profile.get())
        goal_grams = nutrition["daily_grams"] if nutrition else None

        # 记录设备进食数据（每天保存最大值）
        history.record_device_eaten(feeder_state.get("eaten_food"))

        # 饱食度 — 传入设备实际进食数据 + 动态目标
        fullness = history.get_fullness(
            device_eaten=feeder_state.get("eaten_food"),
            goal_grams=goal_grams,
        )

        return {
            "ok": True,
            "temperature": temperature,
            "humidity": humidity,
            "sensor_battery": battery,
            "feeder": feeder_state,
            "fullness": fullness,
            "cat": cat_profile.get(),
            "nutrition": nutrition,
            "grams_per_portion": cat_profile.get().get("portion_grams", 10.0),
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/feed")
async def trigger_feed(portions: int = 1):
    """手动出粮"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    portions = min(max(portions, 1), 112)
    ok = await feeder.feed(portions)
    if ok:
        history.record(portions)
    return {"ok": ok, "message": f"出粮 {portions} 份" if ok else "出粮失败"}


@app.post("/api/beep")
async def toggle_beep(on: bool = True):
    """开关提示音"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    ok = await feeder.set_beep(on)
    return {"ok": ok, "message": "提示音已开启" if on else "提示音已关闭"}


@app.post("/api/plan")
async def update_plan(request: Request):
    """更新喂食计划"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "请求格式错误"}, status_code=400)

    meals = body.get("meals", [])
    enabled = bool(body.get("enabled", True))

    # 校验
    if not isinstance(meals, list) or len(meals) > 8:
        return JSONResponse({"ok": False, "error": "计划最多支持 8 个喂食时间"}, status_code=400)
    if enabled and len(meals) == 0:
        return JSONResponse({"ok": False, "error": "启用计划至少需要一个喂食时间"}, status_code=400)

    seen = set()
    valid_meals = []
    for m in meals:
        hour = int(m.get("hour", 0))
        minute = int(m.get("minute", 0))
        portions = int(m.get("portions", 1))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return JSONResponse({"ok": False, "error": "时间格式错误"}, status_code=400)
        if portions < 1 or portions > 99:
            return JSONResponse({"ok": False, "error": "单次出粮份数需为 1-99"}, status_code=400)
        key = f"{hour:02d}:{minute:02d}"
        if key in seen:
            return JSONResponse({"ok": False, "error": "存在重复的喂食时间"}, status_code=400)
        seen.add(key)
        valid_meals.append({"hour": hour, "minute": minute, "portions": portions})

    try:
        ok = await feeder.set_schedule(valid_meals, enabled)
        if not ok:
            return JSONResponse({"ok": False, "error": "写入设备失败"}, status_code=500)

        # 重读确认
        state = await feeder.get_state()
        feeding_plan = state.to_dict().get("feeding_plan", {})
        return {"ok": True, "data": feeding_plan, "message": "喂食计划已更新"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/plan/generate")
async def generate_feeding_plan(request: Request):
    """根据营养建议自动生成喂食计划"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    # 获取营养数据
    nutrition = calculate_from_profile(cat_profile.get())
    if nutrition is None or nutrition.get("daily_grams", 0) <= 0:
        return JSONResponse({"ok": False, "error": "请先完善猫咪档案（至少需要体重）"}, status_code=400)

    num_meals = int(body.get("num_meals", 3))
    grams_per_portion = float(body.get("grams_per_portion", 0) or cat_profile.get().get("portion_grams", 10.0))

    result = generate_plan(
        daily_grams=nutrition["daily_grams"],
        grams_per_portion=grams_per_portion,
        num_meals=num_meals,
    )

    if "error" in result:
        return JSONResponse({"ok": False, "error": result["error"]}, status_code=400)

    result["kcal_per_gram"] = nutrition.get("kcal_per_gram")
    return {"ok": True, "data": result}


@app.get("/api/cat")
async def get_cat():
    """获取猫咪档案"""
    return {"ok": True, "data": cat_profile.get()}


@app.post("/api/cat")
async def update_cat(request: Request):
    """更新猫咪档案"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "请求格式错误"}, status_code=400)
    data = cat_profile.update(
        breed=str(body.get("breed", "")).strip(),
        age=str(body.get("age", "")).strip(),
        weight=str(body.get("weight", "")).strip(),
        food_id=str(body.get("food_id", "")).strip(),
        food_label=str(body.get("food_label", "")).strip(),
        portion_grams=float(body["portion_grams"]) if "portion_grams" in body else None,
    )
    return {"ok": True, "data": data}


@app.get("/api/nutrition")
async def get_nutrition():
    """获取猫咪营养计算结果"""
    profile = cat_profile.get()
    result = calculate_from_profile(profile)
    if result is None:
        return JSONResponse(
            {"ok": False, "error": "请先完善猫咪档案（体重为必填）"},
            status_code=400,
        )
    return {"ok": True, "data": result}


@app.get("/api/foods/brands")
async def list_brands():
    """获取所有猫粮品牌"""
    return {"ok": True, "data": get_brands()}


@app.get("/api/history")
async def get_history(days: int = 7):
    """获取近 N 天的喂食历史汇总"""
    if feeder is None:
        return JSONResponse({"ok": False, "error": init_error or "系统未初始化"}, status_code=503)
    try:
        days = min(max(days, 1), 30)
        daily = history.get_daily_summary(days)

        profile = cat_profile.get()
        portion_grams = profile.get("portion_grams", 10.0)

        nutrition = calculate_from_profile(profile)
        goal_grams = nutrition["daily_grams"] if nutrition else None
        goal_portions = max(1, round(goal_grams / portion_grams)) if goal_grams and portion_grams else None

        return {
            "ok": True,
            "data": {
                "days": daily,
                "goal_grams": goal_grams,
                "goal_portions": goal_portions,
                "grams_per_portion": portion_grams,
            },
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/foods")
async def list_foods(brand: str = ""):
    """获取猫粮产品列表，可按品牌筛选"""
    if brand:
        return {"ok": True, "data": get_by_brand(brand)}
    # 返回全部数据，按品牌分组
    brands = {}
    for b in get_brands():
        brands[b] = get_by_brand(b)
    return {"ok": True, "data": brands}


@app.get("/api/food")
async def get_food(food_id: str = ""):
    """获取单个猫粮产品详情"""
    food = get_food_by_id(food_id)
    if not food:
        return JSONResponse({"ok": False, "error": "未找到该产品"}, status_code=404)
    return {"ok": True, "data": food}


# ---- 健康检查 ----

@app.get("/api/health")
async def health():
    return {
        "ok": feeder is not None,
        "error": init_error or None,
    }
