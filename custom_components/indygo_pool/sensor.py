"""Sensor platform for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity


@dataclass
class IndygoSensorEntityDescription(SensorEntityDescription):
    """Class describing Indygo Pool sensor entities."""


SENSOR_TYPES: tuple[IndygoSensorEntityDescription, ...] = (
    IndygoSensorEntityDescription(
        key="filtration_status",
        translation_key="filtration_status",
    ),
    IndygoSensorEntityDescription(
        key="temperature",
        translation_key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndygoSensorEntityDescription(
        key="totalElectrolyseDuration",
        translation_key="electrolyzer_duration",
        native_unit_of_measurement="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndygoSensorEntityDescription(
        key="ipx_salt",
        translation_key="ipx_salt",
        native_unit_of_measurement="g/L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndygoSensorEntityDescription(
        key="ph_setpoint",
        translation_key="ph_setpoint",
    ),
    IndygoSensorEntityDescription(
        key="production_setpoint",
        translation_key="production_setpoint",
        native_unit_of_measurement="%",
    ),
    IndygoSensorEntityDescription(
        key="electrolyzer_mode",
        translation_key="electrolyzer_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoSensorEntityDescription(
        key="ph",
        translation_key="ph",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[IndygoPoolSensor] = []

    if not coordinator.data:
        return

    desc_map = {desc.key: desc for desc in SENSOR_TYPES}

    # 1. Root Sensors
    for key, _ in coordinator.data.sensors.items():
        if key in desc_map:
            entities.append(
                IndygoPoolSensor(
                    coordinator=coordinator,
                    description=desc_map[key],
                )
            )

    # 2. Module Sensors
    for module_id, module in coordinator.data.modules.items():
        # Regular sensors
        for key in module.sensors:
            if key in desc_map:
                entities.append(
                    IndygoPoolSensor(
                        coordinator=coordinator,
                        description=desc_map[key],
                        module_id=module_id,
                    )
                )

        # Module-level status sensors (other than filtration_status)
        for index in module.pool_status:
            if index != "0" and index in desc_map:
                entities.append(
                    IndygoPoolSensor(
                        coordinator=coordinator,
                        description=desc_map[index],
                        module_id=module_id,
                    )
                )

    async_add_entities(entities)


class IndygoPoolSensor(IndygoPoolEntity, SensorEntity):
    """Indygo Pool Sensor class."""

    entity_description: IndygoSensorEntityDescription

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        description: IndygoSensorEntityDescription,
        module_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self.entity_description = description
        self._sensor_key = description.key
        self._module_id = module_id

        # Unique ID: PoolID_ModuleID_Key
        self._attr_unique_id = (
            f"{self._pool_unique_id}_{module_id}_{self._sensor_key}"
            if module_id
            else f"{self._pool_unique_id}_{self._sensor_key}"
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the native value of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        if self._module_id and self._module_id in data.modules:
            module = data.modules[self._module_id]
            if self._sensor_key in module.sensors:
                return module.sensors[self._sensor_key].value

        if self._sensor_key in data.sensors:
            return data.sensors[self._sensor_key].value

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        data = self.coordinator.data
        if not data:
            return None

        if self._module_id:
            if self._module_id in data.modules:
                module = data.modules[self._module_id]
                if self._sensor_key in module.sensors:
                    return module.sensors[self._sensor_key].extra_attributes
        elif self._sensor_key in data.sensors:
            return data.sensors[self._sensor_key].extra_attributes

        return None
