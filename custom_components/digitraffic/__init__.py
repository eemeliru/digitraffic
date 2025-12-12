from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DigitrafficApiClient
from .coordinator import DigitrafficDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.CAMERA]
from .const import DOMAIN, ENTITY_TYPE_TRAFFIC_MESSAGES, ENTITY_TYPE_WEATHERCAM


async def async_setup_entry(hass, entry):
    """Set up Digitraffic from a config entry."""
    entity_type = entry.data.get("entity_type", ENTITY_TYPE_TRAFFIC_MESSAGES)

    # Route to appropriate setup based on entity type
    if entity_type == ENTITY_TYPE_TRAFFIC_MESSAGES:
        return await _async_setup_traffic_messages(hass, entry)
    if entity_type == ENTITY_TYPE_WEATHERCAM:
        return await _async_setup_weathercam(hass, entry)

    return False


async def _async_setup_traffic_messages(hass, entry):
    """Set up traffic messages service."""
    session = async_get_clientsession(hass)

    # Prefer options (from reconfigure) but fall back to initial config data
    municipalities = entry.options.get(
        "municipalities", entry.data.get("municipalities", [])
    )
    situation_types = entry.options.get(
        "situation_types", entry.data.get("situation_types", None)
    )

    # Create API client and coordinator with municipality filtering
    api = DigitrafficApiClient(session)
    coordinator = DigitrafficDataUpdateCoordinator(
        hass, api, municipalities=municipalities, situation_types=situation_types
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entity_type": ENTITY_TYPE_TRAFFIC_MESSAGES,
        "coordinator": coordinator,
        "municipalities": municipalities,
        "situation_types": situation_types,
        "entry": entry,
    }

    # Update configuration when options change
    async def _async_update_options(hass, entry):
        """Handle options update - update coordinator config and refresh entities."""
        new_municipalities = entry.options.get(
            "municipalities", entry.data.get("municipalities", [])
        )
        new_situation_types = entry.options.get(
            "situation_types", entry.data.get("situation_types", None)
        )

        # Update the stored config
        hass.data[DOMAIN][entry.entry_id]["municipalities"] = new_municipalities
        hass.data[DOMAIN][entry.entry_id]["situation_types"] = new_situation_types

        # Update coordinator's configuration and refresh data
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator.update_config(
            municipalities=new_municipalities, situation_types=new_situation_types
        )
        await coordinator.async_refresh()

        # Trigger sensor platform update if callback is available
        if "add_entities_callback" in hass.data[DOMAIN][entry.entry_id]:
            callback = hass.data[DOMAIN][entry.entry_id]["add_entities_callback"]
            await callback()

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_weathercam(hass, entry):
    """Set up weathercam."""
    session = async_get_clientsession(hass)

    # Placeholder for weathercam setup - will be implemented later
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entity_type": ENTITY_TYPE_WEATHERCAM,
        "entry": entry,
    }

    # Placeholder update listener for weathercam
    async def _async_update_options(hass, entry):
        """Handle options update for weathercam."""
        # Will be implemented when weathercam entities are added

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
