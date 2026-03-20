"""IndygoPoolEntity class."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, NAME, VERSION
from .coordinator import IndygoPoolDataUpdateCoordinator


class IndygoPoolEntity(CoordinatorEntity[IndygoPoolDataUpdateCoordinator]):
    """IndygoPoolEntity class."""

    _attr_attribution = "Data provided by MyIndygo"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        if coordinator.data and coordinator.data.pool_id:
            pool_id = coordinator.data.pool_id
        else:
            pool_id = coordinator.config_entry.entry_id

        self._pool_unique_id = pool_id
        pool_name = f"{NAME} {self._pool_unique_id[:8]}"

        if module_id and coordinator.data and module_id in coordinator.data.modules:
            module = coordinator.data.modules[module_id]
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{pool_id}_{module_id}")},
                name=module.name,
                model=module.type.upper() if module.type else "Unknown",
                manufacturer=NAME,
                via_device=(DOMAIN, self._pool_unique_id),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._pool_unique_id)},
                name=pool_name,
                model=VERSION,
                manufacturer=NAME,
            )

    @property
    def device_name_slug(self) -> str:
        """Return the device name slug."""
        if hasattr(self, "_attr_device_info") and self._attr_device_info:
            return slugify(self._attr_device_info["name"])
        return slugify(f"{NAME} {self._pool_unique_id[:8]}")
