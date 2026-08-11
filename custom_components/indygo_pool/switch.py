"""Switch platform for Indygo Pool.

Exposes the auxiliary circuits of a Pool Command board (spotlight, water
blade, secondary pump, ...) as switches.  Turning a switch on or off writes
``programCharacteristics.mode`` on the matching program, which is exactly what
the vendor apps do; the reported state comes from the live circuit state
published by the board.
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    LOGGER,
    PROGRAM_MODE_AUTO,
    PROGRAM_MODE_OFF,
    PROGRAM_MODE_ON,
    PROGRAM_TYPE_FILTRATION,
    PROGRAM_TYPE_LIGHTING,
)
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity
from .models import IndygoModuleData

# Delay (seconds) before a follow-up refresh after a mode change.  The command
# travels cloud → gateway → LoRa → device and the device then reports back, so
# the status endpoint keeps returning the old state for a short while.
# Follow-up reads after a write.  Round trips of 12 s, 16 s and 86 s have been
# measured on real hardware, so a single shot cannot cover the range: too early
# and it reads the old state, too late and the entity stays stale until the
# next poll.  Three staged reads span the measured spread at the cost of two
# extra requests per command.
DELAYED_REFRESH_SCHEDULE = (15, 45, 90)

# How long the entity keeps reporting the requested state while waiting for the
# board to confirm it.  Deliberately past the last follow-up read, and bounded:
# beyond it, a command that never took effect must stop being reported as if it
# had.
OPTIMISTIC_TIMEOUT_SECONDS = 150

# Human-readable mode, exposed as an attribute so automations can tell an
# explicit On/Off from a scheduled Auto.
PROGRAM_MODE_NAMES = {
    PROGRAM_MODE_OFF: "off",
    PROGRAM_MODE_ON: "on",
    PROGRAM_MODE_AUTO: "auto",
}


def _program_index(program: dict) -> int | None:
    """Return the circuit index of a program, when it has one."""
    index = program.get("index")
    return index if isinstance(index, int) else None


def _output_name(module: IndygoModuleData, index: int) -> str | None:
    """Return the board output name matching a circuit index."""
    outputs = module.raw_data.get("outputs")
    if not isinstance(outputs, list):
        return None
    for output in outputs:
        if isinstance(output, dict) and output.get("index") == index:
            name = output.get("name")
            if isinstance(name, str) and name:
                return name
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[IndygoPoolCircuitSwitch] = []

    if not coordinator.data:
        return

    for module_id, module in coordinator.data.modules.items():
        used_suffixes: set[str] = set()

        for program in module.programs:
            characteristics = program.get("programCharacteristics")
            if not isinstance(characteristics, dict):
                continue

            program_type = characteristics.get("programType")
            if program_type == PROGRAM_TYPE_FILTRATION:
                # Filtration already has its own three-state select entity.
                continue

            index = _program_index(program)
            if index is None:
                continue

            # Known program types get a dedicated name; anything else falls
            # back to the board output label, so unmapped hardware still shows
            # up instead of being silently dropped.
            if program_type == PROGRAM_TYPE_LIGHTING and "spotlight" not in (
                used_suffixes
            ):
                translation_key = "spotlight"
                suffix = "spotlight"
                placeholders = None
            else:
                translation_key = "auxiliary_circuit"
                suffix = f"circuit_{index}"
                placeholders = {
                    "circuit": _output_name(module, index) or str(index + 1)
                }

            used_suffixes.add(suffix)
            entities.append(
                IndygoPoolCircuitSwitch(
                    coordinator=coordinator,
                    module_id=module_id,
                    circuit_index=index,
                    translation_key=translation_key,
                    entity_suffix=suffix,
                    translation_placeholders=placeholders,
                )
            )

    async_add_entities(entities)


class IndygoPoolCircuitSwitch(IndygoPoolEntity, SwitchEntity):
    """A single auxiliary circuit of a Pool Command board."""

    def __init__(
        self,
        *,
        coordinator: IndygoPoolDataUpdateCoordinator,
        module_id: str,
        circuit_index: int,
        translation_key: str,
        entity_suffix: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self._circuit_index = circuit_index
        self._attr_translation_key = translation_key
        if translation_placeholders:
            self._attr_translation_placeholders = translation_placeholders
        self._attr_unique_id = self._build_unique_id(f"circuit_{circuit_index}")
        self.entity_id = f"switch.{self.device_name_slug}_{entity_suffix}"
        self._pending_refreshes: list[CALLBACK_TYPE] = []
        # Requested state, held until the board confirms it or the window
        # expires.  See `is_on`.
        self._optimistic: bool | None = None
        self._optimistic_expires: float = 0.0

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    @property
    def _module(self) -> IndygoModuleData | None:
        """Return the owning module, if still present in the coordinator."""
        data = self.coordinator.data
        if not data or self._module_id not in data.modules:
            return None
        return data.modules[self._module_id]

    @property
    def _program(self) -> dict | None:
        """Return the program driving this circuit."""
        module = self._module
        if not module:
            return None
        for program in module.programs:
            if _program_index(program) == self._circuit_index:
                return program
        return None

    @property
    def _mode(self) -> int | None:
        """Return the programmed mode of this circuit."""
        program = self._program
        if not program:
            return None
        mode = program.get("programCharacteristics", {}).get("mode")
        return mode if isinstance(mode, int) else None

    @property
    def _circuit_state(self) -> bool | None:
        """Return the live circuit state reported by the board."""
        module = self._module
        if not module:
            return None
        status = module.pool_status.get(str(self._circuit_index))
        if status is None or status.value is None:
            return None
        try:
            return float(status.value) == 1.0
        except ValueError, TypeError:
            return None

    # ------------------------------------------------------------------
    # Entity
    # ------------------------------------------------------------------

    def _optimistic_value(self) -> bool | None:
        """Return the pending requested state, or None if it no longer holds.

        Clears itself once the board reports the requested value, or once the
        window elapses — so a command that never took effect surfaces as the
        real state instead of lying indefinitely.
        """
        if self._optimistic is None:
            return None
        if time.monotonic() >= self._optimistic_expires:
            self._optimistic = None
            return None
        if self._circuit_state is self._optimistic:
            self._optimistic = None
            return None
        return self._optimistic

    @property
    def is_on(self) -> bool | None:
        """Return true if the circuit is powered."""
        # A command takes cloud → gateway → LoRa → board and back: measured
        # between 12 s and 86 s.  Reporting the stale state during that window
        # makes any controller that expects prompt confirmation — HomeKit in
        # particular — treat the command as failed and retry it in a burst,
        # while the user taps again.  Every one of those is a real write, so
        # the board later replays the whole sequence and the light appears to
        # switch itself off.  Hold the requested state until the board agrees.
        optimistic = self._optimistic_value()
        if optimistic is not None:
            return optimistic

        state = self._circuit_state
        if state is not None:
            return state
        # Hardware that does not answer the live status endpoint leaves us
        # with the programmed mode only.  When that is missing too — the
        # module dropped out of the payload — the honest answer is "unknown",
        # not "off".
        mode = self._mode
        if mode is None:
            return None
        return mode == PROGRAM_MODE_ON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        mode = self._mode
        if self._optimistic_value() is not None:
            source = "optimistic"
        elif self._circuit_state is not None:
            source = "circuit"
        else:
            source = "program_mode"
        return {
            "circuit_index": self._circuit_index,
            "program_mode": PROGRAM_MODE_NAMES.get(mode, mode),
            "state_source": source,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the circuit on."""
        await self._async_set_mode(PROGRAM_MODE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the circuit off."""
        await self._async_set_mode(PROGRAM_MODE_OFF)

    async def _async_set_mode(self, mode: int) -> None:
        """Write a new mode on the program driving this circuit."""
        program = self._program
        if not program:
            LOGGER.error(
                "Cannot set mode: no program for circuit %s of module %s",
                self._circuit_index,
                self._module_id,
            )
            return

        await self.coordinator.client.async_set_program_mode(
            self._module_id, program, mode
        )

        # Report the requested state at once. Only after the write succeeded:
        # a failed command must not leave the entity claiming a state the
        # board never reached.
        self._optimistic = mode == PROGRAM_MODE_ON
        self._optimistic_expires = time.monotonic() + OPTIMISTIC_TIMEOUT_SECONDS
        self.async_write_ha_state()

        await self.coordinator.async_request_refresh()
        self._schedule_delayed_refresh()

    @callback
    def _schedule_delayed_refresh(self) -> None:
        """Arm the follow-up reads that catch the board's confirmation."""
        self._cancel_pending_refreshes()
        for delay in DELAYED_REFRESH_SCHEDULE:
            self._pending_refreshes.append(
                async_call_later(self.hass, delay, self._delayed_refresh_callback)
            )

    @callback
    def _cancel_pending_refreshes(self) -> None:
        """Drop every armed follow-up read.

        Cancelling a timer that already fired is a no-op, so handles are not
        tracked individually.
        """
        for cancel in self._pending_refreshes:
            cancel()
        self._pending_refreshes.clear()

    @callback
    def _delayed_refresh_callback(self, _now: object) -> None:
        """Fire one follow-up read.

        Invoked by ``async_call_later`` in the event loop, so it stays
        synchronous and hands the awaitable work to a task.
        """
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending reads when the entity goes away.

        Without this, unloading or reloading the integration inside the
        follow-up window leaves timers armed, firing on a dead entity.
        """
        self._cancel_pending_refreshes()
        await super().async_will_remove_from_hass()
