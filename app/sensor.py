"""
米家蓝牙温湿度计控制器
设备型号: miaomiaoce.sensor_ht.t9
"""
import time
from dataclasses import dataclass, field
from typing import Any

from app.cloud import MiCloudClient


@dataclass
class SensorState:
    """温湿度传感器状态"""
    did: str = ""
    name: str = ""
    model: str = ""

    # SIID 3: Temperature Humidity Sensor
    temperature: float | None = None      # piid 1001
    humidity: int | None = None           # piid 1002

    # SIID 2: Battery
    battery: int | None = None            # piid 1003

    last_updated: float = field(default_factory=time.time)
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "did": self.did,
            "name": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "battery": self.battery,
            "last_error": self.last_error,
        }


class SensorSpec:
    """温湿度计 MIoT 常量"""
    SIID_BATTERY = 2
    PIID_BATTERY = 1003

    SIID_SENSOR = 3
    PIID_TEMPERATURE = 1001
    PIID_HUMIDITY = 1002

    READABLE_PROPS: list[tuple[int, int]] = [
        (3, 1001),  # temperature
        (3, 1002),  # humidity
        (2, 1003),  # battery
    ]


class SensorController:
    """温湿度传感器控制器"""

    def __init__(self, cloud: MiCloudClient, did: str):
        self.cloud = cloud
        self.did = did
        self._device_info: dict | None = None

    async def init(self) -> bool:
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

    async def get_state(self) -> SensorState:
        state = SensorState(
            did=self.did,
            name=self.name,
            model=self.model,
        )

        raw = await self.cloud.get_props(self.did, SensorSpec.READABLE_PROPS)

        state.temperature = raw.get("3-1001")
        state.humidity = raw.get("3-1002")
        state.battery = raw.get("2-1003")
        state.last_updated = time.time()

        return state
