"""Indygo Pool API Client."""

from __future__ import annotations

from playwright.async_api import Browser, Page, async_playwright

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
    ) -> None:
        """Initialize Indygo Pool API Client."""
        self._email = email
        self._password = password
        self._pool_id = pool_id
        self._browser: Browser | None = None

    async def async_get_data(self) -> dict:
        """Get data from the API using Playwright to execute JavaScript."""
        try:
            async with async_playwright() as p:
                # Launch browser in headless mode
                self._browser = await p.chromium.launch(headless=True)
                context = await self._browser.new_context()
                page = await context.new_page()

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
