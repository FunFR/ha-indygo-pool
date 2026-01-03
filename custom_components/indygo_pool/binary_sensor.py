"""Binary sensor platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if not coordinator.data:
        return

    # Dynamic TOR sensors from modules
    if "modules" in coordinator.data:
        for module in coordinator.data["modules"]:
            if "inputs" in module:
                for sensor in module["inputs"]:
                    # check for TOR sensors
                    if sensor.get("typeIsTOR") is True:
                        entities.append(
                            IndygoPoolBinarySensor(
                                coordinator=coordinator,
                                sensor_data=sensor,
                                module_name=module.get("name", "Unknown Module"),
                            )
                        )

    # We could also add static sensors for Filtration/Electrolyser if we find
    # the correct flags in pool data
    # For now, relying on dynamic discovery for hardware sensors.

    async_add_entities(entities)


class IndygoPoolBinarySensor(IndygoPoolEntity, BinarySensorEntity):
    """Indygo Pool binary_sensor class."""

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

        # Determine device class
        # For Shutter/Volet:
        if "volet" in self._attr_name.lower():
            self._attr_device_class = (
                BinarySensorDeviceClass.WINDOW
            )  # Or GARAGE, or DOOR
        else:
            self._attr_device_class = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        # Find the sensor in the current data
        if "modules" in self.coordinator.data:
            for module in self.coordinator.data["modules"]:
                if "inputs" in module:
                    for sensor in module["inputs"]:
                        if sensor["id"] == self._sensor_id:
                            # Check for value or lastValue
                            val = None
                            if "value" in sensor:
                                val = sensor.get("value")
                            elif (
                                "lastValue" in sensor and "value" in sensor["lastValue"]
                            ):
                                val = sensor["lastValue"]["value"]

                            if val is None:
                                return None

                            # Logic: 1.0 = On?
                            # For Volet: 0.0 was observed when "Fermé".
                            # If Fermé -> Window is Closed -> is_on = False (usually).
                            # So 0.0 -> False. 1.0 -> True.
                            return float(val) == 1.0
        return None
