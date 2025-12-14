"""Config flow for Digitraffic integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    ENTITY_TYPE_TRAFFIC_MESSAGES,
    ENTITY_TYPE_WEATHERCAM,
    FINNISH_MUNICIPALITIES,
    LOGGER,
    SITUATION_TYPE_LABELS,
    SITUATION_TYPES,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class DigitrafficConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Digitraffic."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DigitrafficOptionsFlow:
        """
        Get the options flow for this handler.

        Returns:
            DigitrafficOptionsFlow instance.

        """
        return DigitrafficOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._entity_type = None
        self._traffic_config = None
        self._existing_service_name = None
        self._weathercam_municipality = None
        self._weathercam_data = None
        self._weathercam_id = None
        self._weathercam_name = None

    async def async_step_user(
        self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle the initial step - show menu to choose entity type.

        Returns:
            Flow result with menu options.

        """
        return self.async_show_menu(
            step_id="user",
            menu_options=["traffic_messages", "weathercam"],
        )

    async def async_step_traffic_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Configure traffic messages service - step 1: select filters.

        Returns:
            Flow result with form or next step.

        """
        errors = {}

        if user_input is not None:
            # Check for duplicate configuration
            municipalities = user_input.get("municipalities", [])
            situation_types = user_input.get("situation_types", SITUATION_TYPES)

            # Sort for consistent comparison
            sorted_municipalities = sorted(municipalities)
            sorted_situation_types = sorted(situation_types)

            # Check existing entries
            for entry in self._async_current_entries():
                if entry.data.get("entity_type") == ENTITY_TYPE_TRAFFIC_MESSAGES:
                    # Get existing configuration
                    existing_municipalities = sorted(
                        entry.options.get(
                            "municipalities", entry.data.get("municipalities", [])
                        )
                    )
                    existing_situation_types = sorted(
                        entry.options.get(
                            "situation_types",
                            entry.data.get("situation_types", SITUATION_TYPES),
                        )
                    )

                    # Check if configuration matches
                    if (
                        sorted_municipalities == existing_municipalities
                        and sorted_situation_types == existing_situation_types
                    ):
                        errors["base"] = "duplicate_config"
                        # Store the existing service name for error message
                        self._existing_service_name = entry.title
                        break

            # If no duplicate, proceed to naming step
            if not errors:
                self._traffic_config = user_input
                return await self.async_step_traffic_messages_name()

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
            }
        )

        description_placeholders = {
            "info": (
                "Each service monitors selected municipalities and creates "
                "one sensor per traffic message."
            )
        }

        # Add existing service name to error message if duplicate
        if errors.get("base") == "duplicate_config":
            description_placeholders["existing_service"] = self._existing_service_name

        return self.async_show_form(
            step_id="traffic_messages",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_traffic_messages_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Configure traffic messages service - step 2: name the service.

        Returns:
            Flow result with form or config entry.

        """
        errors = {}

        if user_input is not None:
            service_name = user_input.get("service_name")

            # Check if name is already in use
            for entry in self._async_current_entries():
                if entry.title == service_name:
                    errors["service_name"] = "duplicate_name"
                    break

            # If no duplicate name, create the entry
            if not errors:
                self._traffic_config["entity_type"] = ENTITY_TYPE_TRAFFIC_MESSAGES
                return self.async_create_entry(
                    title=service_name,
                    data=self._traffic_config,
                )

        # Generate default name suggestion
        municipalities = self._traffic_config.get("municipalities", [])
        situation_types = self._traffic_config.get("situation_types", SITUATION_TYPES)

        # Build default title from municipalities and situation types
        if municipalities:
            if len(municipalities) == 1:
                muni_part = municipalities[0]
            else:
                muni_part = f"{len(municipalities)} municipalities"
        else:
            muni_part = "All municipalities"

        if len(situation_types) == 1:
            type_part = SITUATION_TYPE_LABELS[situation_types[0]]
        elif len(situation_types) == len(SITUATION_TYPES):
            type_part = "All types"
        else:
            type_part = f"{len(situation_types)} types"

        default_name = f"Traffic: {muni_part} - {type_part}"

        schema = vol.Schema(
            {
                vol.Required(
                    "service_name", default=default_name
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="traffic_messages_name",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": (
                    "Give your traffic message service a name to identify it easily."
                )
            },
        )

    async def async_step_weathercam(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Configure weathercam - step 1: select municipality.

        Returns:
            Flow result with form or next step.

        """
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

    async def async_step_weathercam_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Configure weathercam - step 2: select specific camera.

        Returns:
            Flow result with form or next step.

        """
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

    async def async_step_weathercam_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Configure weathercam - step 3: select camera presets (directions).

        Returns:
            Flow result with form or config entry.

        """
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

    @staticmethod
    async def _async_fetch_weathercam_data() -> dict[str, Any]:
        """
        Load weathercam data from static JSON file.

        Returns:
            Dict containing weathercam data.

        """
        data_path = Path(__file__).parent / "data" / "weathercam_data.json"
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _get_municipalities_with_cameras(cameras: dict[str, Any]) -> list[str]:
        """
        Get a list of unique municipalities that have weathercams.

        Returns:
            List of municipality names.

        """
        municipalities = set()

        for camera_data in cameras.values():
            municipality = camera_data.get("municipality")
            if municipality:
                municipalities.add(municipality)

        return list(municipalities)

    @staticmethod
    def _filter_cameras_by_municipality(
        cameras: dict[str, Any], municipality: str
    ) -> list[dict[str, Any]]:
        """
        Filter cameras by municipality from the static data.

        Returns:
            List of camera dictionaries with id and name.

        """
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Support reconfiguring an existing config entry from the Integrations UI.

        Updates the existing entry instead of creating a new one,
        which allows entities to be updated rather than recreated.

        Returns:
            Flow result with reconfiguration form or next step.

        """
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        entity_type = entry.data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

        # Route to appropriate reconfiguration based on entity type
        if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
            return await self._async_reconfigure_traffic_messages(entry, user_input)
        if entity_type == ENTITY_TYPE_WEATHERCAM:
            return await self._async_reconfigure_weathercam(entry, user_input)

        return self.async_abort(reason="unknown_entity_type")

    async def _async_reconfigure_traffic_messages(
        self,
        entry: config_entries.ConfigEntry,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """
        Reconfigure traffic messages entry.

        Returns:
            Flow result with form or abort.

        """
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

    async def _async_reconfigure_weathercam(
        self,
        _entry: config_entries.ConfigEntry,
        _user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """
        Reconfigure weathercam entry - allow adding new cameras.

        Returns:
            Flow result with next step.

        """
        # Reset instance variables for new camera selection
        self._weathercam_municipality = None
        self._weathercam_data = None
        self._weathercam_id = None
        self._weathercam_name = None

        # Start municipality selection
        return await self.async_step_reconfigure_weathercam_municipality()

    async def async_step_reconfigure_weathercam_municipality(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Step 1: Select municipality for new camera.

        Returns:
            Flow result with form or next step.

        """
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

    async def async_step_reconfigure_weathercam_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Step 2: Select camera in the chosen municipality.

        Returns:
            Flow result with form or next step.

        """
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

    async def async_step_reconfigure_weathercam_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Step 3: Select presets for the chosen camera.

        Returns:
            Flow result with form or abort.

        """
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
    """
    Handle options for the integration (reconfiguration).

    This options flow allows the user to change municipalities and situation types.
    Options are saved to `entry.options`.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manage the options.

        Returns:
            Flow result with form or options entry.

        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get entity type to determine which options to show
        entity_type = self.config_entry.data.get(
            "entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES
        )

        if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
            return await self._async_traffic_messages_options(user_input)
        if entity_type == ENTITY_TYPE_WEATHERCAM:
            return await self.async_step_manage_weathercams(user_input)

        # For other entity types, return empty form for now
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))

    async def _async_traffic_messages_options(
        self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Show options for traffic messages.

        Returns:
            Flow result with options form.

        """
        # Prefer existing options, fall back to initial data
        current_municipalities = self.config_entry.options.get(
            "municipalities", self.config_entry.data.get("municipalities", [])
        )
        current_situation_types = self.config_entry.options.get(
            "situation_types",
            self.config_entry.data.get("situation_types", SITUATION_TYPES),
        )

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
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_manage_weathercams(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manage weathercam cameras - allow selecting which cameras/presets to keep.

        Returns:
            Flow result with form or options entry.

        """
        if user_input is not None:
            return await self._save_weathercam_selection(user_input)

        return await self._show_weathercam_management_form()

    async def _save_weathercam_selection(
        self, user_input: dict[str, Any]
    ) -> FlowResult:
        """
        Save user's weathercam preset selection.

        Returns:
            Flow result with entry creation.

        """
        selected_presets = user_input.get("presets", [])
        existing_cameras = self.config_entry.data.get("cameras", [])
        updated_cameras = []

        for camera in existing_cameras:
            camera_presets = [
                p for p in camera.get("presets", []) if p in selected_presets
            ]
            if camera_presets:
                updated_camera = camera.copy()
                updated_camera["presets"] = camera_presets
                updated_cameras.append(updated_camera)

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                "entity_type": ENTITY_TYPE_WEATHERCAM,
                "cameras": updated_cameras,
            },
        )

        return self.async_create_entry(title="", data={})

    async def _show_weathercam_management_form(self) -> FlowResult:
        """
        Show form for managing weathercam presets.

        Returns:
            Flow result with management form.

        """
        existing_cameras = self.config_entry.data.get("cameras", [])

        data_file = Path(__file__).parent / "data" / "weathercam_data.json"
        weathercam_data = await self.hass.async_add_executor_job(
            _load_weathercam_data_sync, data_file
        )

        preset_options, current_presets = _build_preset_options(
            existing_cameras, weathercam_data
        )

        if not preset_options:
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    "presets", default=current_presets
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=preset_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="manage_weathercams",
            data_schema=schema,
            description_placeholders={
                "description": "Select which camera presets to keep. "
                "Unchecked items will be removed."
            },
        )


def _build_preset_options(
    cameras: list[dict], weathercam_data: dict
) -> tuple[list[selector.SelectOptionDict], list[str]]:
    """
    Build preset options for selection form.

    Returns:
        Tuple of (preset options, current preset IDs).

    """
    preset_options = []
    current_presets = []

    for camera in cameras:
        camera_id = camera.get("camera_id", "")
        camera_name = camera.get("camera_name", camera_id)
        camera_data = weathercam_data.get(camera_id, {})
        all_presets = camera_data.get("presets", [])

        for preset_id in camera.get("presets", []):
            preset_info = next((p for p in all_presets if p["id"] == preset_id), None)
            if preset_info:
                preset_name = preset_info.get("presentationName", preset_id)
                label = f"{camera_name} - {preset_name}"
            else:
                label = f"{camera_name} - {preset_id}"

            preset_options.append(
                selector.SelectOptionDict(value=preset_id, label=label)
            )
            current_presets.append(preset_id)

    return preset_options, current_presets


def _load_weathercam_data_sync(data_file: Path) -> dict:
    """
    Load weathercam data synchronously for options flow.

    Args:
        data_file: Path to weathercam data file.

    Returns:
        Weathercam data dictionary.

    """
    with data_file.open(encoding="utf-8") as f:
        return json.load(f)
