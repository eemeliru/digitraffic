"""Camera platform for Digitraffic weathercam images."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components.camera import Camera
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import ATTRIBUTION, DIGITRAFFIC_USER, DOMAIN, ENTITY_TYPE_WEATHERCAM, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

SCAN_INTERVAL = timedelta(minutes=10)


def _load_weathercam_data(data_file: Path) -> dict:
    """
    Load weathercam data from file (executed in executor).

    Args:
        data_file: Path to the weathercam data JSON file.

    Returns:
        Dictionary containing weathercam data.

    """
    with data_file.open(encoding="utf-8") as f:
        return json.load(f)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Digitraffic weathercam cameras."""
    data = hass.data[DOMAIN][entry.entry_id]
    entity_type = data.get("entity_type")

    # Only set up cameras for weathercam entries
    if entity_type != ENTITY_TYPE_WEATHERCAM:
        return

    # Get list of cameras from entry data
    cameras_config = entry.data.get("cameras", [])
    if not cameras_config:
        LOGGER.error("No cameras found in config entry")
        return

    # Load weathercam data
    data_file = Path(__file__).parent / "data" / "weathercam_data.json"
    if not data_file.exists():
        LOGGER.error("Weathercam data file not found")
        return

    weathercam_data = await hass.async_add_executor_job(
        _load_weathercam_data, data_file
    )

    # Perform entity registry cleanup
    expected_preset_ids = _get_expected_preset_ids(cameras_config)
    _cleanup_removed_entities(hass, entry, expected_preset_ids)

    # Create camera entities (all configured ones, Home Assistant handles duplicates)
    cameras = _create_camera_entities(hass, entry, cameras_config, weathercam_data)

    LOGGER.info("Created %d new weathercam camera entities", len(cameras))
    if cameras:
        async_add_entities(cameras)


def _get_expected_preset_ids(cameras_config: list[dict]) -> set[str]:
    """
    Get set of expected preset IDs from camera configuration.

    Returns:
        Set of preset IDs that should exist based on config.

    """
    expected_preset_ids = set()
    for camera_config in cameras_config:
        selected_presets = camera_config.get("presets", [])
        expected_preset_ids.update(selected_presets)
    return expected_preset_ids


def _cleanup_removed_entities(
    hass: HomeAssistant, entry: ConfigEntry, expected_preset_ids: set[str]
) -> None:
    """Remove entities that are no longer in the configuration."""
    entity_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity_entry.domain != "camera":
            continue
        if not entity_entry.unique_id.startswith("digitraffic_"):
            continue

        preset_id = entity_entry.unique_id.replace("digitraffic_", "", 1)
        if preset_id not in expected_preset_ids:
            LOGGER.info(
                "Removing weathercam entity %s (preset %s no longer in config)",
                entity_entry.entity_id,
                preset_id,
            )
            entity_reg.async_remove(entity_entry.entity_id)


def _create_camera_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cameras_config: list[dict],
    weathercam_data: dict,
) -> list[DigitrafficWeathercamCamera]:
    """
    Create camera entities for configured presets.

    Returns:
        List of camera entities to be added.

    """
    cameras = []
    LOGGER.info(
        "Setting up weathercam cameras. Total configured cameras: %d",
        len(cameras_config),
    )

    for camera_config in cameras_config:
        camera_id = camera_config.get("camera_id", "")
        camera_name = camera_config.get("camera_name", camera_id)
        selected_presets = camera_config.get("presets", [])

        LOGGER.debug(
            "Processing camera %s (%s) with %d presets",
            camera_id,
            camera_name,
            len(selected_presets),
        )

        camera_data = weathercam_data.get(camera_id, {})
        all_presets = camera_data.get("presets", [])

        for preset in all_presets:
            preset_id = preset["id"]
            if preset_id in selected_presets:
                cameras.append(
                    DigitrafficWeathercamCamera(
                        hass,
                        entry,
                        {
                            "camera_id": camera_id,
                            "camera_name": camera_name,
                            "preset": preset,
                            "nearest_weather_station_id": camera_data.get(
                                "nearestWeatherStationId"
                            ),
                        },
                    )
                )

    return cameras


class DigitrafficWeathercamCamera(Camera):
    """Representation of a Digitraffic weathercam camera."""

    _attr_attribution = ATTRIBUTION
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        camera_data: dict[str, Any],
    ) -> None:
        """Initialize the camera."""
        super().__init__()

        self._hass = hass
        self._entry = entry
        self._camera_id = camera_data["camera_id"]
        self._camera_name = camera_data["camera_name"]
        self._preset = camera_data["preset"]
        self._preset_id = self._preset["id"]
        self._image_url = self._preset.get("imageUrl", "")
        self._nearest_weather_station_id = camera_data.get("nearest_weather_station_id")

        self._attr_unique_id = f"{entry.entry_id}_wc_{self._preset_id}"
        preset_name = self._preset.get("presentationName", self._preset_id)
        self._attr_name = f"{self._camera_name} - {preset_name}"
        self.entity_id = f"camera.digitraffic_wc_{self._preset_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Digitraffic Weathercams",
            manufacturer="Digitraffic",
            model="Weathercam",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._last_image = None
        self._last_updated = None
        # Set frame interval to 10 minutes (600 seconds) to cache images
        # This prevents excessive requests to Digitraffic servers
        self._attr_frame_interval = 600

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """
        Return image response.

        Args:
            width: Requested image width (unused).
            height: Requested image height (unused).

        Returns:
            Image bytes or None if fetch failed.

        """
        del width, height  # Unused parameters
        try:
            session = async_get_clientsession(self._hass)
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                "User-Agent": "Home Assistant Digitraffic Integration",
                "Accept": "image/jpeg,image/*",
                "Digitraffic-User": DIGITRAFFIC_USER,
            }
            async with session.get(
                self._image_url, timeout=timeout, headers=headers
            ) as response:
                if response.status == 200:  # noqa: PLR2004
                    self._last_image = await response.read()
                    self._last_updated = datetime.now(tz=UTC)
                    return self._last_image
                if response.status == 403:  # noqa: PLR2004
                    LOGGER.debug(
                        "Access denied for weathercam image %s "
                        "(camera may be offline or not publicly accessible)",
                        self._image_url,
                    )
                else:
                    LOGGER.warning(
                        "Failed to fetch image from %s: %s",
                        self._image_url,
                        response.status,
                    )
        except aiohttp.ClientError:
            LOGGER.exception("Error fetching weathercam image")
        except OSError:
            LOGGER.exception("Network error fetching weathercam image")

        return self._last_image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "camera_id": self._camera_id,
            "preset_id": self._preset_id,
            "image_url": self._image_url,
            "direction": self._preset.get("directionCode", ""),
            "presentation_name": self._preset.get("presentationName", ""),
            "nearest_weather_station_id": self._nearest_weather_station_id,
            "last_updated": self._last_updated.isoformat()
            if self._last_updated
            else None,
        }
