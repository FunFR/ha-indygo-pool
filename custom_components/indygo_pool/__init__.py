"""Indygo Pool integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IndygoPoolApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_POOL_ID, DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indygo Pool from a config entry."""
    client = IndygoPoolApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        pool_id=entry.data.get(CONF_POOL_ID),
        session=async_get_clientsession(hass),
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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
