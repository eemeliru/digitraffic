"""Data update coordinator for Digitraffic traffic messages."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import DigitrafficApiClient


class DigitrafficDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching Digitraffic traffic message data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DigitrafficApiClient,
        municipalities: list[str] | None = None,
        situation_types: list[str] | None = None,
    ) -> None:
        """
        Initialize coordinator for a specific service.

        Args:
            hass: Home Assistant instance.
            api: Digitraffic API client.
            municipalities: List of municipalities to filter messages.
            situation_types: List of situation types to filter messages.

        """
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

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """
        Fetch and filter messages for this service's municipalities and situation types.

        Returns:
            List of filtered traffic message features.

        Raises:
            UpdateFailed: If the API request fails.

        """
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

        except Exception as err:
            msg = f"Digitraffic API error: {err}"
            raise UpdateFailed(msg) from err
        else:
            return filtered_features

    def update_config(
        self,
        municipalities: list[str] | None = None,
        situation_types: list[str] | None = None,
    ) -> None:
        """
        Update service configuration.

        Args:
            municipalities: New list of municipalities to filter.
            situation_types: New list of situation types to filter.

        """
        if municipalities is not None:
            self.municipalities = municipalities
        if situation_types is not None:
            self.situation_types = situation_types
