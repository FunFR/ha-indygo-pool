"""Indygo Pool API Client."""

from __future__ import annotations

import json
import re
import socket

import aiohttp
import async_timeout
from bs4 import BeautifulSoup

from .const import LOGGER


class IndygoPoolApiClientError(Exception):
    """Exception to indicate a general API error."""


class IndygoPoolApiClientAuthenticationError(IndygoPoolApiClientError):
    """Exception to indicate an authentication error."""


class IndygoPoolApiClientCommunicationError(IndygoPoolApiClientError):
    """Exception to indicate a communication error."""


class IndygoPoolApiClient:
    """Indygo Pool API Client."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession,
        pool_id: str | None = None,
    ) -> None:
        """Indygo Pool API Client."""
        self._email = email
        self._password = password
        self._session = session
        self._pool_id = pool_id
        self._is_logged_in = False

    async def async_login(self) -> bool:
        """Login to the API."""
        await self._api_wrapper(
            method="post",
            url="https://myindygo.com/login",
            data={
                "email": self._email,
                "password": self._password,
            },
        )
        self._is_logged_in = True
        return True

    async def async_get_data(self) -> dict:
        """Get data from the API."""
        if not self._is_logged_in:
            await self.async_login()

        if not self._pool_id:
            raise IndygoPoolApiClientError("Pool ID is required")

        html = await self._api_wrapper(
            method="get",
            url=f"https://myindygo.com/pools/{self._pool_id}/devices",
        )

        return self._parse_data(html)

    def _parse_data(self, html: str) -> dict:
        """Parse the HTML response and extract JSON variables."""
        data = {}
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script")

        for script in scripts:
            if not script.string:
                continue

            # Extract var pool
            pool_match = re.search(r"var pool\s*=\s*({.*?});", script.string, re.DOTALL)
            if pool_match:
                try:
                    data["pool"] = json.loads(pool_match.group(1))
                except json.JSONDecodeError as e:
                    LOGGER.error("Failed to parse pool JSON: %s", e)

            # Extract var modules
            modules_match = re.search(
                r"var modules\s*=\s*(\[.*?\]);", script.string, re.DOTALL
            )
            if modules_match:
                try:
                    data["modules"] = json.loads(modules_match.group(1))
                except json.JSONDecodeError as e:
                    LOGGER.error("Failed to parse modules JSON: %s", e)

            # Extract var poolCommand
            command_match = re.search(
                r"var poolCommand\s*=\s*({.*?});", script.string, re.DOTALL
            )
            if command_match:
                try:
                    data["poolCommand"] = json.loads(command_match.group(1))
                except json.JSONDecodeError as e:
                    LOGGER.error("Failed to parse poolCommand JSON: %s", e)

        if not data:
            raise IndygoPoolApiClientError("Could not find pool data in the page")

        return data

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    data=data,
                    headers=headers,
                )
                if response.status in (401, 403):
                    raise IndygoPoolApiClientAuthenticationError(
                        "Invalid credentials",
                    )
                response.raise_for_status()
                return await response.text()

        except TimeoutError as exception:
            raise IndygoPoolApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise IndygoPoolApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API call failed: %s", exception)
            raise IndygoPoolApiClientError(
                f"Something really wrong happened: {exception}"
            ) from exception
