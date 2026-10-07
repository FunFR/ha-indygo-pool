"""Select platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    BOOST_DEFAULT_SPEED,
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

# Boost durations (hours) offered by the MyIndygo app; 0 stops the boost.
BOOST_TO_HOURS = {"off": 0} | {f"{h}h": h for h in (2, 4, 8, 12, 24, 36, 48, 72)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    if not coordinator.data:
        return

    for module_id, module in coordinator.data.modules.items():
        if not module.filtration_program:
            continue
        characteristics = module.filtration_program.get("programCharacteristics", {})
        entity_classes: list[type[IndygoPoolCommandSelect]] = [
            IndygoPoolFiltrationModeSelect,
            IndygoPoolBoostSelect,
        ]
        if RULE_FIELD in characteristics:
            entity_classes.append(IndygoPoolManagementSelect)
        if module.has_variable_speed:
            entity_classes.append(IndygoPoolSpeedSelect)
            entities.append(
                IndygoPoolBoostSpeedSelect(coordinator, module_id, module.name)
            )
        entities.extend(
            entity_class(coordinator, module_id, module.name)
            for entity_class in entity_classes
        )

    async_add_entities(entities)


class IndygoPoolCommandSelect(IndygoPoolEntity, SelectEntity):
    """Select sending a command to a Pool Command module."""

    _key: str
    _option_to_int: dict[str, int]
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

    def _get_module(self) -> IndygoModuleData | None:
        """Return this entity's module from the latest coordinator data."""
        data = self.coordinator.data
        if not data or self._module_id is None:
            return None
        return data.modules.get(self._module_id)

    async def _async_send(
        self, module: IndygoModuleData, option: str, value: int
    ) -> bool:
        """Send the command for the selected option; False if impossible."""
        raise NotImplementedError

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        module = self._get_module()
        if module is None:
            LOGGER.error(
                "Cannot set %s: Module %s not found", self._key, self._module_id
            )
            return

        value = self._option_to_int.get(option)
        if value is None:
            LOGGER.error("Invalid option selected: %s", option)
            return

        if not await self._async_send(module, option, value):
            return

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


class IndygoPoolProgramSelect(IndygoPoolCommandSelect):
    """Select writing fields of the filtration program characteristics."""

    # Characteristics written with the selected value; the first one is read.
    _fields: tuple[str, ...]

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        module = self._get_module()
        if module is None or not module.filtration_program:
            return None

        value = module.filtration_program.get("programCharacteristics", {}).get(
            self._fields[0]
        )
        return next(
            (opt for opt, val in self._option_to_int.items() if val == value), None
        )

    async def _async_send(
        self, module: IndygoModuleData, option: str, value: int
    ) -> bool:
        """Write the value into every field of the filtration program."""
        if not module.filtration_program:
            LOGGER.error(
                "Cannot set %s: Filtration program not found for module %s",
                self._key,
                self._module_id,
            )
            return False

        await self.coordinator.client.async_update_program_characteristics(
            module.id,
            module.filtration_program,
            **dict.fromkeys(self._fields, value),
        )
        return True


class IndygoPoolBoostSelect(IndygoPoolCommandSelect):
    """Filtration boost: pick a duration to start it, off to stop it.

    The live status only says whether a boost runs, not its duration, so a
    running boost shows the duration last picked from Home Assistant.
    """

    _key = "filtration_boost"
    _option_to_int = BOOST_TO_HOURS
    _attr_icon = "mdi:rocket-launch"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id, module_name)
        self._picked_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return off, or the picked duration while a boost runs."""
        module = self._get_module()
        boost = module.sensors.get("pump_boost") if module else None
        if boost is None:
            return None
        return self._picked_option if boost.value else "off"

    async def _async_send(
        self, module: IndygoModuleData, option: str, value: int
    ) -> bool:
        """Start a boost of ``value`` hours, or stop it when 0."""
        if value:
            speed = (
                self.coordinator.boost_speeds.get(module.id, BOOST_DEFAULT_SPEED)
                if module.has_variable_speed
                else None
            )
            await self.coordinator.client.async_start_boost(value, speed)
        else:
            await self.coordinator.client.async_stop_boost()
        self._picked_option = option
        return True


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
    """Management type (rule) of the filtration.

    Only variable-speed pumps offer the variable-speed management type.
    """

    _key = "filtration_management"
    _fields = (RULE_FIELD,)
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        module = coordinator.data.modules.get(module_id)
        self._option_to_int = (
            MANAGEMENT_TO_INT
            if module and module.has_variable_speed
            else {
                option: rule
                for option, rule in MANAGEMENT_TO_INT.items()
                if rule != PROGRAM_RULE_VARIABLE_SPEED
            }
        )
        super().__init__(coordinator, module_id, module_name)


class IndygoPoolBoostSpeedSelect(IndygoPoolEntity, SelectEntity, RestoreEntity):
    """Speed the next boost of a variable-speed pump runs at.

    Nothing is sent when it changes: the boost select reads it when it
    starts a boost. Restored across restarts since the API does not keep it.
    """

    _attr_options = list(SPEED_TO_INT)
    _attr_translation_key = "boost_speed"
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self._attr_unique_id = self._build_unique_id("boost_speed")
        self.entity_id = f"select.{self.device_name_slug}_boost_speed"

    @property
    def current_option(self) -> str | None:
        """Return the picked boost speed."""
        speed = self.coordinator.boost_speeds.get(
            self._module_id or "", BOOST_DEFAULT_SPEED
        )
        return PUMP_SPEED_STATES.get(speed)

    async def async_added_to_hass(self) -> None:
        """Restore the speed picked before the restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in SPEED_TO_INT:
            self._set_speed(last_state.state)

    async def async_select_option(self, option: str) -> None:
        """Remember the speed for the next boost."""
        self._set_speed(option)
        self.async_write_ha_state()

    def _set_speed(self, option: str) -> None:
        if self._module_id:
            self.coordinator.boost_speeds[self._module_id] = SPEED_TO_INT[option]
