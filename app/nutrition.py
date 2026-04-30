"""
猫咪营养计算器
基于体重、年龄、猫粮种类计算每日热量和喂食量
"""
import re
import math

from app.cat_profile import DEFAULT_KCAL
from app.food_db import get_kcal as get_food_kcal


def parse_age_years(age_str: str) -> float | None:
    """解析年龄字符串为年份数，如 "2岁"→2.0, "8个月"→0.67, "1岁6个月"→1.5"""
    if not age_str or not age_str.strip():
        return None
    s = age_str.strip()
    years = 0.0
    year_match = re.search(r'(\d+)\s*岁', s)
    if year_match:
        years += float(year_match.group(1))
    month_match = re.search(r'(\d+)\s*个?\s*月', s)
    if month_match:
        years += float(month_match.group(1)) / 12.0
    if not year_match and not month_match:
        try:
            years = float(s)
        except ValueError:
            return None
    return years if years > 0 else None


def parse_weight_kg(weight_str: str) -> float | None:
    """解析体重字符串为公斤数，如 "4.5kg"→4.5, "4500g"→4.5, "4.5"→4.5"""
    if not weight_str or not weight_str.strip():
        return None
    s = weight_str.strip().lower()
    num_str = re.sub(r'\s*(kg|g)\s*$', '', s)
    try:
        val = float(num_str)
    except ValueError:
        return None
    if s.endswith('g') and not s.endswith('kg'):
        val = val / 1000.0
    return val if val > 0 else None


def get_life_stage_factor(age_years: float) -> tuple[float, str]:
    """根据年龄返回热量系数和生命阶段"""
    if age_years < 0.33:
        return 2.5, "幼猫(0-4月)"
    elif age_years < 1.0:
        return 2.0, "幼猫(4-12月)"
    elif age_years < 2.0:
        return 1.4, "青年猫"
    elif age_years < 8.0:
        return 1.2, "成年猫"
    else:
        return 1.1, "老年猫"


def calculate(weight_kg: float, age_years: float | None = None,
              kcal_per_gram: float | None = None) -> dict:
    """
    计算猫咪每日营养需求
    - weight_kg: 体重(公斤)
    - age_years: 年龄(年)，可选
    - kcal_per_gram: 猫粮热量密度(kcal/g)，None=使用默认值
    """
    if kcal_per_gram is None or kcal_per_gram <= 0:
        kcal_per_gram = DEFAULT_KCAL

    rer = 70 * (weight_kg ** 0.75)

    if age_years is not None:
        factor, stage = get_life_stage_factor(age_years)
    else:
        factor, stage = 1.2, "成年猫（默认）"

    der = rer * factor
    daily_grams = der / kcal_per_gram

    return {
        "weight_kg": round(weight_kg, 2),
        "age_years": round(age_years, 2) if age_years is not None else None,
        "life_stage": stage,
        "life_stage_factor": factor,
        "rer_kcal": round(rer),
        "der_kcal": round(der),
        "daily_grams": round(daily_grams),
        "kcal_per_gram": kcal_per_gram,
    }


def calculate_from_profile(profile: dict) -> dict | None:
    """从猫咪档案计算营养需求（自动读取猫粮产品热量）"""
    weight = parse_weight_kg(profile.get("weight", ""))
    if weight is None:
        return None
    age = parse_age_years(profile.get("age", ""))

    # 读取所选猫粮的热量密度
    food_id = profile.get("food_id", "")
    kcal = get_food_kcal(food_id) if food_id else None

    return calculate(weight, age, kcal_per_gram=kcal)
