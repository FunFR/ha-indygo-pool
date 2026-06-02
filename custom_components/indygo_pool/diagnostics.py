"""Diagnostics support for Indygo Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_CONFIG_TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}

# Keys containing personal information — replaced with **REDACTED**.
_RAW_TO_REDACT = frozenset(
    {
        "owner",
        "address",
        "latitude",
        "longitude",
        "macAddress",
        "uuid",
        "adminUsers",
        "garden",
        "locationKey",
        "simcard",
    }
)

# Bulky, location-revealing keys that obscure the useful data — dropped entirely.
_NOISE_KEYS = frozenset(
    {
        "addressWeather",
        "dailyWeatherForecast",
        "daylyWeatherForecast",
        "hourlyWeatherForecast",
        "weeklyWeatherForecast",
    }
)

# Extra keys to drop from pool_data.raw_data (already surfaced via "modules").
_RAW_STATUS_SKIP = _NOISE_KEYS | {"modules", "ipx_module", "professional", "agency"}


def _sanitize(raw: dict, skip: frozenset[str]) -> dict:
    return {k: v for k, v in raw.items() if k not in skip}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    client = coordinator.client
    pool_data = coordinator.data

    modules_info: list[dict[str, Any]] = []
    if pool_data:
        for module in pool_data.modules.values():
            raw = module.raw_data or {}
            modules_info.append(
                async_redact_data(_sanitize(raw, _NOISE_KEYS), _RAW_TO_REDACT)
                | {
                    "sensors": list(module.sensors.keys()),
                    "pool_status_circuits": list(module.pool_status.keys()),
                    "has_filtration_program": module.filtration_program is not None,
                }
            )

    raw_status: dict[str, Any] = {}
    if pool_data and pool_data.raw_data:
        raw_status = async_redact_data(
            _sanitize(pool_data.raw_data, _RAW_STATUS_SKIP),
            _RAW_TO_REDACT,
        )

    return {
        "config_entry": async_redact_data(dict(entry.data), _CONFIG_TO_REDACT),
        "hardware_ids": {
            "pool_address": client._pool_address,
            "device_short_id": client._device_short_id,
            "relay_id": client._relay_id,
        },
        "modules": modules_info,
        "root_sensors": list(pool_data.sensors.keys()) if pool_data else [],
        "root_pool_status_circuits": (
            list(pool_data.pool_status.keys()) if pool_data else []
        ),
        "raw_status": raw_status,
    }
