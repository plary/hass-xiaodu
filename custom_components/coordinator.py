"""Data coordinator for XiaoDu Smart Home."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import XiaoDuAPI
from .const import DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class XiaoDuCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to poll XiaoDu device states."""

    def __init__(self, hass: HomeAssistant, api: XiaoDuAPI, house_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{house_id}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.api = api
        self.house_id = house_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch device states from XiaoDu."""
        try:
            appliances = await self.api.get_device_list(self.house_id)
        except Exception as exc:
            raise UpdateFailed(f"XiaoDu API error: {exc}") from exc

        if not appliances:
            _LOGGER.warning("XiaoDu returned empty device list for house %s", self.house_id)
            return {"appliances": []}

        # Index by applianceId for quick lookup
        by_id = {a["applianceId"]: a for a in appliances}
        return {"appliances": appliances, "by_id": by_id}

    def get_appliance(self, appliance_id: str) -> dict[str, Any] | None:
        """Get a specific appliance by ID."""
        if not self.data:
            return None
        return self.data.get("by_id", {}).get(appliance_id)
