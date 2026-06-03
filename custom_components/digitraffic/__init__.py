"""Digitraffic integration for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DigitrafficApiClient
from .const import ENTITY_TYPE_TRAFFIC_MESSAGES, ENTITY_TYPE_WEATHERCAM
from .coordinator import DigitrafficDataUpdateCoordinator
from .data import DigitrafficData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import DigitrafficConfigEntry

PLATFORMS = [Platform.SENSOR, Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: DigitrafficConfigEntry) -> bool:
    """Set up Digitraffic from a config entry."""
    entity_type = entry.data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

    if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
        return await _async_setup_traffic_messages(hass, entry)
    if entity_type == ENTITY_TYPE_WEATHERCAM:
        return await _async_setup_weathercam(hass, entry)

    return False


async def _async_setup_traffic_messages(
    hass: HomeAssistant, entry: DigitrafficConfigEntry
) -> bool:
    """Set up traffic messages service."""
    session = async_get_clientsession(hass)

    municipalities = entry.options.get(
        "municipalities", entry.data.get("municipalities", [])
    )
    situation_types = entry.options.get(
        "situation_types", entry.data.get("situation_types", None)
    )

    api = DigitrafficApiClient(session)
    coordinator = DigitrafficDataUpdateCoordinator(
        hass, api, municipalities=municipalities, situation_types=situation_types
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = DigitrafficData(
        entity_type=ENTITY_TYPE_TRAFFIC_MESSAGES,
        client=api,
        coordinator=coordinator,
    )

    async def _async_update_options(
        hass: HomeAssistant, entry: DigitrafficConfigEntry
    ) -> None:
        """Handle options update - update coordinator config and refresh entities."""
        new_municipalities = entry.options.get(
            "municipalities", entry.data.get("municipalities", [])
        )
        new_situation_types = entry.options.get(
            "situation_types", entry.data.get("situation_types", None)
        )

        entry.runtime_data.coordinator.update_config(
            municipalities=new_municipalities, situation_types=new_situation_types
        )
        await entry.runtime_data.coordinator.async_refresh()

        if entry.runtime_data.add_entities_callback is not None:
            entry.runtime_data.add_entities_callback()

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_weathercam(
    hass: HomeAssistant, entry: DigitrafficConfigEntry
) -> bool:
    """Set up weathercam cameras."""
    entry.runtime_data = DigitrafficData(entity_type=ENTITY_TYPE_WEATHERCAM)

    async def _async_update_options(
        hass: HomeAssistant, entry: DigitrafficConfigEntry
    ) -> None:
        """Handle options update for weathercam cameras."""
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DigitrafficConfigEntry
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
