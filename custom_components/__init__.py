"""XiaoDu Smart Home integration for Home Assistant.

Pulls devices from XiaoDu (小度) ecosystem into Home Assistant.
Uses BDUSS cookie for authentication (~6 months validity).
Supports: lights, switches, outlets, curtains, ACs, locks, clothes racks, etc.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import XiaoDuAPI
from .const import CONF_BDUSS, DOMAIN
from .coordinator import XiaoDuCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.COVER,
    Platform.CLIMATE,
    Platform.BUTTON,
    Platform.LOCK,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XiaoDu from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    bduss = entry.data[CONF_BDUSS]
    house_id = entry.data["house_id"]
    device_ids = entry.data["device_ids"]

    session = async_get_clientsession(hass)
    api = XiaoDuAPI(session, bduss)

    # Validate cookie
    if not await api.check_session():
        _LOGGER.error("XiaoDu BDUSS cookie expired or invalid")
        return False

    coordinator = XiaoDuCoordinator(hass, api, house_id)
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "house_id": house_id,
        "device_ids": device_ids,
    }

    # First refresh
    await coordinator.async_config_entry_first_refresh()

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "XiaoDu Smart Home loaded: house=%s, %d devices selected",
        house_id,
        len(device_ids),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
