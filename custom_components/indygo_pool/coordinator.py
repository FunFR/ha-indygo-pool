"""DataUpdateCoordinator for Indygo Pool."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    IndygoPoolApiClient,
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientError,
)
from .const import DOMAIN, LOGGER


class IndygoPoolDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Indygo Pool data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: IndygoPoolApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            return await self.client.async_get_data()
        except IndygoPoolApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except IndygoPoolApiClientError as exception:
            raise UpdateFailed(exception) from exception
