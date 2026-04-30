"""
猫咪档案
"""
import json
import os
from dataclasses import dataclass, asdict

from app.food_db import get_kcal


DEFAULT_KCAL = 3.7  # 默认干粮热量


@dataclass
class CatProfile:
    breed: str = ""         # 品种
    age: str = ""           # 年龄
    weight: str = ""        # 体重
    food_id: str = ""       # 猫粮产品 ID (对应 food_db 中的产品)
    food_label: str = ""    # 猫粮显示名 (缓存，避免每次查库)

    def to_dict(self) -> dict:
        return asdict(self)

    def get_kcal_per_gram(self) -> float:
        """从数据库获取所选猫粮的热量密度，未选择时返回默认值"""
        if self.food_id:
            kcal = get_kcal(self.food_id)
            if kcal is not None:
                return kcal
        return DEFAULT_KCAL

    @classmethod
    def from_dict(cls, d: dict) -> "CatProfile":
        return cls(
            breed=str(d.get("breed", "")),
            age=str(d.get("age", "")),
            weight=str(d.get("weight", "")),
            food_id=str(d.get("food_id", "")),
            food_label=str(d.get("food_label", "")),
        )


class CatProfileStore:
    """猫咪档案持久化"""

    def __init__(self, filepath: str = "cat_profile.json"):
        self._filepath = filepath
        self.profile = CatProfile()
        self._load()

    def get(self) -> dict:
        return self.profile.to_dict()

    def update(self, breed: str = "", age: str = "", weight: str = "",
               food_id: str = "", food_label: str = "") -> dict:
        self.profile.breed = breed
        self.profile.age = age
        self.profile.weight = weight
        self.profile.food_id = food_id
        self.profile.food_label = food_label
        self._save()
        return self.profile.to_dict()

    def _save(self):
        try:
            with open(self._filepath, "w") as f:
                json.dump(self.profile.to_dict(), f, ensure_ascii=False)
        except Exception:
            pass

    def _load(self):
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath) as f:
                data = json.load(f)
            self.profile = CatProfile.from_dict(data)
        except Exception:
            self.profile = CatProfile()
