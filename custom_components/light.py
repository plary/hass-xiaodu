"""XiaoDu light entities."""

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LIGHT_TYPES
from .coordinator import XiaoDuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XiaoDuCoordinator = data["coordinator"]
    devices: list[dict] = data["devices"]

    entities = []
    for dev in devices:
        app_types = dev.get("applianceTypes", [])
        if any(t in LIGHT_TYPES for t in app_types):
            entities.append(XiaoDuLight(coordinator, dev, data["house_id"]))

    async_add_entities(entities)


class XiaoDuLight(CoordinatorEntity, LightEntity):
    """XiaoDu light entity."""

    def __init__(self, coordinator: XiaoDuCoordinator, dev: dict, house_id: str) -> None:
        super().__init__(coordinator)
        self._appliance_id = dev["applianceId"]
        self._house_id = house_id
        self._attr_unique_id = f"xiaodu_{self._appliance_id}_light"
        self._attr_name = dev.get("friendlyName", self._appliance_id)
        self._attr_has_entity_name = False
        self._effect_map: dict[str, str] = {}

        # Determine capabilities from stateSetting
        state = dev.get("stateSetting", {})
        has_brightness = "brightness" in state
        has_ct = "colorTemperatureInKelvin" in state
        has_mode = "mode" in state

        if has_brightness and has_ct:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif has_brightness:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

        if has_mode:
            self._attr_supported_features = LightEntityFeature.EFFECT
            value_range = state.get("mode", {}).get("valueRangeMap", {})
            self._effect_map = value_range
            self._attr_effect_list = list(value_range.values())

        self._update_state(dev)

    @callback
    def _handle_coordinator_update(self) -> None:
        app = self.coordinator.get_appliance(self._appliance_id)
        if app:
            self._update_state(app)
        self.async_write_ha_state()

    def _update_state(self, dev: dict) -> None:
        """Update state from device data."""
        try:
            state = dev.get("stateSetting", {})
            self._attr_is_on = state.get("turnOnState", {}).get("value", "").upper() == "ON"

            if self._attr_color_mode == ColorMode.BRIGHTNESS:
                brightness = state.get("brightness", {}).get("value")
                if brightness is not None:
                    self._attr_brightness = round(int(brightness) / 100 * 255)

            elif self._attr_color_mode == ColorMode.COLOR_TEMP:
                brightness = state.get("brightness", {}).get("value")
                if brightness is not None:
                    self._attr_brightness = round(int(brightness) / 100 * 255)

                ct_data = state.get("colorTemperatureInKelvin", {})
                ct_value = ct_data.get("value")
                ct_range = ct_data.get("valueKelvinRangeMap", {})
                if ct_value is not None and ct_range:
                    ct_min = ct_range.get("min", 2700)
                    ct_max = ct_range.get("max", 6500)
                    self._attr_min_color_temp_kelvin = ct_min
                    self._attr_max_color_temp_kelvin = ct_max
                    middle = ct_max - ct_min
                    self._attr_color_temp_kelvin = round(int(ct_value) / 100 * middle) + ct_min

            if "mode" in state:
                mode_val = state.get("mode", {}).get("value")
                if mode_val and mode_val in self._effect_map:
                    self._attr_effect = self._effect_map[mode_val]
        except (KeyError, TypeError, ValueError) as exc:
            _LOGGER.debug("Light state update error for %s: %s", self._appliance_id, exc)

    async def async_turn_on(self, **kwargs: Any) -> None:
        api = self.coordinator.api

        if not kwargs:
            await api.turn_on(self._appliance_id, self._house_id)
        else:
            if ATTR_BRIGHTNESS in kwargs:
                brightness_pct = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
                await api.set_brightness(self._appliance_id, brightness_pct, self._house_id)

            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                ct = kwargs[ATTR_COLOR_TEMP_KELVIN]
                # Convert Kelvin to percentage
                ct_min = self._attr_min_color_temp_kelvin or 2700
                ct_max = self._attr_max_color_temp_kelvin or 6500
                middle = ct_max - ct_min
                if middle > 0:
                    pct = round((ct - ct_min) / middle * 100)
                    await api.set_color_temperature(self._appliance_id, pct, self._house_id)

            if ATTR_EFFECT in kwargs:
                effect = kwargs[ATTR_EFFECT]
                for key, val in self._effect_map.items():
                    if val == effect:
                        await api.set_light_mode(self._appliance_id, key, self._house_id)
                        break

        self._attr_is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._appliance_id, self._house_id)
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
