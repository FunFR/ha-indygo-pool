"""Binary sensor platform for Indygo Pool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

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
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="shutterEntry",
        translation_key="shutter",
        name="Shutter",
        device_class=BinarySensorDeviceClass.WINDOW,
        sub_path="ipxData.deviceState",
        is_inverted=True,
    ),
    IndygoBinarySensorEntityDescription(
        key="flowEntry",
        translation_key="flow",
        name="Flow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="cmdEntry",
        translation_key="cmd_entry",
        name="Command",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="canPhEntry",
        translation_key="can_ph_entry",
        name="pH entry",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="boostEnabled",
        translation_key="boost_enabled",
        name="Boost",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="testProd",
        translation_key="test_prod",
        name="Test production",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="pHInjection",
        translation_key="ph_injection",
        name="pH injection",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="cellPolaruty",
        translation_key="cell_polarity",
        name="Cell polarity",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="prodStatus",
        translation_key="production_status",
        name="Production status",
        sub_path="ipxData.deviceState",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndygoBinarySensorEntityDescription(
        key="0",
        translation_key="filtration",
        name="Filtration",
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
                device_state = ipx_data["deviceState"]
                for key in device_state:
                    if (
                        key in desc_map
                        and desc_map[key].sub_path == "ipxData.deviceState"
                    ):
                        entities.append(
                            IndygoPoolBinarySensor(
                                coordinator=coordinator,
                                description=desc_map[key],
                                module_id=module_id,
                            )
                        )

        # Module-level status sensors (Filtration, etc)
        for index in module.pool_status:
            if index == "0":
                entities.append(
                    IndygoPoolBinarySensor(
                        coordinator=coordinator,
                        description=desc_map["0"],
                        module_id=module_id,
                    )
                )

    # Root Level Pool Status Sensors (Fallback if not moved to module)
    for index in coordinator.data.pool_status:
        if index == "0":
            entities.append(
                IndygoPoolBinarySensor(
                    coordinator=coordinator,
                    description=desc_map["0"],
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
        module_id: str | None = None,
        module_name: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self.entity_description = description
        self._module_id = module_id

        if description.key == "isOnline" and module_name:
            self._attr_translation_placeholders = {"module": module_name}

        # Unique ID: PoolID_ModuleID_Key
        self._attr_unique_id = (
            f"{self._pool_unique_id}_{module_id}_{description.key}"
            if module_id
            else f"{self._pool_unique_id}_{description.key}"
        )

        # Force English entity_id
        suffix = slugify(description.translation_key)
        self.entity_id = f"binary_sensor.{self.device_name_slug}_{suffix}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        desc = self.entity_description

        if desc.is_pool_status:
            target_status = self.coordinator.data.pool_status
            if self._module_id and self._module_id in self.coordinator.data.modules:
                target_status = self.coordinator.data.modules[
                    self._module_id
                ].pool_status

            if desc.key in target_status:
                data = target_status[desc.key]
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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        desc = self.entity_description
        if desc.is_pool_status:
            target_status = self.coordinator.data.pool_status
            if self._module_id and self._module_id in self.coordinator.data.modules:
                target_status = self.coordinator.data.modules[
                    self._module_id
                ].pool_status

            if desc.key in target_status:
                return target_status[desc.key].extra_attributes
        return None
