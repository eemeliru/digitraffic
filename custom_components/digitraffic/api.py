"""API client for Digitraffic traffic messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DIGITRAFFIC_USER

if TYPE_CHECKING:
    import aiohttp

API_URL = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"


class DigitrafficApiClient:
    """Client for interacting with the Digitraffic API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """
        Initialize the API client.

        Args:
            session: aiohttp client session for making requests.

        """
        self._session = session

    async def fetch_active_messages(
        self, situation_types: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Fetch active traffic messages.

        Args:
            situation_types: List of situation types to fetch.
                If None, fetches all types.

        Returns:
            Dictionary containing traffic message data from the API.

        """
        params = {
            "inactiveHours": 0,
            "includeAreaGeometry": "false",
        }

        # Add situation types to params if specified
        if situation_types:
            # API accepts multiple situationType params
            params["situationType"] = situation_types

        headers = {"Digitraffic-User": DIGITRAFFIC_USER}

        async with self._session.get(API_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
