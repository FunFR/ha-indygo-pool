"""Sensor platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if not coordinator.data:
        return

    # Iterate over modules and their sensors
    if "modules" in coordinator.data:
        for module in coordinator.data["modules"]:
            if "inputs" in module:
                for sensor_data in module["inputs"]:
                    # Skip binary sensors (TOR)
                    if sensor_data.get("typeIsTOR") is True:
                        continue

                    entities.append(
                        IndygoPoolSensor(
                            coordinator=coordinator,
                            sensor_data=sensor_data,
                            module_name=module.get("name", "Unknown Module"),
                        )
                    )

    async_add_entities(entities)


class IndygoPoolSensor(IndygoPoolEntity, SensorEntity):
    """Indygo Pool Sensor class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        sensor_data: dict,
        module_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._sensor_id = sensor_data["id"]
        self._attr_unique_id = f"{sensor_data['id']}"
        sensor_name = (
            sensor_data.get("getName")
            or sensor_data.get("getEquipmentName")
            or "Unknown Sensor"
        )
        self._attr_name = f"{module_name} {sensor_name}"

        # Determine device class and unit
        name_lower = self._attr_name.lower()
        if (
            sensor_data.get("typeIsTemperatureSensor") is True
            or "tmperature" in name_lower
            or "thermom" in name_lower
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "ph" in name_lower:
            self._attr_device_class = getattr(SensorDeviceClass, "PH", None)
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "redox" in name_lower or "orp" in name_lower:
            self._attr_native_unit_of_measurement = "mV"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        # Add salt or others if needed
        elif "salt" in name_lower or "sel" in name_lower:
            self._attr_native_unit_of_measurement = "g/L"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        # Find the sensor in the current data
        if "modules" in self.coordinator.data:
            for module in self.coordinator.data["modules"]:
                if "inputs" in module:
                    for sensor in module["inputs"]:
                        if sensor["id"] == self._sensor_id:
                            # Value might be in 'value' or 'lastValue.value'
                            val = sensor.get("value")
                            if val is None and "lastValue" in sensor:
                                val = sensor["lastValue"].get("value")

                            if val is not None:
                                return val

                            # Fallback to pool data for temperature and pH
                            # if missing in module
                            pool_data = self.coordinator.data.get("pool", {})
                            if self._attr_device_class == SensorDeviceClass.TEMPERATURE:
                                return pool_data.get("temperature")
                            if self._attr_device_class == SensorDeviceClass.PH:
                                return pool_data.get("ph")

                            return None
        return None
