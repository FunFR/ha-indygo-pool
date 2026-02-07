"""Indygo Pool integration."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import IndygoPoolApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_POOL_ID, DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indygo Pool from a config entry."""
    # Create a dedicated session with cookie jar for authentication
    # unsafe=True allows cookies from all domains (required for cross-domain auth)
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=cookie_jar)

    client = IndygoPoolApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        pool_id=entry.data.get(CONF_POOL_ID),
        session=session,
    )

    coordinator = IndygoPoolDataUpdateCoordinator(
        hass=hass,
        client=client,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # Close the dedicated session
        await coordinator.client._session.close()

    return unload_ok
