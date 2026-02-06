"""Data models for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndygoSensorData:
    """Class representing a single sensor value."""

    key: str
    name: str | None = None
    value: float | str | None = None
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    entity_category: str | None = None
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
