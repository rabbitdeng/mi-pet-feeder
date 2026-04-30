"""
猫粮品牌数据库
"""
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CatFood:
    id: str
    brand: str          # 品牌
    name: str           # 产品名
    type: str           # dry/wet/freeze/air_dried
    type_label: str     # 干粮/湿粮/冻干/风干
    kcal_per_g: float   # 热量密度 (kcal/g)
    protein_pct: float  # 蛋白质 %
    fat_pct: float      # 脂肪 %
    stage: str          # 适用阶段: kitten/adult/senior/all
    stage_label: str    # 幼猫/成猫/老年猫/全阶段

    def to_dict(self) -> dict:
        return asdict(self)


# ---- 主流猫粮数据库 ----

FOODS: list[CatFood] = [
    # ===== 干粮 =====
    # 皇家 Royal Canin
    CatFood("rc_k36",  "皇家", "K36 幼猫粮", "dry", "干粮", 4.10, 36, 18, "kitten", "幼猫"),
    CatFood("rc_f32",  "皇家", "F32 理想体态成猫粮", "dry", "干粮", 3.90, 32, 15, "adult", "成猫"),
    CatFood("rc_hair", "皇家", "去毛球成猫粮", "dry", "干粮", 3.85, 34, 15, "adult", "成猫"),
    CatFood("rc_sen12","皇家", "S12 老年猫粮", "dry", "干粮", 3.75, 28, 12, "senior", "老年猫"),
    CatFood("rc_fbn",  "皇家", "英短成猫粮", "dry", "干粮", 3.95, 34, 16, "adult", "成猫"),
    CatFood("rc_light","皇家", "Light 体重控制成猫粮", "dry", "干粮", 3.45, 36, 10, "adult", "成猫"),

    # 冠能 Pro Plan
    CatFood("pp_kitten","冠能", "幼猫全价粮", "dry", "干粮", 4.15, 42, 18, "kitten", "幼猫"),
    CatFood("pp_adult", "冠能", "成猫全价粮", "dry", "干粮", 4.00, 36, 16, "adult", "成猫"),
    CatFood("pp_ster",  "冠能", "绝育成猫粮", "dry", "干粮", 3.70, 38, 12, "adult", "成猫"),
    CatFood("pp_urine", "冠能", "泌尿道健康成猫粮", "dry", "干粮", 3.85, 34, 14, "adult", "成猫"),

    # 渴望 Orijen
    CatFood("or_cat",   "渴望", "Original 六种鱼", "dry", "干粮", 4.16, 40, 20, "all", "全阶段"),
    CatFood("or_fit",   "渴望", "Fit & Trim 体重控制", "dry", "干粮", 3.71, 42, 15, "adult", "成猫"),
    CatFood("or_kitten","渴望", "Kitten 幼猫粮", "dry", "干粮", 4.25, 40, 20, "kitten", "幼猫"),

    # 爱肯拿 Acana
    CatFood("ac_grass", "爱肯拿", "牧场盛宴", "dry", "干粮", 4.08, 37, 20, "all", "全阶段"),
    CatFood("ac_sea",   "爱肯拿", "海洋盛宴", "dry", "干粮", 4.03, 37, 20, "all", "全阶段"),
    CatFood("ac_indoor","爱肯拿", "室内猫粮", "dry", "干粮", 3.76, 37, 16, "adult", "成猫"),

    # 纽顿 Nutram
    CatFood("nt_t22",   "纽顿", "T22 鸡肉火鸡", "dry", "干粮", 3.82, 36, 17, "all", "全阶段"),
    CatFood("nt_t24",   "纽顿", "T24 三文鱼", "dry", "干粮", 3.78, 36, 17, "all", "全阶段"),

    # 网易严选
    CatFood("wy_kitten","网易严选", "幼猫粮", "dry", "干粮", 4.05, 38, 18, "kitten", "幼猫"),
    CatFood("wy_adult", "网易严选", "全价成猫粮", "dry", "干粮", 3.95, 36, 16, "adult", "成猫"),
    CatFood("wy_hair",  "网易严选", "冻干双拼猫粮", "dry", "干粮", 4.10, 40, 18, "all", "全阶段"),

    # 麦富迪
    CatFood("mf_kitten","麦富迪", "鲜肉幼猫粮", "dry", "干粮", 4.00, 36, 16, "kitten", "幼猫"),
    CatFood("mf_adult", "麦富迪", "三文鱼成猫粮", "dry", "干粮", 3.85, 32, 14, "adult", "成猫"),
    CatFood("mf_std",   "麦富迪", "全价猫粮", "dry", "干粮", 3.80, 30, 13, "all", "全阶段"),

    # 伯纳天纯
    CatFood("bn_kitten","伯纳天纯", "幼猫粮", "dry", "干粮", 4.05, 38, 18, "kitten", "幼猫"),
    CatFood("bn_adult", "伯纳天纯", "全价成猫粮", "dry", "干粮", 3.90, 34, 16, "adult", "成猫"),

    # 卫仕
    CatFood("ws_adult", "卫仕", "全价猫粮", "dry", "干粮", 3.85, 34, 15, "adult", "成猫"),
    CatFood("ws_kitten","卫仕", "幼猫粮", "dry", "干粮", 4.05, 38, 18, "kitten", "幼猫"),

    # 素力高 Solid Gold
    CatFood("sg_indigo","素力高", "金素 鸡肉", "dry", "干粮", 3.90, 42, 20, "all", "全阶段"),
    CatFood("sg_kitten","素力高", "幼猫粮", "dry", "干粮", 4.05, 40, 20, "kitten", "幼猫"),

    # 比瑞吉
    CatFood("br_std",   "比瑞吉", "全价猫粮", "dry", "干粮", 3.80, 28, 12, "adult", "成猫"),
    CatFood("br_kitten","比瑞吉", "奶糕幼猫粮", "dry", "干粮", 4.00, 32, 16, "kitten", "幼猫"),

    # 领先
    CatFood("lx_adult", "领先", "全价猫粮", "dry", "干粮", 3.90, 36, 16, "adult", "成猫"),

    # ===== 湿粮/罐头 =====
    CatFood("rc_w_k36", "皇家", "K36 幼猫湿粮", "wet", "湿粮", 0.95, 11, 5.5, "kitten", "幼猫"),
    CatFood("rc_w_ad",  "皇家", "成猫湿粮", "wet", "湿粮", 0.90, 10, 4.5, "adult", "成猫"),
    CatFood("pp_w",     "冠能", "成猫主食罐", "wet", "湿粮", 0.95, 12, 5, "adult", "成猫"),
    CatFood("or_w",     "渴望", "Original 主食罐", "wet", "湿粮", 1.05, 12, 6, "all", "全阶段"),
    CatFood("ac_w",     "爱肯拿", "主食罐", "wet", "湿粮", 1.00, 11, 5.5, "all", "全阶段"),
    CatFood("wy_w",     "网易严选", "主食罐", "wet", "湿粮", 0.92, 11, 4.5, "adult", "成猫"),
    CatFood("mf_w",     "麦富迪", "主食罐", "wet", "湿粮", 0.90, 10, 4, "adult", "成猫"),

    # ===== 冻干 =====
    CatFood("or_fd",    "渴望", "冻干猫粮", "freeze", "冻干", 4.50, 45, 25, "all", "全阶段"),
    CatFood("ac_fd",    "爱肯拿", "冻干猫粮", "freeze", "冻干", 4.60, 42, 24, "all", "全阶段"),
    CatFood("wy_fd",    "网易严选", "全价冻干", "freeze", "冻干", 4.40, 50, 22, "all", "全阶段"),
    CatFood("pp_fd",    "冠能", "冻干生骨肉", "freeze", "冻干", 4.55, 48, 24, "all", "全阶段"),

    # ===== 风干粮 =====
    CatFood("or_ad",    "渴望", "风干猫粮", "air_dried", "风干", 4.20, 38, 22, "all", "全阶段"),
]


def get_brands() -> list[str]:
    """返回去重排序的品牌列表"""
    return sorted(set(f.brand for f in FOODS))


def get_by_brand(brand: str) -> list[dict]:
    """按品牌获取产品列表"""
    return [f.to_dict() for f in FOODS if f.brand == brand]


def get_by_id(food_id: str) -> dict | None:
    """根据 ID 获取产品"""
    for f in FOODS:
        if f.id == food_id:
            return f.to_dict()
    return None


def search(query: str) -> list[dict]:
    """搜索猫粮（品牌/产品名模糊匹配）"""
    q = query.lower()
    return [f.to_dict() for f in FOODS
            if q in f.brand.lower() or q in f.name.lower()]


def get_kcal(food_id: str) -> float | None:
    """获取指定猫粮的热量密度"""
    food = get_by_id(food_id)
    return food["kcal_per_g"] if food else None
