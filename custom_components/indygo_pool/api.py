"""Indygo Pool API Client."""

from __future__ import annotations

import time
from http import HTTPStatus

import aiohttp

from .const import LOGGER
from .models import IndygoPoolData
from .parser import IndygoParser


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
        pool_id: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize Indygo Pool API Client."""
        self._email = email
        self._password = password
        self._pool_id = pool_id
        self._session = session
        self._parser = IndygoParser()

        self._pool_address: str | None = None
        self._relay_id: str | None = None
        self._pool_metadata: dict | None = None
        self._ipx_module_metadata: dict | None = None

    async def async_login(self) -> None:
        """Login to the API."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            # Login payload
            data = {
                "email": self._email,
                "password": self._password,
            }

            # Perform login
            # First, fetch the login page to establish session/cookies
            async with self._session.get(
                "https://myindygo.com/login", headers=headers
            ) as response_get:
                if response_get.status != HTTPStatus.OK:
                    LOGGER.warning("Initial GET /login failed: %s", response_get.status)

            # Then POST credentials
            async with self._session.post(
                "https://myindygo.com/login",
                data=data,
                headers=headers,
                allow_redirects=False,  # We expect a 302 redirect
            ) as response:
                if response.status not in (HTTPStatus.OK, HTTPStatus.FOUND):
                    raise IndygoPoolApiClientAuthenticationError(
                        f"Login failed: status code {response.status}, "
                        f"text: {await response.text()}"
                    )

                if response.status == HTTPStatus.FOUND:
                    location = response.headers.get("Location")
                    LOGGER.debug("Login successful (redirected to %s)", location)
                else:
                    LOGGER.warning(
                        "Login returned 200, expected 302. Content start: %s",
                        (await response.text())[:200],
                    )

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error logging in: {exception}"
            ) from exception

    async def async_ensure_discovery(self) -> None:
        """Ensure we have the internal pool IDs (address and relayId)."""
        if self._pool_address and self._relay_id:
            return

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            # Fetch the devices page
            url = f"https://myindygo.com/pools/{self._pool_id}/devices"
            async with self._session.get(url, headers=headers) as response:
                LOGGER.debug(
                    "Discovery URL: %s, Status: %s", response.url, response.status
                )

                if response.status != HTTPStatus.OK or "login" in str(response.url):
                    LOGGER.debug(
                        "Discovery failed or redirected to login, retrying auth..."
                    )
                    await self.async_login()
                    async with self._session.get(
                        url, headers=headers
                    ) as response_retry:
                        LOGGER.debug("Retry Discovery URL: %s", response_retry.url)
                        if response_retry.status != HTTPStatus.OK:
                            raise IndygoPoolApiClientCommunicationError(
                                f"Failed to fetch devices page: {response_retry.status}"
                            )
                        text = await response_retry.text()
                else:
                    text = await response.text()

            # Parse HTML
            pool_address, relay_id, pool_metadata = self._parser.parse_pool_ids(
                text, self._pool_id
            )

            # Parse IPX Module Metadata (from same page)
            self._ipx_module_metadata = self._parser.parse_ipx_module(text)

            if not pool_address or not relay_id:
                LOGGER.error("HTML (truncated): %s", text[:1000])
                raise IndygoPoolApiClientError(
                    "Could not determine Pool Address or Relay ID."
                )

            self._pool_address = pool_address
            self._relay_id = relay_id
            self._pool_metadata = pool_metadata

            LOGGER.debug(
                "Discovered pool keys: gateway_serial=%s, device_short_id=%s",
                self._pool_address,
                self._relay_id,
            )

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error during discovery: {exception}"
            ) from exception

    async def async_get_data(self) -> IndygoPoolData:
        """Get data from the API."""
        await self.async_ensure_discovery()

        if not self._pool_address or not self._relay_id:
            raise IndygoPoolApiClientError(
                "Pool Address or Relay ID missing after discovery"
            )

        try:
            url = f"https://myindygo.com/v1/module/{self._pool_address}/status/{self._relay_id}?_={int(time.time() * 1000)}"  # noqa: E501
            headers = {
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": f"https://myindygo.com/pools/{self._pool_id}/devices",
                "Origin": "https://myindygo.com",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "x-requested-with": "XMLHttpRequest",
                "accept": "version=2.1",
            }

            LOGGER.debug("Fetching data from %s", url)

            async with self._session.get(url, headers=headers) as response:
                if response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    # Session expired, re-login
                    await self.async_login()
                    async with self._session.get(
                        url, headers=headers
                    ) as response_retry:
                        if response_retry.status != HTTPStatus.OK:
                            raise IndygoPoolApiClientCommunicationError(
                                "Error fetching data after re-login: "
                                f"{response_retry.status}"
                            )
                        data = await response_retry.json()
                elif response.status != HTTPStatus.OK:
                    raise IndygoPoolApiClientCommunicationError(
                        f"Error fetching data: {response.status}"
                    )
                else:
                    data = await response.json()

                # Merge with metadata if available for completeness
                # (Parser might use it if we passed it, but we can also just inject it
                # into the data dict or handle it in parser)
                if self._pool_metadata:
                    data.update(self._pool_metadata)
                if self._ipx_module_metadata:
                    data["ipx_module"] = self._ipx_module_metadata

                # Parse data
                return self._parser.parse_data(
                    data, self._pool_id, self._pool_address, self._relay_id
                )

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error communicating with API: {exception}"
            ) from exception
