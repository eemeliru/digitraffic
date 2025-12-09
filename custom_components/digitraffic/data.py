"""Custom types for Digitraffic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import DigitrafficApiClient
    from .coordinator import DigitrafficDataUpdateCoordinator


type DigitrafficConfigEntry = ConfigEntry[DigitrafficData]


@dataclass
class DigitrafficData:
    """Data for the Digitraffic integration."""

    client: DigitrafficApiClient
    coordinator: DigitrafficDataUpdateCoordinator
    integration: Integration
