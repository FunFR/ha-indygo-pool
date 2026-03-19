"""Binary sensor platform for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity


@dataclass
class IndygoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Indygo Pool binary sensor entities."""

    sub_path: str | None = None
    is_pool_status: bool = False
    is_inverted: bool = False


BINARY_SENSOR_TYPES: tuple[IndygoBinarySensorEntityDescription, ...] = (
    IndygoBinarySensorEntityDescription(
        key="isOnline",
        translation_key="is_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="shutterEntry",
        translation_key="shutter",
        device_class=BinarySensorDeviceClass.WINDOW,
        sub_path="ipxData.deviceState",
        is_inverted=True,
    ),
    IndygoBinarySensorEntityDescription(
        key="flowEntry",
        translation_key="flow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="0",
        translation_key="filtration",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_pool_status=True,
    ),
)


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

    desc_map = {desc.key: desc for desc in BINARY_SENSOR_TYPES}

    for module_id, module in coordinator.data.modules.items():
        # General Module Sensors
        if "isOnline" in module.raw_data:
            entities.append(
                IndygoPoolBinarySensor(
                    coordinator=coordinator,
                    description=desc_map["isOnline"],
                    module_id=module_id,
                    module_name=module.type.upper() if module.type else "Unknown",
                )
            )

        # IPX Specific Sensors
        if module.type == "ipx" and "ipxData" in module.raw_data:
            ipx_data = module.raw_data["ipxData"]
            if "deviceState" in ipx_data:
                if "shutterEntry" in ipx_data["deviceState"]:
                    entities.append(
                        IndygoPoolBinarySensor(
                            coordinator=coordinator,
                            description=desc_map["shutterEntry"],
                            module_id=module_id,
                        )
                    )

                if "flowEntry" in ipx_data["deviceState"]:
                    entities.append(
                        IndygoPoolBinarySensor(
                            coordinator=coordinator,
                            description=desc_map["flowEntry"],
                            module_id=module_id,
                        )
                    )

    # Pool Status Sensors (Filtration, etc)
    for index, _ in coordinator.data.pool_status.items():
        if index == "0":
            entities.append(
                IndygoPoolBinarySensor(
                    coordinator=coordinator,
                    description=desc_map["0"],
                    module_id="pool_status",
                )
            )

    async_add_entities(entities)


class IndygoPoolBinarySensor(IndygoPoolEntity, BinarySensorEntity):
    """Indygo Pool binary_sensor class."""

    entity_description: IndygoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        description: IndygoBinarySensorEntityDescription,
        module_id: str,
        module_name: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._module_id = module_id

        if description.key == "isOnline" and module_name:
            self._attr_translation_placeholders = {"module": module_name}

        # Unique ID: ModuleID_Key
        pool_id = (
            coordinator.data.pool_id
            if coordinator.data and coordinator.data.pool_id
            else coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{pool_id}_{module_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        desc = self.entity_description

        if desc.is_pool_status:
            if desc.key in self.coordinator.data.pool_status:
                data = self.coordinator.data.pool_status[desc.key]
                val = data.value
                if val is not None:
                    try:
                        return float(val) == 1.0
                    except (ValueError, TypeError):
                        pass
            return None

        if self._module_id in self.coordinator.data.modules:
            module = self.coordinator.data.modules[self._module_id]
            target = module.raw_data

            if desc.sub_path:
                for path_part in desc.sub_path.split("."):
                    target = target.get(path_part, {})

            val = target.get(desc.key)

            if isinstance(val, bool):
                return not val if desc.is_inverted else val

            if val is not None:
                try:
                    is_true = float(val) == 1.0
                    return not is_true if desc.is_inverted else is_true
                except (ValueError, TypeError):
                    pass

        return None
