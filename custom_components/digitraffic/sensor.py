import hashlib

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN,
    ENTITY_TYPE_TRAFFIC_MESSAGES,
    ENTITY_TYPE_WEATHERCAM,
    SITUATION_TYPES,
    SITUATION_TYPE_LABELS,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Digitraffic sensors and handle dynamic entity management."""
    data = hass.data[DOMAIN][entry.entry_id]
    entity_type = data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

    # Route to appropriate sensor setup based on entity type
    if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
        await _async_setup_traffic_message_sensors(
            hass, entry, async_add_entities, data
        )
    elif entity_type == ENTITY_TYPE_WEATHERCAM:
        await _async_setup_weathercam_sensors(hass, entry, async_add_entities, data)


async def _async_setup_traffic_message_sensors(hass, entry, async_add_entities, data):
    """Set up traffic message sensors."""
    coordinator = data["coordinator"]

    async def _async_add_remove_entities():
        """Add or remove entities based on current municipality selection."""
        municipalities = data["municipalities"]
        include_raw_data = data.get("include_raw_data", False)
        entities = []
        entity_reg = er.async_get(hass)

        # ✅ 1. Optional "Raw" sensor (only if include_raw_data is True)
        raw_sensor_unique_id = f"{entry.entry_id}_raw"
        existing_raw = entity_reg.async_get_entity_id(
            "sensor", DOMAIN, raw_sensor_unique_id
        )

        if include_raw_data:
            # Create raw sensor if it doesn't exist
            if not existing_raw:
                entities.append(DigitrafficAllSensor(coordinator, entry))
        else:
            # Remove raw sensor if it exists but shouldn't
            if existing_raw:
                entity_reg.async_remove(existing_raw)

        # ✅ 2. Manage municipality sensors dynamically
        # Get situation types filter
        situation_types = data.get("situation_types", SITUATION_TYPES)

        # Generate a short hash of situation types for unique ID
        # This allows multiple sensors per municipality with different filters
        situation_types_str = "_".join(sorted(situation_types))
        types_hash = hashlib.md5(situation_types_str.encode()).hexdigest()[:8]

        # Track which municipalities should exist
        desired_unique_ids = {
            f"{entry.entry_id}_{municipality.lower()}_{types_hash}"
            for municipality in municipalities
        }

        # Remove sensors for municipalities no longer selected
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            if (
                entity_entry.domain == "sensor"
                and entity_entry.unique_id != raw_sensor_unique_id
                and entity_entry.unique_id not in desired_unique_ids
            ):
                entity_reg.async_remove(entity_entry.entity_id)

        # Add sensors for new municipalities
        # Count existing sensors per municipality to generate numbered suffixes
        municipality_counts = {}
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            if (
                entity_entry.domain == "sensor"
                and entity_entry.unique_id != raw_sensor_unique_id
            ):
                # Extract municipality from unique_id pattern: {entry_id}_{municipality}_{hash}
                parts = entity_entry.unique_id.split("_")
                if len(parts) >= 3:
                    muni = parts[1]  # municipality part
                    municipality_counts[muni] = municipality_counts.get(muni, 0) + 1

        for municipality in municipalities:
            unique_id = f"{entry.entry_id}_{municipality.lower()}_{types_hash}"
            existing_entity = entity_reg.async_get_entity_id(
                "sensor", DOMAIN, unique_id
            )

            if not existing_entity:
                # Determine suffix number for this municipality
                muni_lower = municipality.lower()
                count = municipality_counts.get(muni_lower, 0)
                municipality_counts[muni_lower] = count + 1
                suffix_number = count + 1  # Start from 1 for first, 2 for second, etc.

                entities.append(
                    DigitrafficMunicipalitySensor(
                        coordinator,
                        entry,
                        municipality,
                        situation_types,
                        types_hash,
                        suffix_number,
                    )
                )

        if entities:
            async_add_entities(entities)

    # Store the callback for future use during reconfiguration
    data["add_entities_callback"] = _async_add_remove_entities

    # Initial entity setup
    await _async_add_remove_entities()


async def _async_setup_weathercam_sensors(hass, entry, async_add_entities, data):
    """Set up weathercam sensors (placeholder)."""
    # TODO: Implement weathercam sensor setup
    pass


# -----------------------
# ✅ GLOBAL SENSOR
# -----------------------


class DigitrafficAllSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)

        self._attr_name = "Digitraffic Traffic Messages Raw"
        self._attr_unique_id = f"{entry.entry_id}_raw"

    @property
    def raw_data(self):
        """Return raw data from coordinator."""
        return self.coordinator.data or []

    @property
    def native_value(self):
        return len(self.raw_data)

    @property
    def extra_state_attributes(self):
        return {
            "scope": "all",
            "raw_data": self.raw_data,
        }


# -----------------------
# ✅ MUNICIPALITY SENSOR
# -----------------------


class DigitrafficMunicipalitySensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        entry,
        municipality,
        situation_types=None,
        types_hash=None,
        suffix_number=1,
    ):
        super().__init__(coordinator)

        self.municipality = municipality
        self._entry_id = entry.entry_id
        self._hass = coordinator.hass
        self._initial_situation_types = situation_types or SITUATION_TYPES

        # Generate hash if not provided (for backward compatibility)
        if types_hash is None:
            situation_types_str = "_".join(sorted(self._initial_situation_types))
            types_hash = hashlib.md5(situation_types_str.encode()).hexdigest()[:8]

        # Create simple name with numbered suffix if multiple sensors for same municipality
        if suffix_number == 1:
            self._attr_name = f"Digitraffic Traffic Messages {municipality}"
        else:
            self._attr_name = (
                f"Digitraffic Traffic Messages {municipality} {suffix_number}"
            )

        self._attr_unique_id = f"{entry.entry_id}_{municipality.lower()}_{types_hash}"

        # Track seen situation IDs to identify new messages
        self._seen_situation_ids: set[str] = set()

    @property
    def situation_types(self):
        """Get current situation types from hass.data (allows live updates)."""
        if self._hass and DOMAIN in self._hass.data:
            entry_data = self._hass.data[DOMAIN].get(self._entry_id, {})
            types = entry_data.get("situation_types")
            if types is not None:
                return types
        # Fallback to initial value
        return self._initial_situation_types

    def _filtered(self):
        """Filter announcements from coordinator data for this municipality and situation types."""
        raw_data = self.coordinator.data or []
        if not raw_data:
            return []

        out = []

        for msg in raw_data:
            # Check situation type filter
            properties = msg.get("properties", {})
            situation_type = properties.get("situationType")

            if situation_type not in self.situation_types:
                continue

            announcements = properties.get("announcements", [])

            for ann in announcements:
                location_details = ann.get("locationDetails", {})
                road_location = location_details.get("roadAddressLocation", {})

                # Check both primaryPoint and secondaryPoint
                primary_point = road_location.get("primaryPoint", {})
                secondary_point = road_location.get("secondaryPoint", {})

                if (
                    primary_point.get("municipality") == self.municipality
                    or secondary_point.get("municipality") == self.municipality
                ):
                    out.append(msg)
                    break

        return out

    @property
    def native_value(self):
        return len(self._filtered())

    def _extract_message_data(self, feature):
        """Extract structured data from a single message feature."""
        message_data = {}

        # Extract situationId and situationType
        properties = feature.get("properties", {})
        situation_id = properties.get("situationId")
        situation_type = properties.get("situationType")

        if situation_id:
            message_data["situation_id"] = situation_id
            # Mark if this is a new message (not seen before)
            message_data["is_new"] = situation_id not in self._seen_situation_ids

        if situation_type:
            message_data["situation_type"] = situation_type
            message_data["situation_type_label"] = SITUATION_TYPE_LABELS.get(
                situation_type, situation_type
            )

        # Extract coordinates
        geometry = feature.get("geometry", {})
        if geometry.get("coordinates"):
            message_data["coordinates"] = geometry["coordinates"]

        # Extract timestamps
        if properties.get("releaseTime"):
            message_data["release_time"] = properties["releaseTime"]
        if properties.get("dataUpdatedTime"):
            message_data["data_updated_time"] = properties["dataUpdatedTime"]

        # Extract announcement details
        announcements = properties.get("announcements", [])
        message_data["title"] = [
            ann["title"] for ann in announcements if ann.get("title")
        ]
        message_data["description"] = [
            ann["comment"] for ann in announcements if ann.get("comment")
        ]
        message_data["direction"] = [
            ann.get("locationDetails", {})
            .get("roadAddressLocation", {})
            .get("direction")
            for ann in announcements
            if ann.get("locationDetails", {})
            .get("roadAddressLocation", {})
            .get("direction")
        ]
        message_data["name"] = [
            feat["name"]
            for ann in announcements
            for feat in ann.get("features", [])
            if feat.get("name")
        ]

        return message_data

    @property
    def extra_state_attributes(self):
        """Return all messages in a single raw_data attribute."""
        filtered_data = self._filtered()

        # Extract message data
        messages = [self._extract_message_data(feature) for feature in filtered_data]

        # Update seen situation IDs for next comparison
        current_situation_ids = {
            msg["situation_id"] for msg in messages if "situation_id" in msg
        }
        self._seen_situation_ids.update(current_situation_ids)

        return {
            "municipality": self.municipality,
            "situation_types": [
                SITUATION_TYPE_LABELS.get(st, st) for st in self.situation_types
            ],
            "message_count": len(messages),
            "last_updated": self.coordinator.last_update_time,
            "raw_data": messages,
        }
