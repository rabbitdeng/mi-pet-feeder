"""
喂食历史追踪
"""
import datetime
import json
import os
import time
from dataclasses import dataclass


@dataclass
class FeedEvent:
    timestamp: float  # time.time()
    portions: int

    def to_dict(self) -> dict:
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return {
            "time": dt.strftime("%H:%M"),
            "portions": self.portions,
            "timestamp": self.timestamp,
        }


class FeedHistory:
    """喂食历史"""

    GOAL_PORTIONS = 10     # 每日目标份数（手动出粮用）
    GOAL_GRAMS = 50        # 每日目标克数（设备进食数据用）

    def __init__(self, filepath: str = "feed_history.json"):
        self._filepath = filepath
        self._events: list[FeedEvent] = []
        self._daily_device: dict[str, int] = {}  # { "YYYY-MM-DD": grams }
        self._load()

    def record(self, portions: int):
        """记录一次喂食"""
        self._events.append(FeedEvent(
            timestamp=time.time(),
            portions=portions,
        ))
        self._save()

    def record_device_eaten(self, grams: int | None):
        """记录今日设备进食克数（取最大值）"""
        if grams is None or grams <= 0:
            return
        today = datetime.date.today().isoformat()
        current = self._daily_device.get(today, 0)
        if grams > current:
            self._daily_device[today] = grams
            self._save()

    @property
    def events(self) -> list[FeedEvent]:
        return self._events

    def _today_events(self) -> list[FeedEvent]:
        """返回今日的喂食记录"""
        today = datetime.date.today()
        today_start = datetime.datetime(
            today.year, today.month, today.day
        ).timestamp()
        return [e for e in self._events if e.timestamp >= today_start]

    def get_today_total(self) -> int:
        """今日累计喂食份数"""
        return sum(e.portions for e in self._today_events())

    def get_today_list(self) -> list[dict]:
        """今日喂食记录列表"""
        return [e.to_dict() for e in reversed(self._today_events())]

    def get_last_feed_minutes(self) -> float | None:
        """距上次喂食的分钟数，无记录返回 None"""
        if not self._events:
            return None
        return (time.time() - self._events[-1].timestamp) / 60.0

    def get_fullness(self, device_eaten: int | None = None, goal_grams: int | None = None) -> dict:
        """
        饱食度数据：
        - time_based: 基于时间衰减 (上次喂食后 0→4h 线性从 100→0)
        - today_goal: 今日目标完成百分比
        - today_amount: 今日进食量
        - goal_amount: 每日目标
        - unit: 单位 (g=克, 份=手动出粮)
        - last_feed_minutes: 距上次喂食分钟数
        - today_log: 今日手动喂食记录
        - device_eaten: 设备记录的实际进食克数
        """
        manual_total = self.get_today_total()
        if device_eaten is not None:
            # 设备数据：克
            eaten = device_eaten
            goal = goal_grams if goal_grams else self.GOAL_GRAMS
            unit = "g"
        else:
            # 手动记录：份
            eaten = manual_total
            goal = self.GOAL_PORTIONS
            unit = "份"
        goal_pct = min(int(eaten / goal * 100), 100)

        last_min = self.get_last_feed_minutes()
        if last_min is not None:
            # 4 小时从 100% 降到 0%
            time_based = max(0, int(100 - last_min / 240 * 100))
        else:
            time_based = 0

        return {
            "time_based": time_based,
            "today_goal": goal_pct,
            "today_amount": eaten,
            "goal_amount": goal,
            "unit": unit,
            "last_feed_minutes": round(last_min) if last_min else None,
            "today_log": self.get_today_list(),
            "device_eaten": device_eaten,
        }

    def _save(self):
        """持久化到 JSON 文件"""
        try:
            data = {
                "events": [{"ts": e.timestamp, "p": e.portions} for e in self._events],
                "daily_device": self._daily_device,
            }
            with open(self._filepath, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get_daily_summary(self, days: int = 7) -> list[dict]:
        """返回近 N 天的每日喂食汇总，按日期升序，无记录日填 0，含设备克数"""
        today = datetime.date.today()
        start = today - datetime.timedelta(days=days - 1)

        # 按日期分组（手动记录）
        daily: dict[str, int] = {}
        for e in self._events:
            d = datetime.date.fromtimestamp(e.timestamp)
            if d >= start:
                key = d.isoformat()
                daily[key] = daily.get(key, 0) + e.portions

        # 生成日期序列（升序），合并设备克数
        result = []
        for i in range(days):
            d = start + datetime.timedelta(days=i)
            key = d.isoformat()
            result.append({
                "date": key,
                "portions": daily.get(key, 0),
                "device_grams": self._daily_device.get(key),  # None if no device data
            })

        return result

    def _load(self):
        """从 JSON 文件加载（兼容旧格式）"""
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath) as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._events = [FeedEvent(timestamp=d["ts"], portions=d["p"])
                                for d in data.get("events", [])]
                self._daily_device = data.get("daily_device", {})
            elif isinstance(data, list):
                # 兼容旧格式（纯数组）
                self._events = [FeedEvent(timestamp=d["ts"], portions=d["p"]) for d in data]
                self._daily_device = {}
        except Exception:
            self._events = []
            self._daily_device = {}
