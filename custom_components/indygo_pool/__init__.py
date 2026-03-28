"""Indygo Pool integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .api import IndygoPoolApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_POOL_ID, DOMAIN, NAME, VERSION
from .coordinator import IndygoPoolDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indygo Pool from a config entry."""
    session = async_create_clientsession(hass)

    client = IndygoPoolApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        pool_id=entry.data.get(CONF_POOL_ID),
        session=session,
    )

    coordinator = IndygoPoolDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Register the parent pool device before platform setup so that
    # module devices can reference it via `via_device` without errors.
    if coordinator.data and coordinator.data.pool_id:
        pool_id = coordinator.data.pool_id
        device_reg = dr.async_get(hass)
        device_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            **DeviceInfo(
                identifiers={(DOMAIN, pool_id)},
                name=f"{NAME} {pool_id[:8]}",
                model=VERSION,
                manufacturer=NAME,
            ),
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
