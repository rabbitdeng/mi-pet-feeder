"""
小米云服务客户端（基于 miservice 库，支持 passToken 免密登录）
"""
import logging
from random import choices
from string import ascii_letters, digits
from typing import Any

import aiohttp
from miservice import MiAccount, MiIOService

logger = logging.getLogger(__name__)


class XiaomiCloudError(Exception):
    """小米云服务异常"""


class MiCloudClient:
    """小米云服务客户端"""

    def __init__(
        self,
        username: str = "",
        password: str = "",
        user_id: str = "",
        pass_token: str = "",
        token_store: str = ".mi.token",
    ):
        self.username = username
        self.password = password
        self._user_id = user_id
        self._pass_token = pass_token
        self.token_store = token_store
        self._session: aiohttp.ClientSession | None = None
        self._account: MiAccount | None = None
        self._service: MiIOService | None = None
        self._logged_in = False

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """登录小米云服务"""
        self._session = aiohttp.ClientSession()

        if self._user_id and self._pass_token:
            # passToken 免密登录 — 利用 miservice 的 cookie 认证机制
            device_id = "".join(choices(ascii_letters + digits, k=16)).upper()
            self._account = MiAccount(
                self._session, self.username or "token_auth", "", self.token_store
            )
            self._account.token = {
                "deviceId": device_id,
                "userId": self._user_id,
                "passToken": self._pass_token,
            }
            ok = await self._account.login("xiaomiio")
            if not ok:
                raise XiaomiCloudError("passToken 登录失败，可能已过期")
        elif self.username and self.password:
            # 密码登录
            self._account = MiAccount(
                self._session, self.username, self.password, self.token_store
            )
            ok = await self._account.login("xiaomiio")
            if not ok:
                raise XiaomiCloudError("密码登录失败")
        else:
            raise XiaomiCloudError("请提供 passToken 或账号密码")

        self._service = MiIOService(self._account)
        self._logged_in = True
        logger.info("小米云服务登录成功")

    async def close(self) -> None:
        """关闭连接"""
        self._logged_in = False
        if self._session:
            await self._session.close()
            self._session = None
        self._account = None
        self._service = None

    # ------------------------------------------------------------------
    # 设备管理
    # ------------------------------------------------------------------

    def _ensure_auth(self):
        if not self._logged_in:
            raise XiaomiCloudError("未登录，请先调用 login()")

    async def list_devices(self) -> list[dict]:
        """列出所有米家设备"""
        self._ensure_auth()
        try:
            return await self._service.device_list(
                getVirtualModel=True, getHuamiDevices=1
            )
        except Exception as e:
            raise XiaomiCloudError(f"获取设备列表失败: {e}")

    async def find_device(
        self, *, did: str | None = None, name: str | None = None
    ) -> dict | None:
        """按 DID 或名称查找设备"""
        devices = await self.list_devices()
        for d in devices:
            if did and d.get("did") == did:
                return d
            if name and name.lower() in (d.get("name", "")).lower():
                return d
        return None

    # ------------------------------------------------------------------
    # MIoT 属性读写
    # ------------------------------------------------------------------

    async def get_prop(self, did: str, siid: int, piid: int) -> Any:
        """读取单个 MIoT 属性"""
        self._ensure_auth()
        try:
            return await self._service.miot_get_prop(did, (siid, piid))
        except Exception:
            logger.exception("读取属性失败 siid=%s piid=%s", siid, piid)
            return None

    async def get_props(self, did: str, props: list[tuple[int, int]]) -> dict[str, Any]:
        """批量读取 MIoT 属性"""
        self._ensure_auth()
        try:
            values = await self._service.miot_get_props(
                did, [(s, p) for s, p in props]
            )
            return {f"{s}-{p}": v for (s, p), v in zip(props, values)}
        except Exception:
            logger.exception("批量读取属性失败")
            return {f"{s}-{p}": None for s, p in props}

    async def set_prop(self, did: str, siid: int, piid: int, value: Any) -> bool:
        """设置 MIoT 属性"""
        self._ensure_auth()
        try:
            code = await self._service.miot_set_prop(did, (siid, piid), value)
            return code == 0
        except Exception:
            logger.exception("设置属性失败 siid=%s piid=%s", siid, piid)
            return False

    # ------------------------------------------------------------------
    # MIoT 动作
    # ------------------------------------------------------------------

    async def do_action(
        self, did: str, siid: int, aiid: int, params: list | None = None
    ) -> bool:
        """执行 MIoT 动作"""
        self._ensure_auth()
        try:
            code = await self._service.miot_action(
                did, (siid, aiid), params or []
            )
            return code == 0
        except Exception:
            logger.exception("动作执行失败 siid=%s aiid=%s", siid, aiid)
            return False
