"""Sensor platform for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity
from .models import IndygoSensorData


@dataclass
class IndygoSensorEntityDescription(SensorEntityDescription):
    """Class describing Indygo Pool sensor entities."""


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

    # 1. Root Sensors
    for key, sensor_data in coordinator.data.sensors.items():
        description = IndygoSensorEntityDescription(
            key=key,
            name=sensor_data.name,
            native_unit_of_measurement=sensor_data.unit,
            device_class=sensor_data.device_class,
            state_class=SensorStateClass.MEASUREMENT if sensor_data.unit else None,
            entity_category=sensor_data.entity_category,
        )
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                description=description,
                sensor_data=sensor_data,
            )
        )

    # 2. Module Sensors
    for module_id, module in coordinator.data.modules.items():
        for key, sensor_data in module.sensors.items():
            # Naming: Indygo Pool {Module Name} {Sensor Name}
            # We use the module name in the Entity (init), here we just pass data
            description = IndygoSensorEntityDescription(
                key=key,
                name=sensor_data.name,
                native_unit_of_measurement=sensor_data.unit,
                device_class=sensor_data.device_class,
                state_class=SensorStateClass.MEASUREMENT if sensor_data.unit else None,
                entity_category=sensor_data.entity_category,
            )
            entities.append(
                IndygoPoolSensor(
                    coordinator=coordinator,
                    description=description,
                    sensor_data=sensor_data,
                    module_name=module.name,
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
        sensor_data: IndygoSensorData,
        module_name: str | None = None,
        module_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_key = sensor_data.key
        self._module_id = module_id

        # Unique ID strategy
        # Root: {pool_id}_{key}
        # Module: {pool_id}_{module_id}_{key}
        pool_id = (
            coordinator.data.pool_id
            if coordinator.data and coordinator.data.pool_id
            else coordinator.config_entry.entry_id
        )

        if module_id:
            self._attr_unique_id = f"{pool_id}_{module_id}_{self._sensor_key}"
            # Name: {Module} {Sensor} (Device name prepended automatically)
            self._attr_name = f"{module_name} {description.name}"
        else:
            self._attr_unique_id = f"{pool_id}_{self._sensor_key}"
            self._attr_name = f"{description.name}"

    @property
    def native_value(self) -> float | str | None:
        """Return the native value of the sensor."""
        # Fetch fresh data from coordinator
        data = self.coordinator.data
        if not data:
            return None

        # Try to find the sensor data again
        val = None

        if self._module_id:
            if self._module_id in data.modules:
                module = data.modules[self._module_id]
                if self._sensor_key in module.sensors:
                    val = module.sensors[self._sensor_key].value
        elif self._sensor_key in data.sensors:
            val = data.sensors[self._sensor_key].value

        return val
