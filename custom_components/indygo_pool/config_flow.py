"""Config flow for Indygo Pool integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import (
    IndygoPoolApiClient,
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientCommunicationError,
    IndygoPoolApiClientError,
)
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)


class IndygoPoolFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Indygo Pool."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_POOL_ID])
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_credentials(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                pool_id=user_input[CONF_POOL_ID],
            )
            if not errors:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication triggered by an authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self._async_validate_credentials(
                email=reauth_entry.data[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                pool_id=reauth_entry.data[CONF_POOL_ID],
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of email, password or pool ID."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            new_pool_id = user_input[CONF_POOL_ID]
            if new_pool_id != entry.unique_id and any(
                other.entry_id != entry.entry_id and other.unique_id == new_pool_id
                for other in self._async_current_entries()
            ):
                errors["base"] = "already_configured"
            else:
                errors = await self._async_validate_credentials(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    pool_id=new_pool_id,
                )
                if not errors:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=new_pool_id,
                        title=user_input[CONF_EMAIL],
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=entry.data[CONF_EMAIL]): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_POOL_ID, default=entry.data[CONF_POOL_ID]): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate_credentials(
        self, email: str, password: str, pool_id: str
    ) -> dict[str, str]:
        """Validate credentials against the MyIndygo API, returning any errors."""
        errors: dict[str, str] = {}
        try:
            await self._test_credentials(
                email=email, password=password, pool_id=pool_id
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
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors

    async def _test_credentials(self, email: str, password: str, pool_id: str) -> None:
        """Validate credentials."""
        session = async_create_clientsession(self.hass)

        client = IndygoPoolApiClient(
            email=email,
            password=password,
            pool_id=pool_id,
            session=session,
        )
        # Test credentials by attempting to get data
        await client.async_get_data()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IndygoPoolOptionsFlowHandler:
        """Get the options flow for this handler."""
        return IndygoPoolOptionsFlowHandler()


class IndygoPoolOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle Indygo Pool options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the polling interval option."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=60,
                            max=3600,
                            step=30,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
