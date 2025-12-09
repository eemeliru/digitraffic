<!-- Copilot instructions for working on the Digitraffic blueprint integration -->
# Quick Orientation

This repository is a Home Assistant custom integration blueprint (domain `digitraffic`). Main flow:

- `custom_components/digitraffic/api.py` — small `aiohttp` client; fetches JSON from Digitraffic API (`API_URL`).
- `custom_components/digitraffic/coordinator.py` — extends `DataUpdateCoordinator`. Returns RAW `features` list (important: do not pre-filter here).
- `custom_components/digitraffic/__init__.py` — creates `DigitrafficApiClient` and `DigitrafficCoordinator`, stores them at `hass.data[DOMAIN][entry.entry_id]`, and forwards setups to `Platform.SENSOR`.
- `custom_components/digitraffic/sensor.py` — defines entities as `CoordinatorEntity` + `SensorEntity`. One global sensor plus per-municipality sensors. Filtering happens in entity code.
- `custom_components/digitraffic/config_flow.py` — config flow that exposes `municipalities` (uses `FINNISH_MUNICIPALITIES` from `const.py`).

# Key Patterns & Conventions (project-specific)

- Coordinator returns raw API payload: `_async_update_data()` must return the unfiltered `features` array (entities perform any filtering). See `coordinator.py` where `return data.get("features", [])` is explicit.
- Entities are `CoordinatorEntity` subclasses. They access data via `self.coordinator.data` and implement lightweight filtering locally (see `DigitrafficMunicipalitySensor._filtered()` in `sensor.py`).
- Unique ID format: sensors use `f"{entry.entry_id}_all"` and `f"{entry.entry_id}_{municipality.lower()}"` — keep that pattern to avoid breaking existing installs.
- Device identifiers and attribution: `entity.py` sets `DeviceInfo.identifiers` to `(domain, entry_id)` and `_attr_attribution = ATTRIBUTION` — use these when adding device info or attribution.
- Use Home Assistant provided aiohttp session via `hass.helpers.aiohttp_client.async_get_clientsession(hass)` (see `__init__.py`), not a new ClientSession.
- Config is stored in the config entry `data` (see `config_flow.py`); the value `municipalities` may be an empty list which means "all".

# Developer Workflows (how to run / debug)

- Start a local dev instance (recommended): run `scripts/develop` from repo root. That script:
  - Ensures `config/` exists, sets `PYTHONPATH` to `custom_components/`, and launches `hass --config config`.
- Linting and formatting: this project includes `scripts/lint`. Use it before PRs.
- Dependencies: see `requirements.txt` (pinned `homeassistant` version used for dev/testing). If adding new runtime deps, add them here.

# Integration / External Points

- External API: `https://tie.digitraffic.fi/api/traffic-message/v1/messages` — requests are made from `api.py`.
- `manifest.json` declares `config_flow: true` and `iot_class: cloud_polling`. Keep manifest metadata consistent when changing behaviors.

# Safe Change Guidelines (to avoid breaking existing behavior)

- If you change the coordinator return structure, update every entity that relies on `coordinator.data` — prefer maintaining the `features` list structure.
- When adding new sensors/platforms, follow `PLATFORMS = [Platform.SENSOR]` and forward setups from `async_setup_entry` like `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)`.
- Maintain `unique_id` format to preserve device/entity continuity.

# Files To Inspect For Examples

- `custom_components/digitraffic/__init__.py`
- `custom_components/digitraffic/api.py`
- `custom_components/digitraffic/coordinator.py`
- `custom_components/digitraffic/sensor.py`
- `custom_components/digitraffic/config_flow.py`
- `custom_components/digitraffic/entity.py`
- `manifest.json`, `requirements.txt`, `scripts/develop`

# Notes / Gaps

- There are no unit tests in the repo. The `README.md` recommends `pytest-homeassistant-custom-component` for tests — write tests that exercise the coordinator and sensors using a mocked aiohttp response.
- `sensor.py_backup` and `testi.py` appear to be scraps; prefer editing the `custom_components/digitraffic/*` production files.

# When in doubt (recommended quick checks)

- To see what the coordinator returns, add a debug log in `_async_update_data()` or inspect `self.coordinator.data` in an entity.
- To reproduce issues locally, run `scripts/develop` and enable `--debug` (the script already uses `--debug`).

Please review and tell me which parts need more detail (examples, commands, or missing conventions) and I'll iterate.
