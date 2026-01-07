"""IndygoPoolEntity class."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import IndygoPoolDataUpdateCoordinator


class IndygoPoolEntity(CoordinatorEntity[IndygoPoolDataUpdateCoordinator]):
    """IndygoPoolEntity class."""

    _attr_attribution = "Data provided by MyIndygo"
    _attr_has_entity_name = True

    def __init__(self, coordinator: IndygoPoolDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        name = NAME
        if coordinator.data:
            if coordinator.data.pool_id:
                self._attr_unique_id = coordinator.data.pool_id
            else:
                self._attr_unique_id = coordinator.config_entry.entry_id

            name = f"{NAME} {self._attr_unique_id}"
        else:
            self._attr_unique_id = coordinator.config_entry.entry_id
            name = f"{NAME} {self._attr_unique_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=name,
            model=VERSION,
            manufacturer=NAME,
        )
