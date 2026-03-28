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
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity
from .models import IndygoSensorData


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
        native_unit_of_measurement=UnitOfTime.HOURS,
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
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
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
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    IndygoSensorEntityDescription(
        key="filtration_remaining_time",
        translation_key="filtration_remaining_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
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
        self._attr_unique_id = self._build_unique_id(description.key)
        self.entity_id = (
            f"sensor.{self.device_name_slug}_{slugify(description.translation_key)}"
        )

    def _get_sensor_data(self) -> IndygoSensorData | None:
        """Resolve the sensor data from module or root sensors."""
        data = self.coordinator.data
        if not data:
            return None
        key = self.entity_description.key
        if self._module_id and self._module_id in data.modules:
            sensor = data.modules[self._module_id].sensors.get(key)
            if sensor:
                return sensor
        return data.sensors.get(key)

    @property
    def native_value(self) -> float | str | None:
        """Return the native value of the sensor."""
        sensor = self._get_sensor_data()
        return sensor.value if sensor else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        sensor = self._get_sensor_data()
        return sensor.extra_attributes if sensor else None
