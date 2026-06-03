"""API client for Digitraffic traffic messages."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout

from .const import DIGITRAFFIC_USER

API_URL = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"


class DigitrafficApiClientError(Exception):
    """Exception to indicate a general API error."""


class DigitrafficApiClientCommunicationError(DigitrafficApiClientError):
    """Exception to indicate a communication error."""


class DigitrafficApiClientAuthenticationError(DigitrafficApiClientError):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise DigitrafficApiClientAuthenticationError(msg)
    response.raise_for_status()


class DigitrafficApiClient:
    """Client for interacting with the Digitraffic API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._session = session

    async def fetch_active_messages(
        self, situation_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Fetch active traffic messages."""
        params: dict[str, Any] = {
            "inactiveHours": 0,
            "includeAreaGeometry": "false",
        }

        if situation_types:
            params["situationType"] = situation_types

        return await self._api_wrapper(
            method="get",
            url=API_URL,
            params=params,
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        default_headers = {"Digitraffic-User": DIGITRAFFIC_USER}
        if headers:
            default_headers.update(headers)

        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=default_headers,
                    params=params,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise DigitrafficApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise DigitrafficApiClientCommunicationError(msg) from exception
        except DigitrafficApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise DigitrafficApiClientError(msg) from exception
