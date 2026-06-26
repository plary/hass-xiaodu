"""XiaoDu switch/outlet entities."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_TYPES
from .coordinator import XiaoDuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XiaoDuCoordinator = data["coordinator"]
    device_ids: list[str] = data["device_ids"]
    devices: list[dict] = data["devices"]

    entities = []
    for dev in devices:
        if dev["applianceId"] not in device_ids:
            continue
        app_types = dev.get("applianceTypes", [])
        if any(t in SWITCH_TYPES for t in app_types):
            entities.append(XiaoDuSwitch(coordinator, dev, data["house_id"]))

            # Clothes rack: register extra panel entities
            if "CLOTHES_RACK" in app_types:
                panels = _extract_panels(dev)
                for panel in panels:
                    entities.append(XiaoDuSwitchPanel(coordinator, dev, data["house_id"], panel))

    async_add_entities(entities)


def _extract_panels(dev: dict) -> list[dict]:
    """Extract panel controls from clothes rack device."""
    panels_out = []
    for panel_group in dev.get("panels", []):
        if panel_group.get("title") == "功能控制":
            for item in panel_group.get("list", []):
                actions = item.get("actions", [])
                header_on = actions[0].get("headerName") if len(actions) > 0 else None
                header_off = actions[1].get("headerName") if len(actions) > 1 else None
                payload = actions[0].get("payload") if len(actions) > 0 else None
                panels_out.append({
                    "name": item.get("name"),
                    "value": item.get("value"),
                    "label": item.get("label", item.get("name", "")),
                    "header_on": header_on,
                    "header_off": header_off,
                    "payload": payload,
                })
    return panels_out


class XiaoDuSwitch(CoordinatorEntity, SwitchEntity):
    """XiaoDu switch or outlet."""

    def __init__(self, coordinator: XiaoDuCoordinator, dev: dict, house_id: str) -> None:
        super().__init__(coordinator)
        self._appliance_id = dev["applianceId"]
        self._house_id = house_id
        self._attr_unique_id = f"xiaodu_{self._appliance_id}"
        self._attr_name = dev.get("friendlyName", self._appliance_id)
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:toggle-switch"
        if "灯" in self._attr_name:
            self._attr_icon = "mdi:lightbulb"
        if dev.get("applianceTypes", [None])[0] == "SOCKET":
            self._attr_icon = "mdi:power-socket-us"
            self._attr_device_class = "outlet"

    @callback
    def _handle_coordinator_update(self) -> None:
        app = self.coordinator.get_appliance(self._appliance_id)
        if app:
            try:
                state = app.get("stateSetting", {}).get("turnOnState", {})
                self._attr_is_on = state.get("value", "").upper() == "ON"
            except (KeyError, TypeError):
                pass
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_on(self._appliance_id, self._house_id)
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._appliance_id, self._house_id)
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class XiaoDuSwitchPanel(CoordinatorEntity, SwitchEntity):
    """Multi-function panel switch (e.g., clothes rack controls)."""

    def __init__(self, coordinator: XiaoDuCoordinator, dev: dict, house_id: str, panel: dict) -> None:
        super().__init__(coordinator)
        self._appliance_id = dev["applianceId"]
        self._house_id = house_id
        self._panel = panel
        self._attr_unique_id = f"xiaodu_{self._appliance_id}_panel_{panel['name']}_{panel['value']}"
        self._attr_name = f"{dev.get('friendlyName', '')} {panel['label']}"
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:tune-vertical"

    @callback
    def _handle_coordinator_update(self) -> None:
        # Panel state is not directly queryable, keep last known
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.switch_panel(
            self._appliance_id, self._panel["name"], self._panel["value"],
            self._panel["header_on"], str(self._panel["payload"]) if self._panel["payload"] else None,
            self._house_id,
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.switch_panel(
            self._appliance_id, self._panel["name"], self._panel["value"],
            self._panel["header_off"], str(self._panel["payload"]) if self._panel["payload"] else None,
            self._house_id,
        )
        self._attr_is_on = False
        self.async_write_ha_state()
