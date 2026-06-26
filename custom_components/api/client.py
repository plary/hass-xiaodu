"""XiaoDu Smart Home API client.

Uses BDUSS cookie (百度账号长期令牌, ~6个月有效期) to talk to
xiaodu.baidu.com web API.

Endpoints:
  /appserver/gateway/app/v1          - session validation
  /saiya/smarthome/devicelist        - device list
  /saiya/smarthome/appliancedetails  - single device detail
  /saiya/smarthome/appliance         - batch device details
  /saiya/smarthome/directivesend     - send DuerOS control command
  /saiya/smarthome/unified           - trigger scene
"""

import logging
from typing import Any

import aiohttp

from ..const import XIAODU_HOST

_LOGGER = logging.getLogger(__name__)


def _common_headers(bduss: str) -> dict[str, str]:
    return {
        "Cookie": f"BDUSS={bduss}",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://xiaodu.baidu.com/saiya/smarthome/index.html",
        "Accept": "application/json",
    }


class XiaoDuAPI:
    """Async API client for XiaoDu Smart Home."""

    def __init__(self, session: aiohttp.ClientSession, bduss: str) -> None:
        self._session = session
        self._bduss = bduss
        self._headers = _common_headers(bduss)

    async def check_session(self) -> bool:
        """Validate BDUSS cookie by calling the gateway endpoint."""
        try:
            async with self._session.post(
                f"{XIAODU_HOST}/appserver/gateway/app/v1",
                json={"url": "dueros://smarthome.bot.dueros.ai/gateway/myspeaker"},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                return data.get("status") == 0
        except Exception as exc:
            _LOGGER.error("XiaoDu session check failed: %s", exc)
            return False

    async def get_home_list(self) -> dict[str, str]:
        """Get list of homes. Returns {houseId: houseName}."""
        try:
            async with self._session.post(
                f"{XIAODU_HOST}/appserver/gateway/app/v1",
                json={"url": "dueros://smarthome.bot.dueros.ai/gateway/myhouse"},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                homes = {}
                if data.get("status") == 0:
                    for home in data.get("data", []):
                        homes[home["houseId"]] = home["houseName"]
                return homes
        except Exception as exc:
            _LOGGER.error("XiaoDu get home list failed: %s", exc)
            return {}

    async def get_device_list(self, house_id: str) -> list[dict[str, Any]]:
        """Get all devices in a home."""
        try:
            async with self._session.get(
                f"{XIAODU_HOST}/saiya/smarthome/devicelist",
                params={"from": "h5_control", "withscene": "1", "generalscene": "3"},
                headers=self._headers,
                cookies={"HOUSE_ID": house_id},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("status") == 0:
                    return data.get("data", {}).get("appliances", [])
                _LOGGER.warning("XiaoDu device list returned status: %s", data.get("status"))
                return []
        except Exception as exc:
            _LOGGER.error("XiaoDu get device list failed: %s", exc)
            return []

    async def get_device_detail(self, house_id: str, appliance_id: str) -> dict[str, Any]:
        """Get detailed info for a single device."""
        try:
            async with self._session.get(
                f"{XIAODU_HOST}/saiya/smarthome/appliancedetails",
                params={"applianceId": appliance_id, "version": 2, "from": "h5"},
                headers=self._headers,
                cookies={"HOUSE_ID": house_id},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("status") == 0:
                    return data.get("data", {})
                return {}
        except Exception as exc:
            _LOGGER.error("XiaoDu get device detail failed for %s: %s", appliance_id, exc)
            return {}

    async def get_devices_batch(self, house_id: str, appliance_ids: list[str]) -> dict[str, Any]:
        """Get details for multiple devices at once."""
        try:
            async with self._session.get(
                f"{XIAODU_HOST}/saiya/smarthome/appliance",
                json={
                    "enableCancelToken": True,
                    "method": "GET_APPLIANCES_BY_ID",
                    "params": {
                        "from": "h5_control",
                        "applianceIdList": appliance_ids,
                        "clientCuidList": [],
                        "enablecache": True,
                    },
                },
                headers=self._headers,
                cookies={"HOUSE_ID": house_id},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("status") == 0:
                    return data.get("data", {})
                return {}
        except Exception as exc:
            _LOGGER.error("XiaoDu batch get devices failed: %s", exc)
            return {}

    async def send_command(self, payload: dict[str, Any], house_id: str = "") -> bool:
        """Send a DuerOS ConnectedHome directive."""
        try:
            cookies = {"HOUSE_ID": house_id} if house_id else {}
            async with self._session.post(
                f"{XIAODU_HOST}/saiya/smarthome/directivesend",
                json=payload,
                headers=self._headers,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                success = resp.status == 200
                if not success:
                    _LOGGER.error("XiaoDu command failed: %s -> %s", payload.get("header", {}).get("name"), data)
                return success
        except Exception as exc:
            _LOGGER.error("XiaoDu send command error: %s", exc)
            return False

    async def trigger_scene(self, scene_id: str, house_id: str = "") -> bool:
        """Trigger a scene."""
        try:
            cookies = {"HOUSE_ID": house_id} if house_id else {}
            async with self._session.post(
                f"{XIAODU_HOST}/saiya/smarthome/unified",
                json={"method": "triggerScene", "params": {"sceneId": scene_id}},
                headers=self._headers,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                return resp.status == 200
        except Exception as exc:
            _LOGGER.error("XiaoDu trigger scene error: %s", exc)
            return False

    # ── High-level commands ──

    def _cmd(self, namespace: str, name: str, appliance_id: str, extra: dict | None = None) -> dict:
        """Build a DuerOS directive payload."""
        payload: dict[str, Any] = {
            "header": {"namespace": namespace, "name": name, "payloadVersion": 3},
            "payload": {
                "applianceId": appliance_id,
                "appliance": {"applianceId": [appliance_id]},
                "parameters": {"proxyConnectStatus": False},
                **(extra or {}),
            },
        }
        return payload

    async def turn_on(self, appliance_id: str, house_id: str = "") -> bool:
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "TurnOnRequest", appliance_id,
                       {"turnOnState": {"value": "ON"}}),
            house_id,
        )

    async def turn_off(self, appliance_id: str, house_id: str = "") -> bool:
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "TurnOffRequest", appliance_id,
                       {"turnOnState": {"value": "OFF"}}),
            house_id,
        )

    async def set_brightness(self, appliance_id: str, brightness: int, house_id: str = "") -> bool:
        """Set brightness (0-100 percent)."""
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "SetBrightnessPercentageRequest", appliance_id,
                       {"brightness": {"value": brightness},
                        "parameters": {"attribute": "brightness", "attributeValue": brightness, "proxyConnectStatus": False}}),
            house_id,
        )

    async def set_color_temperature(self, appliance_id: str, value: int, house_id: str = "") -> bool:
        """Set color temperature (0-100 percent)."""
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "SetColorTemperatureRequest", appliance_id,
                       {"colorTemperatureInKelvin": value,
                        "parameters": {"attribute": "colorTemperatureInKelvin", "attributeValue": value, "proxyConnectStatus": False}}),
            house_id,
        )

    async def set_light_mode(self, appliance_id: str, mode: str, house_id: str = "") -> bool:
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "SetModeRequest", appliance_id,
                       {"mode": {"value": mode},
                        "parameters": {"attribute": "mode", "attributeValue": mode, "proxyConnectStatus": False}}),
            house_id,
        )

    async def curtain_open(self, appliance_id: str, house_id: str = "") -> bool:
        return await self.turn_on(appliance_id, house_id)

    async def curtain_close(self, appliance_id: str, house_id: str = "") -> bool:
        return await self.turn_off(appliance_id, house_id)

    async def curtain_stop(self, appliance_id: str, house_id: str = "") -> bool:
        return await self.send_command(
            self._cmd("DuerOS.ConnectedHome.Control", "PauseRequest", appliance_id),
            house_id,
        )

    async def set_ac_mode(self, appliance_id: str, mode: str, house_id: str = "") -> bool:
        """Set AC mode (COOL/HEAT/FAN/AUTO/DEHUMIDIFICATION)."""
        payload = self._cmd("DuerOS.ConnectedHome.Control", "SetModeRequest", appliance_id,
                            {"mode": {"value": mode.upper()}})
        payload["header"]["payloadVersion"] = 1
        return await self.send_command(payload, house_id)

    async def set_ac_on(self, appliance_id: str, house_id: str = "") -> bool:
        payload = self._cmd("DuerOS.ConnectedHome.Control", "TurnOnRequest", appliance_id)
        payload["header"]["payloadVersion"] = 1
        return await self.send_command(payload, house_id)

    async def set_ac_off(self, appliance_id: str, house_id: str = "") -> bool:
        payload = self._cmd("DuerOS.ConnectedHome.Control", "TurnOffRequest", appliance_id)
        payload["header"]["payloadVersion"] = 1
        return await self.send_command(payload, house_id)

    async def ac_temp_up(self, appliance_id: str, house_id: str = "") -> bool:
        payload = self._cmd("DuerOS.ConnectedHome.Control", "IncrementRequest", appliance_id)
        payload["header"]["payloadVersion"] = 1
        return await self.send_command(payload, house_id)

    async def ac_temp_down(self, appliance_id: str, house_id: str = "") -> bool:
        payload = self._cmd("DuerOS.ConnectedHome.Control", "DecrementRequest", appliance_id)
        payload["header"]["payloadVersion"] = 1
        return await self.send_command(payload, house_id)

    async def switch_panel(self, appliance_id: str, name: str, value: str,
                           header_name: str, payload_obj: str | None, house_id: str = "") -> bool:
        """Control a multi-function panel (e.g., clothes rack)."""
        import json
        payload = json.loads(payload_obj) if payload_obj else {}
        payload.setdefault("header", {}).update({
            "namespace": "DuerOS.ConnectedHome.Control",
            "name": header_name,
            "payloadVersion": 3,
        })
        payload.setdefault("payload", {}).update({
            "applianceId": appliance_id,
            "appliance": {"applianceId": [appliance_id]},
            "parameters": {"attribute": name, "attributeValue": value, "proxyConnectStatus": False},
        })
        return await self.send_command(payload, house_id)
