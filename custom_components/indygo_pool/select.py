"""Select platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity
from .models import IndygoModuleData

# Mapping: Mode -> Integer
MODE_OFF = "Off"
MODE_ON = "On"
MODE_AUTO = "Auto"

MODE_TO_INT = {
    MODE_OFF: 0,
    MODE_ON: 1,
    MODE_AUTO: 2,
}

INT_TO_MODE = {v: k for k, v in MODE_TO_INT.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[IndygoPoolSelect] = []

    if not coordinator.data:
        return

    # Check modules for filtration program
    for module_id, module in coordinator.data.modules.items():
        if module.filtration_program:
            entities.append(
                IndygoPoolSelect(
                    coordinator=coordinator,
                    module_id=module_id,
                    module_name=module.name,
                )
            )

    async_add_entities(entities)


class IndygoPoolSelect(IndygoPoolEntity, SelectEntity):
    """Indygo Pool Filtration Mode Select class."""

    _attr_options = [MODE_OFF, MODE_ON, MODE_AUTO]
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._module_id = module_id
        pool_id = (
            coordinator.data.pool_id
            if coordinator.data and coordinator.data.pool_id
            else coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{pool_id}_{module_id}_filtration_mode"
        self._attr_name = f"{module_name} Filtration Mode"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        data = self.coordinator.data
        if not data or self._module_id not in data.modules:
            return None

        module: IndygoModuleData = data.modules[self._module_id]
        if not module.filtration_program:
            return None

        mode = module.filtration_program.get("programCharacteristics", {}).get("mode")

        return INT_TO_MODE.get(mode)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        data = self.coordinator.data
        if not data or self._module_id not in data.modules:
            LOGGER.error("Cannot set mode: Module %s not found", self._module_id)
            return

        module: IndygoModuleData = data.modules[self._module_id]
        if not module.filtration_program:
            LOGGER.error(
                "Cannot set mode: Filtration program not found for module %s",
                self._module_id,
            )
            return

        mode_int = MODE_TO_INT.get(option)
        if mode_int is None:
            LOGGER.error("Invalid option selected: %s", option)
            return

        # Perform the update
        await self.coordinator.client.async_set_filtration_mode(
            self._module_id, module.filtration_program, mode_int
        )

        # Trigger refresh
        await self.coordinator.async_request_refresh()
