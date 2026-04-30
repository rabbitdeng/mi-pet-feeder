"""
自动生成喂食计划
根据每日营养建议，计算总份数并按餐次分配
"""
import math


def generate_plan(
    daily_grams: float,
    grams_per_portion: float = 10.0,
    num_meals: int = 3,
) -> dict:
    """
    根据每日建议喂食克数自动生成喂食计划

    Args:
        daily_grams: 每日建议喂食克数
        grams_per_portion: 每份出粮克数
        num_meals: 每天喂食餐数 (1-4)

    Returns:
        {meals, total_portions, estimated_daily_grams, ...}
    """
    if daily_grams <= 0:
        return {"error": "无法计算：请先完善猫咪档案"}

    if num_meals < 1 or num_meals > 4:
        num_meals = 3

    grams_per_portion = max(1.0, min(grams_per_portion, 50.0))

    total_portions = max(1, round(daily_grams / grams_per_portion))
    base = total_portions // num_meals
    remainder = total_portions % num_meals

    # 默认时间槽
    slots = {
        1: [(8, 0)],
        2: [(8, 0), (20, 0)],
        3: [(8, 0), (12, 0), (18, 0)],
        4: [(8, 0), (12, 0), (16, 0), (20, 0)],
    }[num_meals]

    meals = []
    for i, (hour, minute) in enumerate(slots):
        portions = base + (1 if i < remainder else 0)
        meals.append({"hour": hour, "minute": minute, "portions": portions})

    estimated_grams = total_portions * grams_per_portion

    return {
        "meals": meals,
        "total_portions": total_portions,
        "daily_grams_target": round(daily_grams),
        "grams_per_portion": grams_per_portion,
        "estimated_daily_grams": round(estimated_grams),
        "num_meals": num_meals,
    }
