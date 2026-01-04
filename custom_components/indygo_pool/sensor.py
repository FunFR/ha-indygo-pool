"""Sensor platform for Indygo Pool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry

try:
    from homeassistant.const import EntityCategory
except ImportError:
    from homeassistant.helpers.entity import EntityCategory

try:
    from homeassistant.const import UnitOfTemperature
except ImportError:
    # Fallback for older HA versions
    class UnitOfTemperature:
        CELSIUS = "°C"
        FAHRENHEIT = "°F"
        KELVIN = "K"


from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity


async def async_setup_entry(  # noqa: PLR0912
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if not coordinator.data:
        return

    # Check for root-level sensors in the pool data
    data = coordinator.data

    # Device Temperature (Internal)
    if "temperature" in data and data["temperature"] is not None:
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="temperature",
                name="Device Temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.CELSIUS,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )

    # pH
    if "ph" in data and data["ph"] is not None:
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="ph",
                name="ph",
                device_class=SensorDeviceClass.PH,
                unit=None,  # PH has no unit
            )
        )

    # ORP / Redox (Check if 'redox' or 'orp' key exists)
    for key, name, unit, device_class in [
        ("redox", "Redox", "mV", None),
        ("orp", "ORP", "mV", None),
        ("salt", "Salt", "g/L", None),
        ("chlorineRate", "Chlorine", "ppm", None),
    ]:
        if key in data and data[key] is not None:
            entities.append(
                IndygoPoolSensor(
                    coordinator=coordinator,
                    key=key,
                    name=name,
                    device_class=device_class,
                    unit=unit,
                )
            )

    # Generic Sensors from sensorState map
    # User confirmed Index 0 is Water Temperature (724 -> 7.24)
    if "sensorState" in data and isinstance(data["sensorState"], list):
        for sensor_item in data["sensorState"]:
            idx = sensor_item.get("index")
            if idx is not None:
                if idx == 0:
                    # Water Temperature
                    entities.append(
                        IndygoPoolSensor(
                            coordinator=coordinator,
                            key=f"sensorState_{idx}",
                            name="Water Temperature",
                            device_class=SensorDeviceClass.TEMPERATURE,
                            unit=UnitOfTemperature.CELSIUS,
                            json_path=f"sensorState.{idx}",
                            converter=lambda x: x / 100.0 if x is not None else None,
                        )
                    )
                else:
                    # Generic fallback - REMOVED per user request
                    pass

    # Sensors from IPX Modules (Electrolysis, etc.)
    if "modules" in data:
        for module in data["modules"]:
            if module.get("type") == "ipx" and "ipxData" in module:
                ipx_data = module["ipxData"]
                module_name = module.get("name", "IPX")

                # Total Electrolyse Duration
                if "totalElectrolyseDuration" in ipx_data:
                    entities.append(
                        IndygoPoolSensor(
                            coordinator=coordinator,
                            key="totalElectrolyseDuration",
                            name=f"{module_name} Electrolyse Duration",
                            device_class=None,
                            unit="h",
                            entity_category=EntityCategory.DIAGNOSTIC,
                            module_id=module.get("id"),
                            json_path="ipxData.totalElectrolyseDuration",
                        )
                    )

    # Sensors from ipx_module (Scraped from Discovery)
    if "ipx_module" in data:
        # Salt Value (outputs[1].ipxData.saltValue) - Usually Station 2
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="saltValue",
                name="Salt Level",
                device_class=None,
                unit="g/L",
                json_path="ipx_module.outputs.1.ipxData.saltValue",
            )
        )

        # pH Setpoint (outputs[0].ipxData.pHSetpoint) - Station 1
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="pHSetpoint",
                name="pH Setpoint",
                device_class=None,
                unit=None,  # pH has no unit
                entity_category=EntityCategory.DIAGNOSTIC,
                json_path="ipx_module.outputs.0.ipxData.pHSetpoint",
            )
        )

        # Production Setpoint (outputs[1].ipxData.percentageSetpoint)
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="percentageSetpoint",
                name="Production Setpoint",
                device_class=None,
                unit="%",
                entity_category=EntityCategory.DIAGNOSTIC,
                json_path="ipx_module.outputs.1.ipxData.percentageSetpoint",
            )
        )

        # Electrolyzer Mode
        # 1 = Comfort?
        entities.append(
            IndygoPoolSensor(
                coordinator=coordinator,
                key="electrolyzerMode",
                name="Electrolyzer Mode",
                device_class=None,
                unit=None,
                entity_category=EntityCategory.DIAGNOSTIC,
                json_path="ipx_module.outputs.1.ipxData.electrolyzerMode",
            )
        )

    async_add_entities(entities)


class IndygoPoolSensor(IndygoPoolEntity, SensorEntity):
    """Indygo Pool Sensor class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        json_path: str | None = None,
        entity_category: EntityCategory | None = None,
        converter: Callable[[Any], Any] | None = None,
        module_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._key = key
        self._json_path = json_path
        self._converter = converter
        self._module_id = module_id
        # Use simple ID based on key since there's one pool
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        if module_id:
            self._attr_unique_id = f"{module_id}_{key}"

        self._attr_name = f"Indygo {name}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        if entity_category:
            self._attr_entity_category = entity_category

    @property
    def native_value(self) -> float | None:  # noqa: PLR0912
        """Return the native value of the sensor."""
        val = None

        if self._module_id and "modules" in self.coordinator.data:
            # Find module and get data
            for module in self.coordinator.data["modules"]:
                if module.get("id") == self._module_id:
                    target = module
                    # Traverse path if provided
                    if self._json_path:
                        for path_part in self._json_path.split("."):
                            if isinstance(target, dict):
                                target = target.get(path_part, {})
                            else:
                                target = {}
                                break

                    if (
                        isinstance(target, dict) and self._key in target
                    ):  # If path led to dict containing key
                        val = target[self._key]
                    elif not isinstance(target, dict):
                        # If path led to value directly
                        val = target

                    # Simpler Logic:
                    # 1. Start at module
                    # 2. If json_path, follow it.
                    # 3. If result is the value, done.
                    # 4. If result is dict, look for key?

                    t = module
                    if self._json_path:
                        for part in self._json_path.split("."):
                            t = t.get(part, {})

                    # If we found something relevant (not empty dict fallback)
                    if t != {}:
                        val = t
                    break

        elif self._json_path:
            # Handle "sensorState.0" style paths special case
            if self._json_path.startswith("sensorState."):
                try:
                    idx = int(self._json_path.split(".")[1])
                    states = self.coordinator.data.get("sensorState", [])
                    matches = [s for s in states if s.get("index") == idx]
                    if matches:
                        val = matches[0].get("value")
                except (ValueError, IndexError, TypeError):
                    pass
            else:
                # Generic path traversal from root data
                # e.g. "ipx_module.outputs.1.ipxData.saltValue"
                target = self.coordinator.data
                try:
                    for part in self._json_path.split("."):
                        if isinstance(target, dict):
                            target = target.get(part)
                        elif isinstance(target, list):
                            target = target[int(part)]
                        else:
                            target = None
                            break

                        if target is None:
                            break

                    if target is not None:
                        val = target
                except (ValueError, IndexError, TypeError):
                    pass
        else:
            # Use the key to fetch from root data
            val = self.coordinator.data.get(self._key)

        if self._converter and val is not None:
            return self._converter(val)
        return val
