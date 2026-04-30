"""
小米智能宠物喂食器 2 业务模块
设备型号: mmgg.feeder.petfeeder / xiaomi.feeder.pi2001
MIoT URN: urn:miot-spec-v2:device:pet-feeder:0000A06C
"""
import datetime
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from app.cloud import MiCloudClient


def parse_schedule(raw: list | str | None) -> dict:
    """解析喂食计划
    格式: "[enabled, HHMMSSPP, HHMMSSPP, ...]"
    返回: {enabled, meals: [{time, portions}, ...], total_portions}
    """
    if not raw:
        return {"enabled": False, "meals": [], "total_portions": 0}

    # 设备返回的是字符串，需要解析
    if isinstance(raw, str):
        import re
        nums = [int(x) for x in re.findall(r'\d+', raw)]
    elif isinstance(raw, list):
        nums = [int(x) for x in raw]
    else:
        return {"enabled": False, "meals": [], "total_portions": 0}

    if len(nums) < 2:
        return {"enabled": False, "meals": [], "total_portions": 0}

    enabled = bool(nums[0])
    meals = []
    for entry in nums[1:]:
        try:
            s = str(entry).zfill(8)
            hour = int(s[0:2])
            minute = int(s[2:4])
            portions = int(s[4:6])
            if portions == 0 and hour == 0 and minute == 0:
                continue
            meals.append({
                "time": f"{hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "portions": portions,
            })
        except (ValueError, IndexError):
            continue
    return {
        "enabled": enabled,
        "meals": meals,
        "total_portions": sum(m["portions"] for m in meals),
    }


def encode_schedule(meals: list[dict], enabled: bool = True) -> str:
    """编码喂食计划为设备格式
    meals: [{"hour": 8, "minute": 0, "portions": 3}, ...]
    返回: "[1,08000300,12000400,18000300]"
    """
    entries = [1 if enabled else 0]
    for m in meals:
        hh = str(m.get("hour", 0)).zfill(2)
        mm = str(m.get("minute", 0)).zfill(2)
        pp = str(m.get("portions", 1)).zfill(2)
        entries.append(int(f"{hh}{mm}00{pp}"))
    return str(entries).replace(" ", "")


# ---- 枚举定义 ----

class FaultCode(IntEnum):
    NORMAL = 0
    LACK = 1        # 缺粮
    EXHAUSTION = 2  # 耗尽
    BLOCKING = 3    # 堵粮

    @classmethod
    def label(cls, code: int) -> str:
        return {
            0: "正常",
            1: "缺粮",
            2: "粮食耗尽",
            3: "出粮口堵塞",
        }.get(code, f"未知({code})")


class PowerStatus(IntEnum):
    DC = 0        # 电源供电
    BATTERY = 1   # 电池供电


# ---- 数据模型 ----

@dataclass
class FeederState:
    """喂食器完整状态"""
    did: str = ""
    name: str = ""
    model: str = ""

    # SIID 2: 核心喂食服务
    fault: int | None = None           # piid 1: 故障码
    fault_label: str = "未知"
    feeding_measure: int | None = None  # piid 5: 当前出粮份数/状态
    power: int | None = None            # piid 6: 0=电源, 1=电池
    power_label: str = "未知"

    # SIID 3: 扩展功能
    feed_result: int | None = None      # piid 2: 上一次出粮结果
    schedule_raw: str | None = None     # piid 3: 定时喂食计划
    feeder_enable: int | None = None    # piid 4: 按键使能 + 份数
    beep: bool | None = None           # piid 5: 提示音开关
    physical_locked: bool | None = None # piid 1: 物理按键锁定

    # SIID 2: 进食数据（设备自动记录）
    eaten_food: int | None = None       # piid 22: 今日已吃份数

    # SIID 5: 自定义服务
    feeding_plan: dict | None = None    # piid 1: 定时喂食计划（解析后）
    food_intake_rate: int | None = None # piid 5: 进食率 (10-90)
    schedule_state: int | None = None   # piid 8: 计划状态
    add_meal_state: bool | None = None  # piid 3: 加餐状态
    food_remaining: int | None = None   # piid 15: 余粮百分比

    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "did": self.did,
            "name": self.name,
            "model": self.model,
            "fault": self.fault,
            "fault_label": self.fault_label,
            "feeding_measure": self.feeding_measure,
            "power": self.power,
            "power_label": self.power_label,
            "feed_result": self.feed_result,
            "schedule": self.schedule_raw,
            "feeder_enable": self.feeder_enable,
            "beep": self.beep,
            "physical_locked": self.physical_locked,
            "eaten_food": self.eaten_food,
            "feeding_plan": self.feeding_plan,
            "food_intake_rate": self.food_intake_rate,
            "schedule_state": self.schedule_state,
            "add_meal_state": self.add_meal_state,
            "food_remaining": self.food_remaining,
            "last_error": self.last_error,
        }


# ---- MIoT 常量 ----

class FeederSpec:
    """喂食器 MIoT 规范常量"""
    # 服务 2: pet-feeder (核心喂食)
    SIID_FEEDER = 2
    PIID_FAULT = 1
    PIID_FEEDING_MEASURE = 5
    PIID_STATUS = 6
    AIID_PET_FOOD_OUT = 1

    # 服务 3: feeder-function (扩展功能)
    SIID_FUNCTION = 3
    PIID_FEED_RESULT = 2
    PIID_SCHEDULE = 3
    PIID_FEEDING_ENABLE = 4
    PIID_BEEP = 5

    # 服务 5: custom
    SIID_CUSTOM = 5
    PIID_FEEDING_PLAN = 1

    # 所有可读属性
    READABLE_PROPS: list[tuple[int, int]] = [
        (2, 1),   # fault
        (2, 5),   # feeding-measure
        (2, 6),   # status (power)
        (2, 22),  # eaten-food (今日已吃克数)
        (3, 1),   # physical-controls-locked
        (3, 2),   # feed-result
        (3, 3),   # schedule
        (3, 4),   # feeding-enable
        (3, 5),   # beep
        (5, 1),   # feeding-plan (定时计划)
        (5, 3),   # add-meal-state
        (5, 5),   # food-intake-rate
        (5, 8),   # schedule-state
        (5, 15),  # food-remaining
    ]


# ---- 业务逻辑 ----

class FeederController:
    """喂食器控制器"""

    def __init__(self, cloud: MiCloudClient, did: str):
        self.cloud = cloud
        self.did = did
        self._device_info: dict | None = None

    async def init(self) -> bool:
        """初始化：查找设备信息"""
        dev = await self.cloud.find_device(did=self.did)
        if dev is None:
            return False
        self._device_info = dev
        return True

    @property
    def name(self) -> str:
        return (self._device_info or {}).get("name", "")

    @property
    def model(self) -> str:
        return (self._device_info or {}).get("model", "")

    async def get_state(self) -> FeederState:
        """获取喂食器完整状态"""
        state = FeederState(
            did=self.did,
            name=self.name,
            model=self.model,
        )

        raw = await self.cloud.get_props(self.did, FeederSpec.READABLE_PROPS)

        # 解析各属性
        state.fault = raw.get("2-1")
        state.fault_label = FaultCode.label(state.fault) if state.fault is not None else "未知"

        state.feeding_measure = raw.get("2-5")

        state.power = raw.get("2-6")
        state.power_label = {0: "电源供电", 1: "电池供电"}.get(
            state.power, "未知"
        )

        state.feed_result = raw.get("3-2")
        state.schedule_raw = raw.get("3-3")
        state.feeder_enable = raw.get("3-4")
        state.beep = bool(raw.get("3-5")) if raw.get("3-5") is not None else None
        state.physical_locked = bool(raw.get("3-1")) if raw.get("3-1") is not None else None

        state.eaten_food = raw.get("2-22")
        state.feeding_plan = parse_schedule(raw.get("5-1"))
        state.food_intake_rate = raw.get("5-5")
        state.schedule_state = raw.get("5-8")
        state.add_meal_state = bool(raw.get("5-3")) if raw.get("5-3") is not None else None
        state.food_remaining = raw.get("5-15")

        return state

    async def feed(self, portions: int = 1) -> bool:
        """手动出粮"""
        portions = min(max(portions, 1), 112)
        return await self.cloud.do_action(
            self.did,
            siid=FeederSpec.SIID_FEEDER,
            aiid=FeederSpec.AIID_PET_FOOD_OUT,
            params=[portions],
        )

    async def set_beep(self, on: bool) -> bool:
        """设置出粮提示音开关"""
        return await self.cloud.set_prop(
            self.did,
            siid=FeederSpec.SIID_FUNCTION,
            piid=FeederSpec.PIID_BEEP,
            value=int(on),
        )

    async def set_feeder_enable(self, enabled: bool, portions: int = 10) -> bool:
        """设置按键出粮使能与份数
        百位=1 表示按键出粮使能，个位+十位=出粮份数(1-99)
        """
        value = (100 if enabled else 0) + min(max(portions, 1), 99)
        return await self.cloud.set_prop(
            self.did,
            siid=FeederSpec.SIID_FUNCTION,
            piid=FeederSpec.PIID_FEEDING_ENABLE,
            value=value,
        )

    async def set_schedule(self, meals: list[dict], enabled: bool = True) -> bool:
        """写入喂食计划到设备
        meals: [{"hour": 8, "minute": 0, "portions": 3}, ...]
        """
        encoded = encode_schedule(meals, enabled)
        # 写入 SIID=5 PIID=1 (feeding-plan)，设备同时同步到 SIID=3 PIID=3
        return await self.cloud.set_prop(
            self.did,
            siid=FeederSpec.SIID_CUSTOM,
            piid=FeederSpec.PIID_FEEDING_PLAN,
            value=encoded,
        )
