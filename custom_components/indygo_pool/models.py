"""Data models for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import VARIABLE_SPEED_MODULE_PREFIX


@dataclass
class IndygoSensorData:
    """Class representing a single sensor value."""

    key: str
    value: float | str | None = None
    extra_attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndygoModuleData:
    """Class representing a module (e.g., IPX, Gateway)."""

    id: str
    type: str
    name: str
    sensors: dict[str, IndygoSensorData] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)
    programs: list[dict[str, Any]] = field(default_factory=list)
    filtration_program: dict[str, Any] | None = None
    pool_status: dict[str, IndygoSensorData] = field(default_factory=dict)

    @property
    def has_variable_speed(self) -> bool:
        """Return True when the filtration pump runs at variable speed."""
        return self.type.startswith(VARIABLE_SPEED_MODULE_PREFIX)


@dataclass
class IndygoPoolData:
    """Class representing the aggregated pool data."""

    pool_id: str
    address: str | None = None
    relay_id: str | None = None

    # Root level sensors (temperature, pH, ORP, etc.)
    sensors: dict[str, IndygoSensorData] = field(default_factory=dict)

    # Modules found attached to the pool
    modules: dict[str, IndygoModuleData] = field(default_factory=dict)

    # Raw data for fallback/diagnostics
    raw_data: dict[str, Any] = field(default_factory=dict)

    # Pool Status Items (from 'pool' list in JSON)
    # Key = index (e.g. "0" for filtration), Value = IndygoSensorData
    pool_status: dict[str, IndygoSensorData] = field(default_factory=dict)
