"""Config flow for XiaoDu Smart Home."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import XiaoDuAPI
from .const import CONF_BDUSS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class XiaoDuFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for XiaoDu Smart Home."""

    VERSION = 1

    def __init__(self) -> None:
        self._bduss: str = ""
        self._api: XiaoDuAPI | None = None
        self._homes: dict[str, str] = {}
        self._house_id: str = ""
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: Enter BDUSS cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._bduss = user_input[CONF_BDUSS].strip()
            if not self._bduss:
                errors["base"] = "invalid_auth"
            else:
                session = async_get_clientsession(self.hass)
                self._api = XiaoDuAPI(session, self._bduss)

                if await self._api.check_session():
                    self._homes = await self._api.get_home_list()
                    if self._homes:
                        return await self.async_step_home()
                    errors["base"] = "no_homes"
                else:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_BDUSS): str}),
            errors=errors,
            description_placeholders={
                "hint": "从浏览器开发者工具中获取 BDUSS Cookie 值",
            },
        )

    async def async_step_home(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 2: Select home."""
        if user_input is not None:
            self._house_id = user_input["house_id"]
            self._devices = await self._api.get_device_list(self._house_id)
            if self._devices:
                return await self.async_step_device()
            return self.async_abort(reason="no_devices")

        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema({
                vol.Required("house_id"): vol.In(self._homes),
            }),
        )

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 3: Select devices."""
        if user_input is not None:
            device_ids = user_input["device_ids"]
            if not device_ids:
                return self.async_show_form(
                    step_id="device",
                    data_schema=self._device_schema(),
                    errors={"base": "no_device_selected"},
                )

            # Store all devices for entity creation
            selected = [d for d in self._devices if d["applianceId"] in device_ids]
            home_name = self._homes.get(self._house_id, self._house_id)

            return self.async_create_entry(
                title=f"小度: {home_name}",
                data={
                    CONF_BDUSS: self._bduss,
                    "house_id": self._house_id,
                    "device_ids": device_ids,
                    "devices": selected,
                },
            )

        return self.async_show_form(
            step_id="device",
            data_schema=self._device_schema(),
        )

    def _device_schema(self) -> vol.Schema:
        """Build device selection schema."""
        device_map = {}
        for d in self._devices:
            name = d.get("friendlyName", d["applianceId"])
            types = d.get("applianceTypes", [])
            type_str = types[0] if types else "UNKNOWN"
            device_map[d["applianceId"]] = f"{name} ({type_str})"

        return vol.Schema({
            vol.Required("device_ids"): vol.multi_select(device_map),
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return XiaoDuOptionsFlowHandler(config_entry)


class XiaoDuOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow to update BDUSS cookie."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Update BDUSS cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            new_bduss = user_input[CONF_BDUSS].strip()
            if not new_bduss:
                errors["base"] = "invalid_auth"
            else:
                session = async_get_clientsession(self.hass)
                api = XiaoDuAPI(session, new_bduss)
                if await api.check_session():
                    new_data = {**self._config_entry.data, CONF_BDUSS: new_bduss}
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=new_data
                    )
                    return self.async_create_entry(title="", data={})
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_BDUSS): str}),
            errors=errors,
            description_placeholders={"hint": "更新 BDUSS Cookie（约6个月过期一次）"},
        )
