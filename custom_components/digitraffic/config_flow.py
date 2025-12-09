from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol
import logging

import hashlib

from .const import (
    DOMAIN,
    LOGGER,
    FINNISH_MUNICIPALITIES,
    ENTITY_TYPE_TRAFFIC_MESSAGES,
    ENTITY_TYPE_WEATHERCAM,
    SITUATION_TYPES,
    SITUATION_TYPE_LABELS,
)


class DigitrafficConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._entity_type = None
        self._weathercam_municipality = None
        self._weathercam_data = None
        self._weathercam_id = None
        self._weathercam_name = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step - show menu to choose entity type."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["traffic_messages", "weathercam"],
        )

    async def async_step_traffic_messages(self, user_input=None):
        """Configure traffic messages."""
        if user_input is not None:
            user_input["entity_type"] = ENTITY_TYPE_TRAFFIC_MESSAGES

            # Create a descriptive title based on situation types
            situation_types = user_input.get("situation_types", SITUATION_TYPES)
            if len(situation_types) == 1:
                title_suffix = SITUATION_TYPE_LABELS[situation_types[0]]
            else:
                title_suffix = "Multiple Situations"

            return self.async_create_entry(
                title=f"Traffic Messages - {title_suffix}",
                data=user_input,
            )

        situation_type_options = [
            {"value": st, "label": SITUATION_TYPE_LABELS[st]} for st in SITUATION_TYPES
        ]

        schema = vol.Schema(
            {
                vol.Optional("municipalities", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=FINNISH_MUNICIPALITIES,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    "situation_types", default=SITUATION_TYPES
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=situation_type_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    "include_raw_data", default=False
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="traffic_messages",
            data_schema=schema,
        )

    async def async_step_weathercam(self, user_input=None):
        """Configure weathercam - step 1: select municipality."""
        # Check if a weathercam entry already exists
        existing_entries = [
            entry
            for entry in self._async_current_entries()
            if entry.data.get("entity_type") == ENTITY_TYPE_WEATHERCAM
        ]

        if existing_entries:
            # If an entry already exists, redirect to reconfigure it
            return self.async_abort(
                reason="single_instance_allowed",
                description_placeholders={"entity_type": "Weathercams"},
            )

        if user_input is not None:
            # Store selected municipality and move to camera selection
            self._weathercam_municipality = user_input["municipality"]
            return await self.async_step_weathercam_select()

        # Fetch weathercam data if not already cached
        if self._weathercam_data is None:
            self._weathercam_data = await self._async_fetch_weathercam_data()

        # Get only municipalities that have weathercams
        available_municipalities = self._get_municipalities_with_cameras(
            self._weathercam_data
        )

        schema = vol.Schema(
            {
                vol.Required("municipality"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(available_municipalities),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="weathercam",
            data_schema=schema,
        )

    async def async_step_weathercam_select(self, user_input=None):
        """Configure weathercam - step 2: select specific camera."""
        if user_input is not None:
            # Store selected camera and move to preset selection
            self._weathercam_id = user_input["weathercam_id"]
            camera_data = self._weathercam_data.get(self._weathercam_id, {})
            self._weathercam_name = camera_data.get("names", {}).get(
                "fi", self._weathercam_id
            )
            return await self.async_step_weathercam_presets()

        # Fetch weathercam data if not already cached
        if self._weathercam_data is None:
            self._weathercam_data = await self._async_fetch_weathercam_data()

        # Filter cameras by municipality
        available_cameras = self._filter_cameras_by_municipality(
            self._weathercam_data, self._weathercam_municipality
        )

        if not available_cameras:
            return self.async_abort(
                reason="no_cameras_found",
                description_placeholders={
                    "municipality": self._weathercam_municipality
                },
            )

        # Create options for dropdown
        camera_options = [
            selector.SelectOptionDict(
                value=cam["id"],
                label=cam["name"],
            )
            for cam in available_cameras
        ]

        schema = vol.Schema(
            {
                vol.Required("weathercam_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=camera_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="weathercam_select",
            data_schema=schema,
            description_placeholders={"municipality": self._weathercam_municipality},
        )

    async def async_step_weathercam_presets(self, user_input=None):
        """Configure weathercam - step 3: select camera presets (directions)."""
        if user_input is not None:
            # Create entry with selected weathercam and presets in a list
            selected_presets = user_input["presets"]

            # Store as a list of cameras for future extensibility
            cameras = [
                {
                    "camera_id": self._weathercam_id,
                    "camera_name": self._weathercam_name,
                    "municipality": self._weathercam_municipality,
                    "presets": selected_presets,
                }
            ]

            return self.async_create_entry(
                title="Weathercams",
                data={
                    "entity_type": ENTITY_TYPE_WEATHERCAM,
                    "cameras": cameras,
                },
            )

        # Get presets for the selected camera
        camera_data = self._weathercam_data.get(self._weathercam_id, {})
        presets = camera_data.get("presets", [])

        if not presets:
            return self.async_abort(
                reason="no_presets_found",
                description_placeholders={"camera_name": self._weathercam_name},
            )

        # Create options for preset selection (multi-select)
        preset_options = [
            selector.SelectOptionDict(
                value=preset["id"],
                label=preset.get("presentationName", preset["id"]),
            )
            for preset in presets
        ]

        schema = vol.Schema(
            {
                vol.Required("presets"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=preset_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="weathercam_presets",
            data_schema=schema,
            description_placeholders={"camera_name": self._weathercam_name},
        )

    async def _async_fetch_weathercam_data(self):
        """Load weathercam data from static JSON file."""
        import json
        from pathlib import Path

        # Load from static data file in data/ folder
        data_file = Path(__file__).parent / "data" / "weathercam_data.json"

        if not data_file.exists():
            return {}

        def _load_data():
            """Load data in executor."""
            with data_file.open(encoding="utf-8") as f:
                return json.load(f)

        return await self.hass.async_add_executor_job(_load_data)

    def _get_municipalities_with_cameras(self, cameras):
        """Get a list of unique municipalities that have weathercams."""
        municipalities = set()

        for camera_data in cameras.values():
            municipality = camera_data.get("municipality")
            if municipality:
                municipalities.add(municipality)

        return list(municipalities)

    def _filter_cameras_by_municipality(self, cameras, municipality):
        """Filter cameras by municipality from the static data."""
        filtered = []

        for camera_id, camera_data in cameras.items():
            if camera_data.get("municipality") == municipality:
                # Get display name from presets if available
                display_name = camera_data.get("name", camera_id)
                if camera_data.get("names", {}).get("fi"):
                    display_name = camera_data["names"]["fi"]

                filtered.append(
                    {
                        "id": camera_id,
                        "name": display_name,
                    }
                )

        return filtered

    async def async_step_reconfigure(self, user_input=None):
        """Support reconfiguring an existing config entry from the Integrations UI.

        Updates the existing entry instead of creating a new one,
        which allows entities to be updated rather than recreated.
        """
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        entity_type = entry.data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

        # Route to appropriate reconfiguration based on entity type
        if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
            return await self._async_reconfigure_traffic_messages(entry, user_input)
        elif entity_type == ENTITY_TYPE_WEATHERCAM:
            return await self._async_reconfigure_weathercam(entry, user_input)

        return self.async_abort(reason="unknown_entity_type")

    async def _async_reconfigure_traffic_messages(self, entry, user_input=None):
        """Reconfigure traffic messages entry."""
        if user_input is not None:
            user_input["entity_type"] = ENTITY_TYPE_TRAFFIC_MESSAGES
            self.hass.config_entries.async_update_entry(
                entry,
                title="Traffic Messages",
                data=user_input,
            )
            return self.async_abort(reason="reconfigure_successful")

        # Pre-populate form with current values
        current_municipalities = entry.data.get("municipalities", [])
        current_situation_types = entry.data.get("situation_types", SITUATION_TYPES)
        current_include_raw = entry.data.get("include_raw_data", False)

        situation_type_options = [
            {"value": st, "label": SITUATION_TYPE_LABELS[st]} for st in SITUATION_TYPES
        ]

        schema = vol.Schema(
            {
                vol.Optional(
                    "municipalities", default=current_municipalities
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=FINNISH_MUNICIPALITIES,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    "situation_types", default=current_situation_types
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=situation_type_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    "include_raw_data", default=current_include_raw
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
        )

    async def _async_reconfigure_weathercam(self, entry, user_input=None):
        """Reconfigure weathercam entry - allow adding new cameras."""
        # Reset instance variables for new camera selection
        self._weathercam_municipality = None
        self._weathercam_data = None
        self._weathercam_id = None
        self._weathercam_name = None

        # Start municipality selection
        return await self.async_step_reconfigure_weathercam_municipality()

    async def async_step_reconfigure_weathercam_municipality(self, user_input=None):
        """Step 1: Select municipality for new camera."""
        if user_input is not None:
            self._weathercam_municipality = user_input["municipality"]
            return await self.async_step_reconfigure_weathercam_camera()

        # Fetch weathercam data if not already cached
        if self._weathercam_data is None:
            self._weathercam_data = await self._async_fetch_weathercam_data()

        # Get only municipalities that have weathercams
        available_municipalities = self._get_municipalities_with_cameras(
            self._weathercam_data
        )

        schema = vol.Schema(
            {
                vol.Required("municipality"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(available_municipalities),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_weathercam_municipality",
            data_schema=schema,
            description_placeholders={
                "description": "Select municipality to add a new weathercam"
            },
        )

    async def async_step_reconfigure_weathercam_camera(self, user_input=None):
        """Step 2: Select camera in the chosen municipality."""
        if user_input is not None:
            self._weathercam_id = user_input["weathercam_id"]

            # Fetch data if not cached
            if self._weathercam_data is None:
                self._weathercam_data = await self._async_fetch_weathercam_data()

            camera_data = self._weathercam_data.get(self._weathercam_id, {})
            self._weathercam_name = camera_data.get("names", {}).get(
                "fi", self._weathercam_id
            )
            return await self.async_step_reconfigure_weathercam_presets()

        # Fetch weathercam data if not cached
        if self._weathercam_data is None:
            self._weathercam_data = await self._async_fetch_weathercam_data()

        # Filter cameras by municipality
        available_cameras = self._filter_cameras_by_municipality(
            self._weathercam_data, self._weathercam_municipality
        )

        if not available_cameras:
            return self.async_abort(
                reason="no_cameras_found",
                description_placeholders={
                    "municipality": self._weathercam_municipality
                },
            )

        # Create options for dropdown
        camera_options = [
            selector.SelectOptionDict(
                value=cam["id"],
                label=cam["name"],
            )
            for cam in available_cameras
        ]

        schema = vol.Schema(
            {
                vol.Required("weathercam_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=camera_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_weathercam_camera",
            data_schema=schema,
            description_placeholders={"municipality": self._weathercam_municipality},
        )

    async def async_step_reconfigure_weathercam_presets(self, user_input=None):
        """Step 3: Select presets for the chosen camera."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Add the new camera to the existing cameras list
            new_camera = {
                "camera_id": self._weathercam_id,
                "camera_name": self._weathercam_name,
                "municipality": self._weathercam_municipality,
                "presets": user_input["presets"],
            }

            # Create a NEW list (copy) to ensure Home Assistant detects the change
            existing_cameras = list(entry.data.get("cameras", []))
            existing_cameras.append(new_camera)

            LOGGER.info(
                "Adding camera %s to weathercam entry. Total cameras: %d",
                self._weathercam_id,
                len(existing_cameras),
            )

            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    "entity_type": ENTITY_TYPE_WEATHERCAM,
                    "cameras": existing_cameras,
                },
            )

            # Reload the entry to add the new entities
            await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_abort(reason="reconfigure_successful")

        # Get presets for the selected camera
        camera_data = self._weathercam_data.get(self._weathercam_id, {})
        presets = camera_data.get("presets", [])

        if not presets:
            return self.async_abort(
                reason="no_presets_found",
                description_placeholders={"camera_name": self._weathercam_name},
            )

        # Create options for preset selection (multi-select)
        preset_options = [
            selector.SelectOptionDict(
                value=preset["id"],
                label=preset.get("presentationName", preset["id"]),
            )
            for preset in presets
        ]

        schema = vol.Schema(
            {
                vol.Required("presets"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=preset_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_weathercam_presets",
            data_schema=schema,
            description_placeholders={"camera_name": self._weathercam_name},
        )


class DigitrafficOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the integration (reconfiguration).

    This options flow mirrors the initial config flow and allows the user
    to change `municipalities`. Options are saved to `entry.options`.
    """

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Prefer existing options, fall back to initial data
        current = self.config_entry.options.get(
            "municipalities", self.config_entry.data.get("municipalities", [])
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    "municipalities", default=current
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=FINNISH_MUNICIPALITIES,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


def async_get_options_flow(config_entry):
    """Return options flow handler for this config entry.

    Must be a regular function (not coroutine) that returns an
    OptionsFlow handler instance so Home Assistant can expose the
    "Options" button for existing entries.
    """
    return DigitrafficOptionsFlow(config_entry)
