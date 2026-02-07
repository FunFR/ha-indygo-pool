"""Indygo Pool API Client."""

from __future__ import annotations

import copy
import json
from http import HTTPStatus
from typing import Any

import aiohttp

from .const import LOGGER, PROGRAM_TYPE_FILTRATION
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
        self._device_short_id: str | None = None
        self._relay_id: str | None = None
        self._pool_metadata: dict | None = None
        self._ipx_module_metadata: dict | None = None
        self._scraped_programs: dict[str, list[dict]] | None = None
        self._data: IndygoPoolData | None = None

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

        # Parse Pool IDs and metadata
        pool_address, device_short_id, relay_id, pool_metadata = (
            self._parser.parse_pool_ids(text, self._pool_id)
        )
        self._ipx_module_metadata = self._parser.parse_ipx_module(text)

        # Parse Programs (from embedded JS)
        self._scraped_programs = self._parser.parse_programs_from_html(text)

        if not pool_address or not device_short_id or not relay_id:
            LOGGER.error("HTML (truncated): %s", text[:1000])
            raise IndygoPoolApiClientError(
                "Could not determine Pool Address, Device Short ID, or Relay ID."
            )

        self._pool_address = pool_address
        self._device_short_id = device_short_id
        self._relay_id = relay_id
        self._pool_metadata = pool_metadata

        LOGGER.debug(
            "Refreshed scraped data: gateway_serial=%s, device_short_id=%s, "
            "relay_id=%s, programs_found=%s",
            self._pool_address,
            self._device_short_id,
            self._relay_id,
            bool(self._scraped_programs),
        )

    async def async_get_data(self) -> IndygoPoolData:
        """Get data from the API."""
        await self.async_refresh_scraped_data()

        if not self._pool_address or not self._device_short_id:
            raise IndygoPoolApiClientError(
                "Missing pool address or device short ID. "
                "Call async_refresh_data first."
            )

        url = f"https://myindygo.com/v1/module/{self._pool_address}/status/{self._device_short_id}"
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
        self._data = self._parser.parse_data(
            data,
            self._pool_id,
            self._pool_address,
            self._relay_id,
            scraped_programs=self._scraped_programs,
        )
        return self._data

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

        # 3. Set dataChanged flag to trigger activation
        program_copy["dataChanged"] = True

        # 4. Fetch all programs and module name to send a complete set
        module_programs = []
        module_name = ""
        if hasattr(self, "_data") and self._data and module_id in self._data.modules:
            module_programs = self._data.modules[module_id].programs
            module_name = self._data.modules[module_id].name
        elif (
            hasattr(self, "_scraped_programs")
            and self._scraped_programs
            and module_id in self._scraped_programs
        ):
            module_programs = self._scraped_programs[module_id]

        # Replace the old program in the list with the newly updated one
        # and set dataChanged=True on ALL programs
        updated_programs = []
        program_id = program_copy.get("id")
        for prog in module_programs:
            if prog.get("id") == program_id:
                updated_programs.append(program_copy)
            else:
                # Deep copy other programs and set dataChanged=True on them too
                prog_copy = copy.deepcopy(prog)
                prog_copy["dataChanged"] = True

                # Only filtration programs (programType=4) should have a mode value
                prog_type = prog_copy.get("programCharacteristics", {}).get(
                    "programType"
                )
                if prog_type != PROGRAM_TYPE_FILTRATION:
                    # Set mode to None for non-filtration programs
                    if (
                        "programCharacteristics" in prog_copy
                        and "mode" in prog_copy["programCharacteristics"]
                    ):
                        prog_copy["programCharacteristics"]["mode"] = None

                updated_programs.append(prog_copy)

        if not any(p.get("id") == program_id for p in updated_programs):
            updated_programs.append(program_copy)

        # 5. Construct payload with ALL programs
        payload = {
            "module": module_id,
            "programs": updated_programs,  # Send ALL programs, not just one!
        }

        url_program = "https://myindygo.com/program/update"
        url_module = "https://myindygo.com/module/update"

        LOGGER.debug(
            "Setting filtration mode to %s for module %s. Sending %d programs.",
            mode,
            module_id,
            len(updated_programs),
        )

        try:
            headers = {"Content-Type": "application/json"}

            module_payload = {
                "module": {
                    "id": module_id,
                    "name": module_name if module_name else "",
                }
            }

            await self._request(
                "PUT",
                url_module,
                headers=headers,
                data=json.dumps(module_payload),
                return_json=True,
                retry_auth=True,
            )

            await self._request(
                "PUT",
                url_program,
                headers=headers,
                data=json.dumps(payload),
                return_json=True,
                retry_auth=True,
            )

            # 6. Trigger remote synchronization
            await self.async_apply_module_changes(
                module_id,
                self._relay_id,
                updated_programs,
                program_copy,
                module_name=module_name,
            )

        except IndygoPoolApiClientError as exception:
            LOGGER.error("Failed to set filtration mode: %s", exception)
            raise

    def _get_module_serial(self, module_id: str) -> str | None:
        """Get module serial number from various sources."""
        # Try from cached data
        if hasattr(self, "_data") and self._data and module_id in self._data.modules:
            serial = self._data.modules[module_id].raw_data.get("serialNumber")
            if serial:
                return serial

        # Try from metadata
        if self._pool_metadata:
            for module in self._pool_metadata.get("modules", []):
                if module.get("id") == module_id:
                    return module.get("serialNumber")

        # Fallback to pool address
        return self._pool_address

    async def _send_module_name_update(
        self, module_id: str, relay_id: str, module_name: str, headers: dict
    ) -> None:
        """Send module name update to remote."""
        name_url = "https://myindygo.com/remote/module/name"
        name_payload = {
            "moduleId": module_id,
            "relayId": relay_id,
            "moduleName": module_name,
        }
        await self._request(
            "POST",
            name_url,
            headers=headers,
            data=json.dumps(name_payload),
            return_json=True,
            retry_auth=True,
        )

    async def _report_programs_sent(
        self, module_id: str, programs: list[dict], headers: dict
    ) -> None:
        """Report programs data sent to server."""
        report_prog_url = "https://myindygo.com/program/reportProgramsDataSent"
        report_prog_payload = {
            "module": module_id,
            "programs": programs,
        }
        await self._request(
            "POST",
            report_prog_url,
            headers=headers,
            data=json.dumps(report_prog_payload),
            return_json=True,
            retry_auth=True,
        )

    async def _handle_off_mode_control(
        self, module_id: str, full_program_data: dict
    ) -> None:
        """Handle remote control for OFF mode."""
        mode_id = full_program_data.get("programCharacteristics", {}).get("mode")

        # Only send remote control for OFF mode
        if mode_id == 0:
            module_serial = self._get_module_serial(module_id)
            # Action: 1=Stop. Used to immediately stop the pump/light when set to OFF.
            await self.async_send_remote_control("off", module_serial, action=1)

    async def async_apply_module_changes(
        self,
        module_id: str,
        relay_id: str | None,
        programs: list[dict] | None = None,
        full_program_data: dict | None = None,
        module_name: str | None = None,
    ) -> None:
        """Apply changes to the remote module.

        This triggers the synchronization between the Cloud and the physical device.
        """
        if not relay_id:
            LOGGER.warning("Missing relay_id, skipping remote sync")
            return

        headers = {"Content-Type": "application/json"}
        LOGGER.debug(
            "Applying remote changes for module %s (relay: %s)", module_id, relay_id
        )

        try:
            # 1. Update module name if provided
            if module_name:
                await self._send_module_name_update(
                    module_id, relay_id, module_name, headers
                )

            # 2. Apply configuration to remote
            url = "https://myindygo.com/remote/module/configuration/and/programs"
            payload = {"moduleId": module_id, "relayId": relay_id}
            await self._request(
                "POST",
                url,
                headers=headers,
                data=json.dumps(payload),
                return_json=True,
                retry_auth=True,
            )

            # 3. Report module data sent
            await self._request(
                "POST",
                "https://myindygo.com/module/reportModuleDataSent",
                headers=headers,
                data=json.dumps({"module": module_id}),
                return_json=True,
                retry_auth=True,
            )

            # 4. Report programs data sent
            programs_to_report = programs or (
                [full_program_data] if full_program_data else None
            )
            if programs_to_report:
                await self._report_programs_sent(module_id, programs_to_report, headers)

            # 5. Handle OFF mode remote control
            if full_program_data:
                await self._handle_off_mode_control(module_id, full_program_data)

            # 6. LoRaWAN Synchronization for V2 modules
            if (
                hasattr(self, "_data")
                and self._data
                and module_id in self._data.modules
                and self._data.modules[module_id].raw_data.get("typeIsLoraWanV2", False)
            ):
                await self.async_synchronize_lorawan(
                    module_id, send_program=True, send_command=True
                )
            else:
                LOGGER.debug("Skipping LoRaWAN sync for non-V2 module %s", module_id)

        except IndygoPoolApiClientError as exception:
            LOGGER.error("Failed to apply remote changes: %s", exception)

    async def async_send_remote_control(
        self,
        mode: str,
        module_serial: str | None = None,
        action: int = 1,
        **kwargs: Any,
    ) -> None:
        """Send an immediate remote control command to force relay activation.

        Args:
            mode: The mode to set ("on", "off", "auto").
            module_serial: The serial number of the module to control.
                If None, uses pool address.
            action: The action code (1=Stop, 3=Forced March).
            **kwargs: Additional parameters for the command (e.g. time, manualDuration).
        """
        serial = module_serial or self._pool_address
        if not serial:
            LOGGER.warning("Missing serial number, skipping immediate remote control")
            return

        # Investigation shows specific action codes are used for different commands.
        lines_control_item = {"index": 0, "mode": mode, "action": action}
        if kwargs:
            lines_control_item.update(kwargs)

        payload = {
            "moduleSerialNumber": serial,
            "linesControl": [lines_control_item],
        }

        LOGGER.debug("Sending remote control: %s", payload)

        await self._request(
            "POST",
            "https://myindygo.com/remote/module/control",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            return_json=True,
            retry_auth=True,
        )

    async def async_synchronize_lorawan(
        self, module_id: str, send_program: bool = True, send_command: bool = True
    ) -> None:
        """Trigger a LoRaWAN synchronization to push pending changes to the module.

        Args:
            module_id: The ID of the module to synchronize.
            send_program: Whether to push program updates.
            send_command: Whether to push manual command overrides.
        """
        url = "https://myindygo.com/modules/sendDataViaLoRaWAN"
        payload = {
            "moduleId": module_id,
            "sendProgram": send_program,
            "sendCommand": send_command,
        }

        LOGGER.debug("Triggering LoRaWAN sync: %s", payload)

        try:
            await self._request(
                "POST",
                url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                return_json=True,
                retry_auth=True,
            )
        except IndygoPoolApiClientError as exception:
            LOGGER.error("LoRaWAN sync failed: %s", exception)
            # We don't raise here as the preceding program update might have worked
            # and the device will eventually sync on its own.
