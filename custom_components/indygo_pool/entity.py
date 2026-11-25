"""IndygoPoolEntity class."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, LOGGER, NAME, VERSION
from .coordinator import IndygoPoolDataUpdateCoordinator
from .models import IndygoModuleData, IndygoPoolData


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
        self._module_id = module_id

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
            )
            # The parent pool device is registered during setup; without its
            # registry id the module device is left unlinked rather than
            # failing, since `via_device_id` must point at a known device.
            if coordinator.pool_device_id:
                self._attr_device_info["via_device_id"] = coordinator.pool_device_id
            else:
                LOGGER.debug(
                    "No pool device id available, leaving module %s unlinked",
                    module_id,
                )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._pool_unique_id)},
                name=pool_name,
                model=VERSION,
                manufacturer=NAME,
            )

        self._device_name_slug = slugify(self._attr_device_info["name"])

    @property
    def device_name_slug(self) -> str:
        """Return the device name slug."""
        return self._device_name_slug

    def _build_unique_id(self, key: str) -> str:
        """Build a unique ID from pool ID, optional module ID, and key."""
        if self._module_id:
            return f"{self._pool_unique_id}_{self._module_id}_{key}"
        return f"{self._pool_unique_id}_{key}"


def filtration_is_stopped(data: IndygoPoolData | None) -> bool:
    """Return True when the filtration pump is known to be stopped.

    The electrolyser only produces while water flows, so the MyIndygo app
    refuses to change it then.
    """
    if not data:
        return False
    for module in data.modules.values():
        if module.filtration_program:
            status = module.pool_status.get("0")
            return status is not None and status.value == 0
    return False


async def async_set_electrolyser(
    coordinator: IndygoPoolDataUpdateCoordinator,
    module: IndygoModuleData,
    settings: dict[str, Any],
) -> None:
    """Send electrolyser settings, refusing while the filtration is stopped."""
    output = module.electrolyser_output
    if output is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="electrolyser_not_found"
        )
    if filtration_is_stopped(coordinator.data):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="filtration_stopped"
        )
    await coordinator.client.async_set_ipx_data(str(output["id"]), settings)
