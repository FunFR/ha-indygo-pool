"""Indygo Pool API Client."""

from __future__ import annotations

import socket

import aiohttp
import async_timeout
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

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
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

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
        """Get data from the API using Playwright to execute JavaScript."""
        if not self._pool_id:
            raise IndygoPoolApiClientError("Pool ID is required")

        try:
            async with async_playwright() as p:
                # Launch browser in headless mode
                self._browser = await p.chromium.launch(headless=True)
                self._context = await self._browser.new_context()
                page = await self._context.new_page()

                # Navigate to login page
                await page.goto("https://myindygo.com/login")

                # Fill in login form
                await page.fill('input[name="email"]', self._email)
                await page.fill('input[name="password"]', self._password)

                # Submit form and wait for navigation
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle")

                # Navigate to devices page
                await page.goto(f"https://myindygo.com/pools/{self._pool_id}/devices")

                # Wait for JavaScript to load the data
                await page.wait_for_load_state("networkidle")

                # Give extra time for JavaScript execution
                await page.wait_for_timeout(2000)

                # Extract JavaScript variables from the page
                data = await self._extract_data_from_page(page)

                await self._browser.close()
                return data

        except Exception as exception:
            LOGGER.error("Failed to get data with Playwright: %s", exception)
            if self._browser:
                await self._browser.close()
            raise IndygoPoolApiClientError(
                f"Failed to retrieve pool data: {exception}"
            ) from exception

    async def _extract_data_from_page(self, page: Page) -> dict:
        """Extract pool, modules, and poolCommand from the page's JavaScript context."""
        try:
            # Extract the JavaScript variables directly from the page context
            pool_data = await page.evaluate(
                "() => typeof pool !== 'undefined' ? pool : null"
            )
            modules_data = await page.evaluate(
                "() => typeof modules !== 'undefined' ? modules : null"
            )
            pool_command_data = await page.evaluate(
                "() => typeof poolCommand !== 'undefined' ? poolCommand : null"
            )

            data = {}

            if pool_data:
                data["pool"] = pool_data
                LOGGER.debug("Successfully extracted pool data")
            else:
                LOGGER.warning("pool variable not found in page context")

            if modules_data:
                data["modules"] = modules_data
                LOGGER.debug(
                    "Successfully extracted modules data: %d modules", len(modules_data)
                )
            else:
                LOGGER.warning("modules variable not found in page context")

            if pool_command_data:
                data["poolCommand"] = pool_command_data
                LOGGER.debug("Successfully extracted poolCommand data")
            else:
                LOGGER.warning("poolCommand variable not found in page context")

            if not data:
                raise IndygoPoolApiClientError("Could not find pool data in the page")

            return data

        except Exception as e:
            LOGGER.error("Error extracting data from page: %s", e)
            raise IndygoPoolApiClientError(f"Failed to extract data: {e}") from e

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
