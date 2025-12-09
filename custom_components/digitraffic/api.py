import aiohttp

from .const import DIGITRAFFIC_USER

API_URL = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"


class DigitrafficApiClient:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def fetch_active_messages(self, situation_types=None):
        """Fetch active traffic messages.

        Args:
            situation_types: List of situation types to fetch. If None, fetches all types.
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
