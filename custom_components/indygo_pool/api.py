"""Indygo Pool API Client."""

from __future__ import annotations

import copy
import json
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

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

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
        self._scraped_programs: dict[str, list[dict]] | None = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        data: dict | None = None,
        return_json: bool = False,
        allow_redirects: bool = True,
        retry_auth: bool = False,
    ) -> aiohttp.ClientResponse | dict | str:
        """Perform an HTTP request."""
        request_headers = self.DEFAULT_HEADERS.copy()
        if headers:
            request_headers.update(headers)

        try:
            LOGGER.debug(f"--- REQUEST: {method} {url} ---")
            async with self._session.request(
                method,
                url,
                headers=request_headers,
                data=data,
                allow_redirects=allow_redirects,
            ) as response:
                if (
                    response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)
                    or (
                        # Sometimes scraping redirects to login on session expiry
                        not allow_redirects
                        and response.status == HTTPStatus.FOUND
                        and "login" in response.headers.get("Location", "")
                    )
                    or (
                        # Specific check for scraping where redirect
                        # might be followed transparently
                        "login" in str(response.url)
                    )
                ) and retry_auth:
                    LOGGER.debug(
                        "Session expired or redirected to login, re-authenticating..."
                    )
                    await self.async_login()
                    # Retry carefully to avoid infinite recursion
                    return await self._request(
                        method,
                        url,
                        headers=headers,
                        data=data,
                        return_json=return_json,
                        allow_redirects=allow_redirects,
                        retry_auth=False,
                    )

                if response.status != HTTPStatus.OK and not (
                    # Allow 302 for login flow if caller handles it
                    not allow_redirects and response.status == HTTPStatus.FOUND
                ):
                    # We might want to read the body for error details
                    try:
                        text = await response.text()
                    except Exception:
                        text = "<could not read response>"
                    LOGGER.error(
                        "API Request %s %s failed: %s - %s",
                        method,
                        url,
                        response.status,
                        text,
                    )
                    raise IndygoPoolApiClientCommunicationError(
                        f"Request failed: {response.status}"
                    )

                if return_json:
                    return await response.json()
                return await response.text()

        except aiohttp.ClientError as exception:
            raise IndygoPoolApiClientCommunicationError(
                f"Error communicating with API: {exception}"
            ) from exception

    async def async_login(self) -> None:
        """Login to the API."""
        try:
            # Login payload
            data = {
                "email": self._email,
                "password": self._password,
            }

            # Perform login
            await self._request("GET", "https://myindygo.com/login", retry_auth=False)

            # Then POST credentials
            async with self._session.post(
                "https://myindygo.com/login",
                data=data,
                headers=self.DEFAULT_HEADERS,
                allow_redirects=False,
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

    async def async_refresh_scraped_data(self) -> None:
        """Fetch and parse the pool devices page to get fresh scraped data."""
        # Note: We run this every update because some data (IPX sensors) is only
        # available on the devices page HTML/JS, not in the status JSON API.

        url = f"https://myindygo.com/pools/{self._pool_id}/devices"
        text = await self._request("GET", url, retry_auth=True)
        # Type check helper since _request returns Union
        if not isinstance(text, str):
            # Should not happen if return_json=False
            text = str(text)

        # Parse HTML
        pool_address, relay_id, pool_metadata = self._parser.parse_pool_ids(
            text, self._pool_id
        )

        # Parse IPX Module Metadata (from same page)
        self._ipx_module_metadata = self._parser.parse_ipx_module(text)

        # Parse Programs (from embedded JS)
        self._scraped_programs = self._parser.parse_programs_from_html(text)

        if not pool_address or not relay_id:
            LOGGER.error("HTML (truncated): %s", text[:1000])
            raise IndygoPoolApiClientError(
                "Could not determine Pool Address or Relay ID."
            )

        self._pool_address = pool_address
        self._relay_id = relay_id
        self._pool_metadata = pool_metadata

        LOGGER.debug(
            "Refreshed scraped data: gateway_serial=%s, device_short_id=%s, "
            "programs_found=%s",
            self._pool_address,
            self._relay_id,
            bool(self._scraped_programs),
        )

    async def async_get_data(self) -> IndygoPoolData:
        """Get data from the API."""
        await self.async_refresh_scraped_data()

        if not self._pool_address or not self._relay_id:
            raise IndygoPoolApiClientError(
                "Pool Address or Relay ID missing after discovery"
            )

        url = f"https://myindygo.com/v1/module/{self._pool_address}/status/{self._relay_id}"
        headers = {
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://myindygo.com/pools/{self._pool_id}/devices",
            "Origin": "https://myindygo.com",
            # User-Agent is in DEFAULT_HEADERS
            "x-requested-with": "XMLHttpRequest",
            "accept": "version=2.1",
        }

        LOGGER.debug("Fetching data from %s", url)

        # get_request handles re-login if 401/403
        data = await self._request(
            "GET", url, headers=headers, return_json=True, retry_auth=True
        )
        if not isinstance(data, dict):
            # Should not happen if return_json=True and successful
            # But _request type hint allows str.
            # If it was a string, likely an error page or something went wrong?
            # For now assume it worked or _request raised.
            data = {}

        LOGGER.debug("API Data received: %s", data)

        # Merge with metadata if available for completeness
        if self._pool_metadata:
            data.update(self._pool_metadata)
        if self._ipx_module_metadata:
            data["ipx_module"] = self._ipx_module_metadata

        # Parse data
        return self._parser.parse_data(
            data,
            self._pool_id,
            self._pool_address,
            self._relay_id,
            scraped_programs=self._scraped_programs,
        )

    async def async_set_filtration_mode(
        self, module_id: str, full_program_data: dict, mode: int
    ) -> None:
        """Set the filtration mode (Auto/Off/On) safely.

        We MUST send back the FULL program object, otherwise we risk corrupting
        the device configuration (erasing timers, etc.).
        """
        # 1. Deep copy to avoid mutating the source
        program_copy = copy.deepcopy(full_program_data)

        # 2. Update the mode
        # Mode: 0=OFF, 1=ON, 2=AUTO
        if "programCharacteristics" in program_copy:
            program_copy["programCharacteristics"]["mode"] = mode
        else:
            raise IndygoPoolApiClientError(
                "Invalid program data: missing programCharacteristics"
            )

        # 3. Construct payload
        payload = {
            "module": module_id,
            "programs": [program_copy],
        }

        url = "https://myindygo.com/program/update"

        LOGGER.debug(
            "Setting filtration mode to %s for module %s. Payload: %s",
            mode,
            module_id,
            payload,
        )

        try:
            # Browser uses PUT with JSON content for update
            headers = {"Content-Type": "application/json"}
            await self._request(
                "PUT",
                url,
                headers=headers,
                data=json.dumps(payload),
                return_json=True,
                retry_auth=True,
            )

            # 4. Trigger remote synchronization
            await self.async_apply_module_changes(
                module_id, self._relay_id, program_copy
            )

        except IndygoPoolApiClientError as exception:
            LOGGER.error("Failed to set filtration mode: %s", exception)
            raise

    async def async_apply_module_changes(
        self,
        module_id: str,
        relay_id: str | None,
        full_program_data: dict | None = None,
    ) -> None:
        """Apply changes to the remote module.

        This triggers the synchronization between the Cloud and the physical device.
        """
        if not relay_id:
            LOGGER.warning("Missing relay_id, skipping remote sync")
            return

        url = "https://myindygo.com/remote/module/configuration/and/programs"
        payload = {
            "moduleId": module_id,
            "relayId": relay_id,
        }

        LOGGER.debug(
            "Applying remote changes for module %s (relay: %s)", module_id, relay_id
        )

        try:
            headers = {"Content-Type": "application/json"}
            # 1. Apply configuration to remote
            await self._request(
                "POST",
                url,
                headers=headers,
                data=json.dumps(payload),
                return_json=True,
                retry_auth=True,
            )

            # 2. Report module data sent
            report_module_url = "https://myindygo.com/module/reportModuleDataSent"
            report_module_payload = {"module": module_id}
            await self._request(
                "POST",
                report_module_url,
                headers=headers,
                data=json.dumps(report_module_payload),
                return_json=True,
                retry_auth=True,
            )

            # 3. Report programs data sent
            if full_program_data:
                report_prog_url = "https://myindygo.com/program/reportProgramsDataSent"
                report_prog_payload = {
                    "module": module_id,
                    "programs": [full_program_data],
                }
                await self._request(
                    "POST",
                    report_prog_url,
                    headers=headers,
                    data=json.dumps(report_prog_payload),
                    return_json=True,
                    retry_auth=True,
                )

        except IndygoPoolApiClientError as exception:
            LOGGER.error("Failed to apply remote changes: %s", exception)
            # We don't necessarily want to fail the whole operation if sync fails,
            # as the primary PUT update might have succeeded.
