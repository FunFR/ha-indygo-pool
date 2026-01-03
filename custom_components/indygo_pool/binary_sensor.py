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

    # Iterate over modules and add binary sensors based on flags
    if "modules" in coordinator.data:
        for module in coordinator.data["modules"]:
            module_name = module.get("name", "Unknown Module")

            # General Module Sensors
            for key, name, device_class in [
                ("isOnline", "Online", BinarySensorDeviceClass.CONNECTIVITY),
            ]:
                if key in module:
                    entities.append(
                        IndygoPoolBinarySensor(
                            coordinator=coordinator,
                            module=module,
                            key=key,
                            name=name,
                            device_class=device_class,
                        )
                    )

            # IPX Specific Sensors
            if module.get("type") == "ipx" and "ipxData" in module:
                ipx_data = module["ipxData"]
                if "deviceState" in ipx_data:
                    device_state = ipx_data["deviceState"]

                    # Shutter / Volet
                    if "shutterEntry" in device_state:
                        entities.append(
                            IndygoPoolBinarySensor(
                                coordinator=coordinator,
                                module=module,
                                key="shutterEntry",
                                name="Shutter",
                                device_class=BinarySensorDeviceClass.WINDOW,  # Open/Close
                                sub_path="ipxData.deviceState",
                            )
                        )

                    # Flow / Débit
                    if "flowEntry" in device_state:
                        entities.append(
                            IndygoPoolBinarySensor(
                                coordinator=coordinator,
                                module=module,
                                key="flowEntry",
                                name="Flow",
                                device_class=BinarySensorDeviceClass.PROBLEM,  # Problem if no flow? Or Moving?
                                # Usually flowEntry=False means NO flow? Need to verify logic.
                                # User dump: flowEntry: false.
                                sub_path="ipxData.deviceState",
                            )
                        )

    async_add_entities(entities)


class IndygoPoolBinarySensor(IndygoPoolEntity, BinarySensorEntity):
    """Indygo Pool binary_sensor class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module: dict,
        key: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        sub_path: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._module_id = module.get("id")
        self._key = key
        self._sub_path = sub_path

        # Unique ID: ModuleID_Key
        self._attr_unique_id = f"{self._module_id}_{key}"
        self._attr_name = f"{module.get('name')} {name}"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        # Find the module again to get fresh data
        if "modules" in self.coordinator.data:
            for module in self.coordinator.data["modules"]:
                if module.get("id") == self._module_id:
                    # Check if we need to traverse a subpath (e.g. ipxData.deviceState)
                    target = module
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
