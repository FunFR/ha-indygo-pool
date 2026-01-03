"""Config flow for Indygo Pool integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .api import (
    IndygoPoolApiClient,
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientCommunicationError,
    IndygoPoolApiClientError,
)
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_POOL_ID, DOMAIN, LOGGER


class IndygoPoolFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Indygo Pool."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    pool_id=user_input[CONF_POOL_ID],
                )
            except IndygoPoolApiClientAuthenticationError:
                LOGGER.exception("Authentication error during config flow")
                errors["base"] = "auth"
            except IndygoPoolApiClientCommunicationError:
                LOGGER.exception("Communication error during config flow")
                errors["base"] = "connection"
            except IndygoPoolApiClientError:
                LOGGER.exception("Unknown error during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_POOL_ID): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, email: str, password: str, pool_id: str) -> None:
        """Validate credentials."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)
        client = IndygoPoolApiClient(
            email=email,
            password=password,
            pool_id=pool_id,
            session=session,
        )
        # Test credentials by attempting to get data
        await client.async_get_data()
