"""Binary sensor platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[IndygoPoolBinarySensor] = []

    if not coordinator.data:
        return

    # Iterate over modules and add binary sensors based on flags
    # Using modules dict from IndygoPoolData
    for module_id, module in coordinator.data.modules.items():
        # General Module Sensors from raw_data
        if "isOnline" in module.raw_data:
            entities.append(
                IndygoPoolBinarySensor(
                    coordinator=coordinator,
                    module_id=module_id,
                    module_name=module.name,
                    raw_data_source=module.raw_data,
                    key="isOnline",
                    name="Online",
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                )
            )

        # IPX Specific Sensors
        if module.type == "ipx" and "ipxData" in module.raw_data:
            ipx_data = module.raw_data["ipxData"]
            if "deviceState" in ipx_data:
                # Shutter / Volet
                if "shutterEntry" in ipx_data["deviceState"]:
                    entities.append(
                        IndygoPoolBinarySensor(
                            coordinator=coordinator,
                            module_id=module_id,
                            module_name=module.name,
                            raw_data_source=module.raw_data,
                            key="shutterEntry",
                            name="Shutter",
                            device_class=BinarySensorDeviceClass.WINDOW,
                            sub_path="ipxData.deviceState",
                        )
                    )

                # Flow / Débit
                if "flowEntry" in ipx_data["deviceState"]:
                    entities.append(
                        IndygoPoolBinarySensor(
                            coordinator=coordinator,
                            module_id=module_id,
                            module_name=module.name,
                            raw_data_source=module.raw_data,
                            key="flowEntry",
                            name="Flow",
                            device_class=BinarySensorDeviceClass.PROBLEM,
                            sub_path="ipxData.deviceState",
                            entity_category=EntityCategory.DIAGNOSTIC,
                        )
                    )

    # Pool Status Sensors (Filtration, etc)
    for index, sensor_data in coordinator.data.pool_status.items():
        if index == "0":
            entities.append(
                IndygoPoolBinarySensor(
                    coordinator=coordinator,
                    module_id="pool_status",
                    module_name="Pool",
                    raw_data_source={},  # Not used for pool_status strategy
                    key=index,
                    name=sensor_data.name or "Filtration",
                    device_class=BinarySensorDeviceClass.RUNNING,
                    is_pool_status=True,
                )
            )

    async_add_entities(entities)


class IndygoPoolBinarySensor(IndygoPoolEntity, BinarySensorEntity):
    """Indygo Pool binary_sensor class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
        raw_data_source: dict,
        key: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        sub_path: str | None = None,
        entity_category: EntityCategory | None = None,
        is_pool_status: bool = False,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._module_id = module_id
        self._key = key
        self._sub_path = sub_path
        self._is_pool_status = is_pool_status

        # Unique ID: ModuleID_Key
        # Use config entry id prefix for safety?
        # Current logic: {module_id}_{key}
        # Updated logic to match sensor.py: {entry_id}_{module_id}_{key}
        pool_id = (
            coordinator.data.pool_id
            if coordinator.data and coordinator.data.pool_id
            else coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{pool_id}_{module_id}_{key}"

        # Name: {Module} {Sensor} (Device name prepended automatically)
        self._attr_name = f"{module_name} {name}"
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        # Special handling for pool_status items
        if self._is_pool_status:
            if self._key in self.coordinator.data.pool_status:
                data = self.coordinator.data.pool_status[self._key]
                val = data.value
                if val is not None:
                    try:
                        return float(val) == 1.0
                    except (ValueError, TypeError):
                        pass
            return None

        # Find the module again to get fresh data
        # Note: We can't hold reference to raw_data_source as it won't update
        if self._module_id in self.coordinator.data.modules:
            module = self.coordinator.data.modules[self._module_id]
            target = module.raw_data

            if self._sub_path:
                for path_part in self._sub_path.split("."):
                    target = target.get(path_part, {})

            val = target.get(self._key)

            # Handle boolean directly
            if isinstance(val, bool):
                return val

            # Handle numbers (1.0 = True?)
            if val is not None:
                try:
                    return float(val) == 1.0
                except (ValueError, TypeError):
                    pass

            return None
        return None
