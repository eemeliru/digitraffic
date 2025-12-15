"""Sensor platform for Digitraffic traffic messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    DOMAIN,
    ENTITY_TYPE_TRAFFIC_MESSAGES,
    ENTITY_TYPE_WEATHERCAM,
    LOGGER,
    SITUATION_TYPE_LABELS,
)

# Constants for coordinate parsing
_COORDINATE_PAIR_LENGTH = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Digitraffic sensors and handle dynamic entity management."""
    data = hass.data[DOMAIN][entry.entry_id]
    entity_type = data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

    # Route to appropriate sensor setup based on entity type
    if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
        _async_setup_traffic_message_sensors(hass, entry, async_add_entities, data)
    elif entity_type == ENTITY_TYPE_WEATHERCAM:
        await _async_setup_weathercam_sensors(hass, entry, async_add_entities, data)


def _async_setup_traffic_message_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    data: dict[str, Any],
) -> None:
    """Set up traffic message sensors - one sensor per message."""
    coordinator = data["coordinator"]

    # Track currently active message sensors by situation_id
    data["active_message_sensors"] = {}

    def _async_add_remove_entities() -> None:
        """Dynamically add/remove sensors based on active traffic messages."""
        entity_reg = er.async_get(hass)

        # Get current messages from coordinator
        messages = coordinator.data or []

        # Extract situation IDs from current messages
        current_situation_ids = {
            msg.get("properties", {}).get("situationId")
            for msg in messages
            if msg.get("properties", {}).get("situationId")
        }

        LOGGER.debug(
            "Traffic message sync: %d active messages from API",
            len(current_situation_ids),
        )

        # Get existing message sensor unique IDs for this entry
        existing_sensors = {}
        entry_prefix = f"{entry.entry_id}_tm_"
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            # Check if this is a traffic message sensor
            if entity_entry.domain == "sensor" and entity_entry.unique_id.startswith(
                entry_prefix
            ):
                # Extract situation_id from unique_id
                # (format: {entry_id}_tm_{situation_id})
                situation_id = entity_entry.unique_id.replace(entry_prefix, "", 1)
                existing_sensors[situation_id] = entity_entry.entity_id

        LOGGER.debug(
            "Traffic message sync: %d existing sensors in registry",
            len(existing_sensors),
        )

        # Remove sensors for messages that are no longer active
        removed_ids = set(existing_sensors.keys()) - current_situation_ids
        for situation_id in removed_ids:
            entity_id = existing_sensors[situation_id]
            LOGGER.debug(
                "Removing inactive traffic message sensor: %s (situation_id: %s)",
                entity_id,
                situation_id,
            )
            try:
                # Remove from entity registry - this will delete the entity
                entity_reg.async_remove(entity_id)
                LOGGER.debug("Successfully removed entity %s from registry", entity_id)
            except (KeyError, ValueError) as err:
                LOGGER.warning("Failed to remove entity %s: %s", entity_id, err)

            # Clean up from active sensors dict
            if situation_id in data["active_message_sensors"]:
                del data["active_message_sensors"][situation_id]

        # Add/restore sensors for all current messages
        new_entities = []

        for msg in messages:
            situation_id = msg.get("properties", {}).get("situationId")
            if not situation_id:
                continue

            # Check if sensor already exists in our active tracking
            if situation_id in data["active_message_sensors"]:
                # Already tracked and added, skip
                continue

            # Check if it exists in the registry but not yet added to platform
            if situation_id in existing_sensors:
                # Entity exists in registry, need to restore it to platform
                LOGGER.debug(
                    "Restoring existing sensor for situation_id: %s", situation_id
                )

            # Create/restore the sensor entity
            sensor = DigitrafficTrafficMessageSensor(
                coordinator, entry, msg, situation_id
            )
            new_entities.append(sensor)
            data["active_message_sensors"][situation_id] = sensor

        if new_entities:
            async_add_entities(new_entities)

    # Store the callback for future use during reconfiguration
    data["add_entities_callback"] = _async_add_remove_entities

    # Initial entity setup
    _async_add_remove_entities()

    # Add coordinator listener to clean up entities on each update
    coordinator.async_add_listener(_async_add_remove_entities)


async def _async_setup_weathercam_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    data: dict[str, Any],
) -> None:
    """
    Set up weathercam sensors.

    Weathercam entities are handled by the camera platform.
    This function exists for routing but doesn't create sensor entities.
    """


# -----------------------
# ✅ PER-MESSAGE SENSOR
# -----------------------


class DigitrafficTrafficMessageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for individual traffic message."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: Any,
        entry: ConfigEntry,
        message_data: dict[str, Any],
        situation_id: str,
    ) -> None:
        """Initialize the traffic message sensor."""
        super().__init__(coordinator)

        self._situation_id = situation_id
        self._entry_id = entry.entry_id

        # Generate unique ID based on entry and situation ID
        # This ensures same message in different services gets different unique_id
        self._attr_unique_id = f"{entry.entry_id}_tm_{situation_id}"

        # Extract initial message details
        properties = message_data.get("properties", {})
        situation_type = properties.get("situationType", "UNKNOWN")

        # Set icon based on situation type
        icon_map = {
            "TRAFFIC_ANNOUNCEMENT": "mdi:alert-circle",
            "ROAD_WORK": "mdi:road-variant",
            "WEIGHT_RESTRICTION": "mdi:weight",
            "EXEMPTED_TRANSPORT": "mdi:truck-cargo-container",
        }
        self._attr_icon = icon_map.get(situation_type, "mdi:traffic-cone")
        self.entity_id = f"sensor.digitraffic_tm_{situation_id}"

        # Set device info to group all messages from this service together
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fintraffic",
            model="Digitraffic",
            entry_type=None,
        )

    @property
    def _message_data(self) -> dict[str, Any] | None:
        """Get current message data from coordinator."""
        messages = self.coordinator.data or []
        for msg in messages:
            if msg.get("properties", {}).get("situationId") == self._situation_id:
                return msg
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor using the message title."""
        msg = self._message_data
        if msg:
            announcements = msg.get("properties", {}).get("announcements", [])
            if announcements and announcements[0].get("title"):
                return announcements[0]["title"]
        # Fallback to situation ID if no title available
        return f"Traffic Message {self._situation_id}"

    @property
    def native_value(self) -> str:
        """Return state - 'active' if message exists, 'inactive' otherwise."""
        return "active" if self._message_data else "inactive"

    @property
    def available(self) -> bool:
        """Return True if message still exists in coordinator data."""
        return self._message_data is not None

    @staticmethod
    def _extract_coordinates(
        geometry: dict[str, Any] | None,
    ) -> tuple[float | None, float | None]:
        """
        Extract latitude and longitude from geometry.

        Returns:
            Tuple of (latitude, longitude) or (None, None) if not available.

        """
        if not geometry:
            return None, None
        coordinates = geometry.get("coordinates", [])
        if not coordinates or len(coordinates) == 0:
            return None, None

        first_coord = coordinates[0]
        # If it's a LineString, first_coord is [lon, lat]
        # If it's a Point, coordinates is [lon, lat] directly
        if (
            isinstance(first_coord, list)
            and len(first_coord) >= _COORDINATE_PAIR_LENGTH
        ):
            return first_coord[1], first_coord[0]  # Return lat, lon
        if (
            isinstance(coordinates[0], (int, float))
            and len(coordinates) >= _COORDINATE_PAIR_LENGTH
        ):
            # Point geometry: coordinates = [lon, lat]
            return coordinates[1], coordinates[0]  # Return lat, lon
        return None, None

    @staticmethod
    def _extract_description(announcements: list[dict[str, Any]]) -> str | None:
        """
        Extract description from announcements.

        Returns:
            Combined description string or None if not available.

        """
        description_parts = []
        if announcements:
            # Add comment/description
            description_parts.extend(
                ann["comment"] for ann in announcements if ann.get("comment")
            )

            # Add features
            features = []
            for ann in announcements:
                features.extend(
                    feat["name"] for feat in ann.get("features", []) if feat.get("name")
                )
            if features:
                description_parts.append(", ".join(features))

        return " | ".join(description_parts) if description_parts else None

    @staticmethod
    def _extract_location_info(
        announcements: list[dict[str, Any]],
    ) -> tuple[list[str], str | None, str | None]:
        """
        Extract location details from announcements.

        Returns:
            Tuple of (municipalities, road, direction).

        """
        municipalities = []
        road = None
        direction = None

        if announcements and announcements[0].get("locationDetails"):
            location = announcements[0]["locationDetails"].get(
                "roadAddressLocation", {}
            )
            primary_muni = location.get("primaryPoint", {}).get("municipality")
            secondary_muni = location.get("secondaryPoint", {}).get("municipality")

            # Combine municipalities
            if primary_muni:
                municipalities.append(primary_muni)
            if secondary_muni and secondary_muni != primary_muni:
                municipalities.append(secondary_muni)

            road = location.get("primaryPoint", {}).get("roadNumber")
            direction = location.get("direction")

        return municipalities, road, direction

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return message details as attributes."""
        msg = self._message_data
        if not msg:
            return {}

        properties = msg.get("properties", {})
        geometry = msg.get("geometry", {})
        announcements = properties.get("announcements", [])

        # Extract title
        title = announcements[0].get("title") if announcements else None

        # Extract description
        description = self._extract_description(announcements)

        # Extract coordinates
        latitude, longitude = self._extract_coordinates(geometry)

        # Extract location details
        municipalities, road, direction = self._extract_location_info(announcements)

        # Build GeoJSON with minimal required fields
        geometry_type = geometry.get("type", "LineString") if geometry else "LineString"
        geometry_coords = geometry.get("coordinates", []) if geometry else []

        geojson = {
            "type": "Feature",
            "geometry": {
                "type": geometry_type,
                "coordinates": geometry_coords,
            },
            "properties": {
                "title": title,
                "situation_id": self._situation_id,
                "situation_type": properties.get("situationType"),
            },
        }

        # Build attributes in requested order
        return {
            "situation_id": self._situation_id,
            "title": title,
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
            "situation_type_label": SITUATION_TYPE_LABELS.get(
                properties.get("situationType", ""), "Unknown"
            ),
            "release_time": properties.get("releaseTime"),
            "updated_time": properties.get("dataUpdatedTime"),
            "municipalities": ", ".join(municipalities) if municipalities else None,
            "road": road,
            "direction": direction,
            "geojson": geojson,
        }
