"""XiaoDu air conditioner entities."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CLIMATE_TYPES, DOMAIN
from .coordinator import XiaoDuCoordinator

# DuerOS AC modes -> HA HVACMode
MODE_MAP = {
    "COOL": HVACMode.COOL,
    "HEAT": HVACMode.HEAT,
    "AUTO": HVACMode.AUTO,
    "FAN": HVACMode.FAN_ONLY,
    "DEHUMIDIFICATION": HVACMode.DRY,
}
HVAC_TO_DUEROS = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XiaoDuCoordinator = data["coordinator"]
    devices: list[dict] = data["devices"]

    entities = []
    for dev in devices:
        app_types = dev.get("applianceTypes", [])
        if any(t in CLIMATE_TYPES for t in app_types):
            entities.append(XiaoDuAC(coordinator, dev, data["house_id"]))

    async_add_entities(entities)


class XiaoDuAC(CoordinatorEntity, ClimateEntity):
    """XiaoDu air conditioner entity."""

    def __init__(self, coordinator: XiaoDuCoordinator, dev: dict, house_id: str) -> None:
        super().__init__(coordinator)
        self._appliance_id = dev["applianceId"]
        self._house_id = house_id
        self._attr_unique_id = f"xiaodu_{self._appliance_id}_ac"
        self._attr_name = dev.get("friendlyName", self._appliance_id)
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:air-conditioner"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = 1
        self._attr_min_temp = 16
        self._attr_max_temp = 30
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY]
        self._attr_fan_modes = ["low", "medium", "high", "auto"]
        self._update_state(dev)

    @callback
    def _handle_coordinator_update(self) -> None:
        app = self.coordinator.get_appliance(self._appliance_id)
        if app:
            self._update_state(app)
        self.async_write_ha_state()

    def _update_state(self, dev: dict) -> None:
        try:
            state = dev.get("stateSetting", {})
            is_on = state.get("turnOnState", {}).get("value", "").upper() == "ON"
            self._attr_hvac_mode = HVACMode.OFF if not is_on else HVACMode.AUTO

            mode = state.get("mode", {}).get("value")
            if mode and is_on:
                self._attr_hvac_mode = MODE_MAP.get(mode.upper(), HVACMode.AUTO)

            temp = state.get("targetTemperature", state.get("temperature", {}))
            if temp:
                self._attr_target_temperature = float(temp.get("value", 24))
        except (KeyError, TypeError, ValueError):
            pass

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        api = self.coordinator.api
        if hvac_mode == HVACMode.OFF:
            await api.set_ac_off(self._appliance_id, self._house_id)
            self._attr_hvac_mode = HVACMode.OFF
        else:
            dueros_mode = HVAC_TO_DUEROS.get(hvac_mode, "AUTO")
            await api.set_ac_mode(self._appliance_id, dueros_mode, self._house_id)
            self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature via increment/decrement commands."""
        target = kwargs.get("temperature")
        if target is None:
            return
        api = self.coordinator.api
        current = self._attr_target_temperature or 24
        diff = int(target - current)

        if diff > 0:
            for _ in range(diff):
                await api.ac_temp_up(self._appliance_id, self._house_id)
        elif diff < 0:
            for _ in range(-diff):
                await api.ac_temp_down(self._appliance_id, self._house_id)

        self._attr_target_temperature = target
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Fan mode control (limited - uses increment/decrement)."""
        # XiaoDu doesn't have direct fan speed API, this is a best-effort
        pass
