from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    ENTITY_TYPE_TRAFFIC_MESSAGES,
    ENTITY_TYPE_WEATHERCAM,
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
    """Set up traffic message sensors - one sensor per message."""
    coordinator = data["coordinator"]

    # Track currently active message sensors by situation_id
    data["active_message_sensors"] = {}

    async def _async_add_remove_entities():
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

        # Get existing message sensor unique IDs for this entry
        existing_sensors = {}
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            if entity_entry.domain == "sensor":
                # Extract situation_id from unique_id pattern
                if "_msg_" in entity_entry.unique_id:
                    parts = entity_entry.unique_id.split("_msg_")
                    if len(parts) == 2:
                        situation_id = parts[1]
                        existing_sensors[situation_id] = entity_entry.entity_id

        # Remove sensors for messages that are no longer active
        removed_ids = set(existing_sensors.keys()) - current_situation_ids
        for situation_id in removed_ids:
            entity_id = existing_sensors[situation_id]
            entity_reg.async_remove(entity_id)
            if situation_id in data["active_message_sensors"]:
                del data["active_message_sensors"][situation_id]

        # Add sensors for new messages
        new_entities = []
        new_ids = current_situation_ids - set(existing_sensors.keys())

        for msg in messages:
            situation_id = msg.get("properties", {}).get("situationId")
            if situation_id in new_ids:
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
    await _async_add_remove_entities()


async def _async_setup_weathercam_sensors(hass, entry, async_add_entities, data):
    """Set up weathercam sensors (placeholder)."""
    # TODO: Implement weathercam sensor setup


# -----------------------
# ✅ PER-MESSAGE SENSOR
# -----------------------


class DigitrafficTrafficMessageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for individual traffic message."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, entry, message_data, situation_id):
        """Initialize the traffic message sensor."""
        super().__init__(coordinator)

        self._situation_id = situation_id
        self._entry_id = entry.entry_id

        # Generate unique ID based on situation ID
        self._attr_unique_id = f"digitraffic_{situation_id}"

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

        # Set device info to group all messages from this service together
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fintraffic",
            model="Digitraffic",
            entry_type=None,
        )

    @property
    def _message_data(self):
        """Get current message data from coordinator."""
        messages = self.coordinator.data or []
        for msg in messages:
            if msg.get("properties", {}).get("situationId") == self._situation_id:
                return msg
        return None

    @property
    def name(self):
        """Return the name of the sensor using the message title."""
        msg = self._message_data
        if msg:
            announcements = msg.get("properties", {}).get("announcements", [])
            if announcements and announcements[0].get("title"):
                return announcements[0]["title"]
        # Fallback to situation ID if no title available
        return f"Traffic Message {self._situation_id}"

    @property
    def native_value(self):
        """Return state - 'active' if message exists, 'inactive' otherwise."""
        return "active" if self._message_data else "inactive"

    @property
    def available(self):
        """Return True if message still exists in coordinator data."""
        return self._message_data is not None

    @property
    def extra_state_attributes(self):
        """Return message details as attributes."""
        msg = self._message_data
        if not msg:
            return {}

        properties = msg.get("properties", {})
        geometry = msg.get("geometry", {})
        announcements = properties.get("announcements", [])

        # Extract title
        title = announcements[0].get("title") if announcements else None

        # Extract and combine description with features
        description_parts = []
        if announcements:
            # Add comment/description
            for ann in announcements:
                if ann.get("comment"):
                    description_parts.append(ann["comment"])

            # Add features
            features = []
            for ann in announcements:
                for feat in ann.get("features", []):
                    if feat.get("name"):
                        features.append(feat["name"])
            if features:
                description_parts.append(", ".join(features))

        description = " | ".join(description_parts) if description_parts else None

        # Extract location details
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

        # Build GeoJSON with minimal required fields
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": geometry.get("type", "LineString"),
                "coordinates": geometry.get("coordinates", []),
            },
            "properties": {
                "title": title,
                "situation_id": self._situation_id,
                "situation_type": properties.get("situationType"),
            },
        }

        # Extract latitude and longitude from first coordinate
        coordinates = geometry.get("coordinates", [])
        latitude = None
        longitude = None
        if coordinates and len(coordinates) > 0:
            # Handle different geometry types
            first_coord = coordinates[0]
            # If it's a LineString, first_coord is [lon, lat]
            # If it's a Point, coordinates is [lon, lat] directly
            if isinstance(first_coord, list) and len(first_coord) >= 2:
                longitude = first_coord[0]
                latitude = first_coord[1]
            elif isinstance(coordinates[0], (int, float)) and len(coordinates) >= 2:
                # Point geometry: coordinates = [lon, lat]
                longitude = coordinates[0]
                latitude = coordinates[1]

        # Build attributes in requested order
        attributes = {
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

        return attributes


# -----------------------
# ✅ LEGACY SENSOR (kept for backward compatibility during migration)
# -----------------------


class DigitrafficAllSensor(CoordinatorEntity, SensorEntity):
    """Legacy sensor showing all messages (for backward compatibility)."""

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


class DigitrafficMunicipalitySensor(CoordinatorEntity, SensorEntity):
    """Legacy municipality sensor (for backward compatibility)."""

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
