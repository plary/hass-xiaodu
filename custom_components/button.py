"""XiaoDu scene trigger buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XiaoDuCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XiaoDuCoordinator = data["coordinator"]

    # Extract scenes from coordinator data
    raw = coordinator.data.get("raw", {}) if coordinator.data else {}
    # Scenes are in the original API response, check for them
    appliances = coordinator.data.get("appliances", []) if coordinator.data else []
    # Also check if raw data has scenes
    # For now, we don't create button entities from devices
    # Scenes are handled separately if needed
    async_add_entities([])


class XiaoDuSceneButton(CoordinatorEntity, ButtonEntity):
    """XiaoDu scene trigger button."""

    def __init__(self, coordinator: XiaoDuCoordinator, scene_id: str, name: str, house_id: str) -> None:
        super().__init__(coordinator)
        self._scene_id = scene_id
        self._house_id = house_id
        self._attr_unique_id = f"xiaodu_scene_{scene_id}"
        self._attr_name = name
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:playlist-play"

    async def async_press(self) -> None:
        await self.coordinator.api.trigger_scene(self._scene_id, self._house_id)
