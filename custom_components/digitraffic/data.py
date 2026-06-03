"""Custom types for Digitraffic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import DigitrafficApiClient
    from .coordinator import DigitrafficDataUpdateCoordinator


type DigitrafficConfigEntry = ConfigEntry[DigitrafficData]


@dataclass
class DigitrafficData:
    """Data for the Digitraffic integration."""

    entity_type: str
    client: DigitrafficApiClient | None = None
    coordinator: DigitrafficDataUpdateCoordinator | None = None
    integration: Integration | None = None
    active_message_sensors: dict[str, Any] = field(default_factory=dict)
    add_entities_callback: Callable[[], None] | None = None
