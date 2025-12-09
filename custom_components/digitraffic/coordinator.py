from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import LOGGER


class DigitrafficDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, situation_types=None):
        self.api = api
        self.last_update_time = None
        self.situation_types = situation_types

        super().__init__(
            hass,
            LOGGER,
            name="Digitraffic Traffic Messages",
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self):
        try:
            data = await self.api.fetch_active_messages(self.situation_types)
            # Update timestamp on successful fetch
            self.last_update_time = dt_util.utcnow().isoformat()
            # ✅ Always return RAW unfiltered features
            return data.get("features", [])
        except Exception as err:
            msg = f"Digitraffic API error: {err}"
            raise UpdateFailed(msg) from err

    def update_situation_types(self, situation_types):
        """Update situation types filter."""
        self.situation_types = situation_types
