"""Indygo Pool API Client."""

from __future__ import annotations

import json
import re
from http import HTTPStatus

import aiohttp

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
        pool_id: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize Indygo Pool API Client."""
        self._email = email
        self._password = password
        self._pool_id = pool_id
        self._session = session
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

                # Check if we got the session cookie

                if response.status == HTTPStatus.FOUND:
                    LOGGER.debug("Login successful (redirected)")
                else:
                    # If 200, we might be on the login page (failed auth)
                    # or dashboard (already auth?)
                    LOGGER.warning(
                        "Login returned 200, expected 302. Content start: %s",
                        (await response.text())[:200],
                    )
                    pass

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error logging in: {exception}"
            ) from exception

    async def async_ensure_discovery(self) -> None:  # noqa: PLR0912, PLR0915
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
                # Log where we actually landed
                LOGGER.debug(
                    "Discovery URL: %s, Status: %s", response.url, response.status
                )

                if response.status != HTTPStatus.OK or "login" in str(response.url):
                    # Maybe session expired? Try login again once
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

            # Extract currentPool
            start_regex = re.compile(
                r"(?:var|let|const|window\.)?\s*currentPool\s*=\s*(\{)", re.IGNORECASE
            )
            match = start_regex.search(text)
            if match:
                start_index = match.start(1)
                json_str = self._extract_json_object(text, start_index)
                if json_str:
                    try:
                        self._pool_metadata = json.loads(json_str)
                    except json.JSONDecodeError as exc:
                        LOGGER.error("Failed to decode currentPool JSON: %s", exc)

            # Extract ipxModule (for salt, ph setpoint, etc.)
            ipx_start_regex = re.compile(
                r"(?:var|let|const|window\.)?\s*ipxModule\s*=\s*(\{)", re.IGNORECASE
            )
            ipx_match = ipx_start_regex.search(text)
            if ipx_match:
                ipx_start_index = ipx_match.start(1)
                ipx_json_str = self._extract_json_object(text, ipx_start_index)
                if ipx_json_str:
                    try:
                        self._ipx_module_metadata = json.loads(ipx_json_str)
                    except json.JSONDecodeError as exc:
                        LOGGER.error("Failed to decode ipxModule JSON: %s", exc)
            else:
                LOGGER.warning("Could not find ipxModule in HTML (discovery)")

            if not self._pool_metadata:
                LOGGER.error("HTML (truncated): %s", text[:1000])
                raise IndygoPoolApiClientError(
                    "Could not find valid 'currentPool' object in HTML."
                )

            # Extract IDs from currentPool
            try:
                # Find the main module (lr-pc or ipx)
                if "modules" in self._pool_metadata:
                    modules = self._pool_metadata["modules"]

                    # Logic: Prioritize lr-pc (gateway + realy ID)
                    lr_pc = next((m for m in modules if m.get("type") == "lr-pc"), None)
                    if lr_pc:
                        # Gateway serial is the LRMC/LRMB serial,
                        # found via relay link usually,
                        # BUT user observed URL pattern:
                        # /module/{GATEWAY_SERIAL}/status/{RELAY_ID}
                        # And found: Gateway LRMB10... (Serial 1000...)
                        # -> Device LRPC... (ShortID F1E81E)

                        # We need to find the gateway.
                        # In the user's trace: Gateway was 'LRMB10-0B7519'
                        # (type lr-mb-10).
                        # Let's find a gateway-like module (lr-mb-10 or similar?)
                        # or use the owner?

                        # Actually simpler: The URL uses valid serials.
                        # If we have an 'lr-mb-10', use its serial as the address.
                        gateway = next(
                            (m for m in modules if m.get("type") == "lr-mb-10"), None
                        )
                        if not gateway:
                            # Fallback to current lr-pc if no separate gateway?
                            # Or maybe the lr-pc IS the gateway in some setups?
                            # For now, let's look for lr-mb-10 first.
                            gateway = lr_pc  # Fallback assumption

                        self._pool_address = gateway.get("serialNumber")

                        # Relay ID is the short ID of the lr-pc
                        # e.g. LRPC-F1E81E -> F1E81E.
                        # It seems to be the last part of snake_case name or derived
                        # from serial?
                        name_parts = lr_pc.get("name", "").split("-")
                        if len(name_parts) > 1:
                            self._relay_id = name_parts[-1]
                        else:
                            self._relay_id = lr_pc.get("serialNumber")[
                                -6:
                            ]  # Guessing last 6 chars?

                        LOGGER.debug(
                            "Selected Strategy: Gateway %s (Serial %s) "
                            "-> Device %s (ShortID %s)",
                            gateway.get("name"),
                            self._pool_address,
                            lr_pc.get("name"),
                            self._relay_id,
                        )

                    else:
                        # Fallback for IPX only systems (older?)
                        ipx = next((m for m in modules if m.get("type") == "ipx"), None)
                        if ipx:
                            self._pool_address = ipx.get("serialNumber")
                            self._relay_id = ipx.get("ipxRelay")
                            LOGGER.debug(
                                "Selected Strategy: IPX Direct (Serial %s, Relay %s)",
                                self._pool_address,
                                self._relay_id,
                            )
                        else:
                            raise IndygoPoolApiClientError(
                                "No compatible module (lr-pc or ipx) found."
                            )

            except (KeyError, IndexError, TypeError) as exc:
                LOGGER.error("Failed to parse pool IDs from JSON: %s", exc)
                raise IndygoPoolApiClientError(
                    "Failed to parse pool configuration."
                ) from exc

            if not self._pool_address or not self._relay_id:
                raise IndygoPoolApiClientError(
                    "Could not determine Pool Address or Relay ID."
                )

            LOGGER.debug(
                "Discovered pool keys: gateway_serial=%s, device_short_id=%s",
                self._pool_address,
                self._relay_id,
            )

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error during discovery: {exception}"
            ) from exception

    def _extract_json_object(self, text: str, start_index: int) -> str | None:
        """Extract a JSON object from text starting at start_index."""
        brace_count = 0
        in_string = False
        escape = False

        for i in range(start_index, len(text)):
            char = text[i]

            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[start_index : i + 1]

        return None

    async def async_get_data(self) -> dict:
        """Get data from the API."""
        await self.async_ensure_discovery()

        try:
            url = f"https://myindygo.com/v1/module/{self._pool_address}/status/{self._relay_id}"  # noqa: E501
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
                        # Merge with metadata if available
                        if self._pool_metadata:
                            data.update(self._pool_metadata)
                        if self._ipx_module_metadata:
                            data["ipx_module"] = self._ipx_module_metadata
                        return data

                if response.status != HTTPStatus.OK:
                    raise IndygoPoolApiClientCommunicationError(
                        f"Error fetching data: {response.status}"
                    )

                data = await response.json()
                # Merge with metadata if available
                if self._pool_metadata:
                    data.update(self._pool_metadata)
                if self._ipx_module_metadata:
                    data["ipx_module"] = self._ipx_module_metadata
                return data

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error communicating with API: {exception}"
            ) from exception
