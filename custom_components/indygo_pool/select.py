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
    ELECTROLYSER_MODE_AUTO,
    ELECTROLYSER_MODE_OFF,
    ELECTROLYSER_MODE_PERCENTAGE,
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
from .entity import IndygoPoolEntity, async_set_electrolyser
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


def _boost_speed(coordinator: IndygoPoolDataUpdateCoordinator, module_id: str) -> int:
    """Return the speed the next boost of a variable-speed pump runs at."""
    return coordinator.boost_speeds.get(module_id, BOOST_DEFAULT_SPEED)


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
        if module.electrolyser_output:
            entities.extend(
                entity_class(coordinator, module_id, module.name)
                for entity_class in (
                    IndygoPoolElectrolyserModeSelect,
                    IndygoPoolElectrolyserBoostSelect,
                )
            )
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

    async def _async_send(self, module: IndygoModuleData, value: int) -> bool:
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

        if not await self._async_send(module, value):
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

    async def _async_send(self, module: IndygoModuleData, value: int) -> bool:
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

    The live status only gives the time left, so a running boost shows the
    shortest duration covering it, wherever the boost was started from.
    """

    _key = "filtration_boost"
    _option_to_int = BOOST_TO_HOURS
    _attr_icon = "mdi:rocket-launch"

    @property
    def current_option(self) -> str | None:
        """Return off, or the duration of the running boost."""
        module = self._get_module()
        boost = module.sensors.get("pump_boost") if module else None
        if module is None or boost is None:
            return None
        if not boost.value:
            return "off"
        remaining = module.sensors.get("filtration_remaining_time")
        if remaining is None or not isinstance(remaining.value, int | float):
            return None
        minutes = remaining.value
        return next(
            (opt for opt, hours in BOOST_TO_HOURS.items() if hours * 60 >= minutes),
            None,
        )

    async def _async_send(self, module: IndygoModuleData, value: int) -> bool:
        """Start a boost of ``value`` hours, or stop it when 0."""
        if module.filtration_program not in module.programs:
            LOGGER.error("Cannot set %s: no filtration line", self._key)
            return False

        # The app addresses the filtration line by its program position.
        index = module.programs.index(module.filtration_program)
        if value:
            speed = _boost_speed(self.coordinator, module.id)
            await self.coordinator.client.async_start_boost(
                index, value, speed if module.has_variable_speed else None
            )
        else:
            await self.coordinator.client.async_stop_boost(index)
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
        return PUMP_SPEED_STATES.get(
            _boost_speed(self.coordinator, self._module_id or "")
        )

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


ELECTROLYSER_MODE_TO_INT = {
    "off": ELECTROLYSER_MODE_OFF,
    "percentage": ELECTROLYSER_MODE_PERCENTAGE,
    "auto": ELECTROLYSER_MODE_AUTO,
}

# Electrolyser boost durations (hours) offered by the app; 0 cancels it.
ELECTROLYSER_BOOST_TO_HOURS = {"off": 0, "12h": 12, "24h": 24}


class IndygoPoolElectrolyserSelect(IndygoPoolCommandSelect):
    """Select changing a setting of the IPX electrolyser."""

    _attr_icon = "mdi:water-plus"

    def _ipx_data(self) -> dict:
        """Return the live settings of the electrolyser output."""
        module = self._get_module()
        return module.electrolyser_settings if module else {}

    @property
    def available(self) -> bool:
        """Return False once the electrolyser output disappears."""
        return super().available and bool(self._ipx_data())


class IndygoPoolElectrolyserModeSelect(IndygoPoolElectrolyserSelect):
    """Electrolyser mode (off, percentage, auto).

    AUTO regulates on a redox sensor, so it is offered only with one.
    """

    _key = "electrolyser_mode"

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        module_name: str,
    ) -> None:
        """Initialize."""
        module = coordinator.data.modules.get(module_id)
        current = (
            module.electrolyser_settings.get("electrolyzerMode") if module else None
        )
        offer_auto = bool(module and module.has_redox_input) or (
            current == ELECTROLYSER_MODE_AUTO
        )
        self._option_to_int = {
            option: mode
            for option, mode in ELECTROLYSER_MODE_TO_INT.items()
            if offer_auto or mode != ELECTROLYSER_MODE_AUTO
        }
        super().__init__(coordinator, module_id, module_name)

    @property
    def current_option(self) -> str | None:
        """Return the mode reported by the electrolyser."""
        value = self._ipx_data().get("electrolyzerMode")
        return next(
            (opt for opt, mode in ELECTROLYSER_MODE_TO_INT.items() if mode == value),
            None,
        )

    async def _async_send(self, module: IndygoModuleData, value: int) -> bool:
        """Switch the electrolyser mode."""
        await async_set_electrolyser(
            self.coordinator, module, {"electrolyzerMode": value}
        )
        return True


class IndygoPoolElectrolyserBoostSelect(IndygoPoolElectrolyserSelect):
    """Electrolyser boost: pick a duration to start it, off to cancel it.

    The live data only gives the time left, so a running boost shows the
    shortest duration covering it.
    """

    _key = "electrolyser_boost"
    _option_to_int = ELECTROLYSER_BOOST_TO_HOURS
    _attr_icon = "mdi:rocket-launch"

    def _remaining_minutes(self) -> int:
        """Return the time left on the running boost.

        Observed: a cancelled boost keeps its last remaining time, so the
        time only counts while the boost is enabled.
        """
        ipx_data = self._ipx_data()
        remaining = ipx_data.get("boostRemainingTime")
        if not ipx_data.get("boostEnabled") or not isinstance(remaining, int):
            return 0
        return remaining

    @property
    def current_option(self) -> str | None:
        """Return off, or the duration of the running boost."""
        if "boostEnabled" not in self._ipx_data():
            return None
        minutes = self._remaining_minutes()
        if not minutes:
            return "off"
        return next(
            (
                opt
                for opt, hours in ELECTROLYSER_BOOST_TO_HOURS.items()
                if hours * 60 >= minutes
            ),
            None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Expose the time left on the running boost, in minutes."""
        return {"remaining_minutes": self._remaining_minutes()}

    async def _async_send(self, module: IndygoModuleData, value: int) -> bool:
        """Start a boost of ``value`` hours, or cancel it when 0."""
        await async_set_electrolyser(self.coordinator, module, {"boostCommand": value})
        return True
