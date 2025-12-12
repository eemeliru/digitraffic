from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import LOGGER


class DigitrafficDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, municipalities=None, situation_types=None):
        """Initialize coordinator for a specific service (municipality + situation types)."""
        self.api = api
        self.last_update_time = None
        self.municipalities = municipalities or []
        self.situation_types = situation_types

        # Create a descriptive name for this coordinator
        if municipalities:
            muni_str = ", ".join(municipalities)
            name = f"Digitraffic Traffic Messages ({muni_str})"
        else:
            name = "Digitraffic Traffic Messages"

        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self):
        """Fetch and filter messages for this service's municipalities and situation types."""
        try:
            data = await self.api.fetch_active_messages(self.situation_types)
            # Update timestamp on successful fetch
            self.last_update_time = dt_util.utcnow().isoformat()

            # Return filtered features for this service's municipalities
            features = data.get("features", [])

            # If no municipalities specified, return all
            if not self.municipalities:
                return features

            # Filter by municipalities
            filtered_features = []
            for feature in features:
                properties = feature.get("properties", {})
                announcements = properties.get("announcements", [])

                for ann in announcements:
                    location_details = ann.get("locationDetails", {})
                    road_location = location_details.get("roadAddressLocation", {})

                    primary_point = road_location.get("primaryPoint", {})
                    secondary_point = road_location.get("secondaryPoint", {})

                    primary_muni = primary_point.get("municipality")
                    secondary_muni = secondary_point.get("municipality")

                    if (
                        primary_muni in self.municipalities
                        or secondary_muni in self.municipalities
                    ):
                        filtered_features.append(feature)
                        break

            return filtered_features

        except Exception as err:
            msg = f"Digitraffic API error: {err}"
            raise UpdateFailed(msg) from err

    def update_config(self, municipalities=None, situation_types=None):
        """Update service configuration."""
        if municipalities is not None:
            self.municipalities = municipalities
        if situation_types is not None:
            self.situation_types = situation_types
