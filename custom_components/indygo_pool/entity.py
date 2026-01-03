"""IndygoPoolEntity class."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME, VERSION
from .coordinator import IndygoPoolDataUpdateCoordinator


class IndygoPoolEntity(CoordinatorEntity[IndygoPoolDataUpdateCoordinator]):
    """IndygoPoolEntity class."""

    _attr_attribution = "Data provided by MyIndygo"

    def __init__(self, coordinator: IndygoPoolDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=NAME,
            model=VERSION,
            manufacturer=NAME,
        )
