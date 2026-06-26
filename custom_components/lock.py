"""XiaoDu lock entities."""

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOCK_TYPES
from .coordinator import XiaoDuCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XiaoDuCoordinator = data["coordinator"]
    devices: list[dict] = data["devices"]

    entities = []
    for dev in devices:
        app_types = dev.get("applianceTypes", [])
        if any(t in LOCK_TYPES for t in app_types):
            entities.append(XiaoDuLock(coordinator, dev, data["house_id"]))

    async_add_entities(entities)


class XiaoDuLock(CoordinatorEntity, LockEntity):
    """XiaoDu lock entity."""

    def __init__(self, coordinator: XiaoDuCoordinator, dev: dict, house_id: str) -> None:
        super().__init__(coordinator)
        self._appliance_id = dev["applianceId"]
        self._house_id = house_id
        self._attr_unique_id = f"xiaodu_{self._appliance_id}_lock"
        self._attr_name = dev.get("friendlyName", self._appliance_id)
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:lock"
        self._update_state(dev)

    @callback
    def _handle_coordinator_update(self) -> None:
        app = self.coordinator.get_appliance(self._appliance_id)
        if app:
            self._update_state(app)
        self.async_write_ha_state()

    def _update_state(self, dev: dict) -> None:
        try:
            state = dev.get("stateSetting", {}).get("turnOnState", {})
            is_on = state.get("value", "").upper() == "ON"
            self._attr_is_locked = is_on
        except (KeyError, TypeError):
            pass

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_on(self._appliance_id, self._house_id)
        self._attr_is_locked = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._appliance_id, self._house_id)
        self._attr_is_locked = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
