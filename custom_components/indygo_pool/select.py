"""Select platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    LOGGER,
    ON_SPEED_FIELD,
    PROGRAM_RULE_SCHEDULE,
    PROGRAM_RULE_THERMO_ADAPTIVE,
    PROGRAM_RULE_VARIABLE_SPEED,
    PUMP_SPEED_STATES,
    RULE_FIELD,
    VARIABLE_SPEED_FIELD,
)
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity
from .models import IndygoModuleData

# Delay (seconds) before a follow-up refresh after a mode change.
# The command travels cloud → gateway → LoRa → device, so the status
# endpoint may still return the old state right after the API call.
DELAYED_REFRESH_SECONDS = 10

# Mapping: Mode -> Integer
MODE_OFF = "Off"
MODE_ON = "On"
MODE_AUTO = "Auto"

MODE_TO_INT = {
    MODE_OFF: 0,
    MODE_ON: 1,
    MODE_AUTO: 2,
}

# programCharacteristics.defaultProgramSpeed / onSpeed of variable-speed pumps.
SPEED_TO_INT = {state: speed for speed, state in PUMP_SPEED_STATES.items() if speed}

MANAGEMENT_TO_INT = {
    "schedule": PROGRAM_RULE_SCHEDULE,
    "thermo_adaptive": PROGRAM_RULE_THERMO_ADAPTIVE,
    "variable_speed": PROGRAM_RULE_VARIABLE_SPEED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[IndygoPoolProgramSelect] = []

    if not coordinator.data:
        return

    for module_id, module in coordinator.data.modules.items():
        if not module.filtration_program:
            continue
        entity_classes: list[type[IndygoPoolProgramSelect]] = [
            IndygoPoolFiltrationModeSelect
        ]
        if module.has_variable_speed:
            entity_classes += [IndygoPoolSpeedSelect, IndygoPoolManagementSelect]
        entities.extend(
            entity_class(coordinator, module_id, module.name)
            for entity_class in entity_classes
        )

    async_add_entities(entities)


class IndygoPoolProgramSelect(IndygoPoolEntity, SelectEntity):
    """Select writing fields of the filtration program characteristics."""

    _key: str
    _option_to_int: dict[str, int]
    # Characteristics written with the selected value; the first one is read.
    _fields: tuple[str, ...]
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self._attr_options = list(self._option_to_int)
        self._attr_translation_key = self._key
        self._attr_unique_id = self._build_unique_id(self._key)
        self.entity_id = f"select.{self.device_name_slug}_{self._key}"
        self._cancel_delayed_refresh: CALLBACK_TYPE | None = None

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        data = self.coordinator.data
        if not data or self._module_id not in data.modules:
            return None

        module: IndygoModuleData = data.modules[self._module_id]
        if not module.filtration_program:
            return None

        value = module.filtration_program.get("programCharacteristics", {}).get(
            self._fields[0]
        )
        return next(
            (opt for opt, val in self._option_to_int.items() if val == value), None
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        data = self.coordinator.data
        if not data or self._module_id not in data.modules:
            LOGGER.error(
                "Cannot set %s: Module %s not found", self._key, self._module_id
            )
            return

        module: IndygoModuleData = data.modules[self._module_id]
        if not module.filtration_program:
            LOGGER.error(
                "Cannot set %s: Filtration program not found for module %s",
                self._key,
                self._module_id,
            )
            return

        value = self._option_to_int.get(option)
        if value is None:
            LOGGER.error("Invalid option selected: %s", option)
            return

        await self.coordinator.client.async_update_program_characteristics(
            self._module_id,
            module.filtration_program,
            **dict.fromkeys(self._fields, value),
        )

        # Trigger immediate refresh
        await self.coordinator.async_request_refresh()

        # Schedule a delayed refresh to capture the device state after
        # the command has propagated through cloud → gateway → LoRa.
        self._schedule_delayed_refresh()

    @callback
    def _schedule_delayed_refresh(self) -> None:
        """Schedule a coordinator refresh after a delay."""
        if self._cancel_delayed_refresh:
            self._cancel_delayed_refresh()

        self._cancel_delayed_refresh = async_call_later(
            self.hass,
            DELAYED_REFRESH_SECONDS,
            self._delayed_refresh_callback,
        )

    @callback
    def _delayed_refresh_callback(self, _now: object) -> None:
        """Fire the delayed coordinator refresh.

        Invoked by ``async_call_later`` in the event loop, so it stays
        synchronous and hands the awaitable work to a task.
        """
        self._cancel_delayed_refresh = None
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending delayed refresh when the entity goes away.

        Without this, unloading or reloading the integration during the
        delay window leaves the timer armed and it fires on a dead entity.
        """
        if self._cancel_delayed_refresh:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None
        await super().async_will_remove_from_hass()


class IndygoPoolFiltrationModeSelect(IndygoPoolProgramSelect):
    """Filtration mode (Off/On/Auto)."""

    _key = "filtration_mode"
    _option_to_int = MODE_TO_INT
    _fields = ("mode",)


class IndygoPoolSpeedSelect(IndygoPoolProgramSelect):
    """Configured speed of a variable-speed pump.

    The vendor app always writes both speed fields together, so does this.
    """

    _key = "filtration_speed"
    _option_to_int = SPEED_TO_INT
    _fields = (VARIABLE_SPEED_FIELD, ON_SPEED_FIELD)
    _attr_icon = "mdi:speedometer"


class IndygoPoolManagementSelect(IndygoPoolProgramSelect):
    """Management type (rule) of a variable-speed pump."""

    _key = "filtration_management"
    _option_to_int = MANAGEMENT_TO_INT
    _fields = (RULE_FIELD,)
    _attr_icon = "mdi:calendar-clock"
