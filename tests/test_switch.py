"""Tests for the Indygo Pool switch entities (Pool Command circuits)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)
from custom_components.indygo_pool.switch import (
    IndygoPoolCircuitSwitch,
    async_setup_entry,
)

FILTRATION_PROGRAM = {
    "id": "prog_0",
    "index": 0,
    "programCharacteristics": {"mode": 1, "programType": 4},
}
SPOTLIGHT_PROGRAM = {
    "id": "prog_1",
    "index": 1,
    "programCharacteristics": {"mode": 0, "programType": 2},
}
AUXILIARY_PROGRAM = {
    "id": "prog_2",
    "index": 2,
    "programCharacteristics": {"mode": 0, "programType": 5},
}

EXPECTED_SWITCH_COUNT = 2

OUTPUTS = [
    {"index": 0, "name": "Station 1"},
    {"index": 1, "name": "Station 2"},
    {"index": 2, "name": "Station 3"},
]


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = MagicMock(spec=IndygoPoolData)
    coordinator.data.modules = {}
    coordinator.data.pool_id = "test_pool_id"
    coordinator.client = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    return coordinator


def _module(pool_status: dict | None = None) -> IndygoModuleData:
    """Build a Pool Command module with three circuits."""
    return IndygoModuleData(
        id="mod1",
        type="lr-pc",
        name="LRPC-D37902",
        programs=[FILTRATION_PROGRAM, SPOTLIGHT_PROGRAM, AUXILIARY_PROGRAM],
        raw_data={"outputs": OUTPUTS},
        pool_status=pool_status or {},
    )


def _switch(coordinator, index: int = 1) -> IndygoPoolCircuitSwitch:
    """Build a switch for a given circuit index."""
    return IndygoPoolCircuitSwitch(
        coordinator=coordinator,
        module_id="mod1",
        circuit_index=index,
        translation_key="spotlight",
        entity_suffix="spotlight",
    )


class TestSetup:
    """Test the platform setup."""

    async def _run_setup(self, coordinator):
        hass = MagicMock(spec=HomeAssistant)
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        hass.data = {"indygo_pool": {"test_entry_id": coordinator}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)
        return async_add_entities

    @pytest.mark.asyncio
    async def test_creates_one_switch_per_non_filtration_program(
        self, mock_coordinator
    ):
        """Filtration keeps its select; every other circuit gets a switch."""
        mock_coordinator.data.modules = {"mod1": _module()}

        async_add_entities = await self._run_setup(mock_coordinator)

        entities = async_add_entities.call_args[0][0]
        assert len(entities) == EXPECTED_SWITCH_COUNT
        assert [e._circuit_index for e in entities] == [1, 2]

    @pytest.mark.asyncio
    async def test_names_lighting_and_falls_back_for_unknown_types(
        self, mock_coordinator
    ):
        """An unmapped program type still yields an entity, named after its output."""
        mock_coordinator.data.modules = {"mod1": _module()}

        async_add_entities = await self._run_setup(mock_coordinator)
        spotlight, auxiliary = async_add_entities.call_args[0][0]

        assert spotlight._attr_translation_key == "spotlight"
        assert spotlight.entity_id == "switch.lrpc_d37902_spotlight"

        assert auxiliary._attr_translation_key == "auxiliary_circuit"
        assert auxiliary._attr_translation_placeholders == {"circuit": "Station 3"}
        assert auxiliary.entity_id == "switch.lrpc_d37902_circuit_2"

    @pytest.mark.asyncio
    async def test_placeholder_falls_back_to_index_without_output_name(
        self, mock_coordinator
    ):
        """Missing output labels fall back to a 1-based circuit number."""
        module = _module()
        module.raw_data = {}
        mock_coordinator.data.modules = {"mod1": module}

        async_add_entities = await self._run_setup(mock_coordinator)
        _, auxiliary = async_add_entities.call_args[0][0]

        assert auxiliary._attr_translation_placeholders == {"circuit": "3"}

    @pytest.mark.asyncio
    async def test_placeholder_ignores_blank_output_name(self, mock_coordinator):
        """An output with an empty label also falls back to the index."""
        module = _module()
        module.raw_data = {"outputs": [{"index": 2, "name": ""}]}
        mock_coordinator.data.modules = {"mod1": module}

        async_add_entities = await self._run_setup(mock_coordinator)
        _, auxiliary = async_add_entities.call_args[0][0]

        assert auxiliary._attr_translation_placeholders == {"circuit": "3"}

    @pytest.mark.asyncio
    async def test_skips_programs_without_index_or_characteristics(
        self, mock_coordinator
    ):
        """Malformed programs are ignored rather than crashing setup."""
        module = _module()
        module.programs = [
            {"id": "a", "index": 1},
            {"id": "b", "programCharacteristics": {"programType": 2}},
        ]
        mock_coordinator.data.modules = {"mod1": module}

        async_add_entities = await self._run_setup(mock_coordinator)

        assert async_add_entities.call_args[0][0] == []

    @pytest.mark.asyncio
    async def test_no_data(self, mock_coordinator):
        """No coordinator data means no entities."""
        mock_coordinator.data = None
        async_add_entities = await self._run_setup(mock_coordinator)

        async_add_entities.assert_not_called()


class TestState:
    """Test how the switch reports its state."""

    def test_is_on_from_live_circuit_state(self, mock_coordinator):
        """The live circuit value drives the state."""
        mock_coordinator.data.modules = {
            "mod1": _module({"1": IndygoSensorData(key="circuit_1_status", value=1)})
        }
        entity = _switch(mock_coordinator)

        assert entity.is_on is True
        assert entity.extra_state_attributes["state_source"] == "circuit"

    def test_is_on_false_when_circuit_off(self, mock_coordinator):
        """A circuit reported at 0 is off, whatever the programmed mode."""
        mock_coordinator.data.modules = {
            "mod1": _module({"1": IndygoSensorData(key="circuit_1_status", value=0)})
        }
        entity = _switch(mock_coordinator)

        assert entity.is_on is False

    def test_falls_back_to_program_mode(self, mock_coordinator):
        """Hardware without live status falls back to the programmed mode."""
        module = _module()
        module.programs = [
            FILTRATION_PROGRAM,
            {
                "id": "prog_1",
                "index": 1,
                "programCharacteristics": {"mode": 1, "programType": 2},
            },
        ]
        mock_coordinator.data.modules = {"mod1": module}
        entity = _switch(mock_coordinator)

        assert entity.is_on is True
        assert entity.extra_state_attributes["state_source"] == "program_mode"

    def test_non_numeric_circuit_value_falls_back(self, mock_coordinator):
        """An unparsable circuit value must not raise."""
        mock_coordinator.data.modules = {
            "mod1": _module(
                {"1": IndygoSensorData(key="circuit_1_status", value="oops")}
            )
        }
        entity = _switch(mock_coordinator)

        assert entity.is_on is False
        assert entity.extra_state_attributes["state_source"] == "program_mode"

    def test_attributes_expose_the_programmed_mode(self, mock_coordinator):
        """The tri-state mode stays visible even behind a two-state switch."""
        module = _module({"1": IndygoSensorData(key="circuit_1_status", value=1)})
        module.programs = [
            FILTRATION_PROGRAM,
            {
                "id": "prog_1",
                "index": 1,
                "programCharacteristics": {"mode": 2, "programType": 2},
            },
        ]
        mock_coordinator.data.modules = {"mod1": module}
        entity = _switch(mock_coordinator)

        attributes = entity.extra_state_attributes
        assert attributes["program_mode"] == "auto"
        assert attributes["circuit_index"] == 1

    def test_unknown_module(self, mock_coordinator):
        """A module that disappeared yields no state and no crash."""
        mock_coordinator.data.modules = {}
        entity = _switch(mock_coordinator)

        assert entity.is_on is False
        assert entity.extra_state_attributes["program_mode"] is None


class TestCommands:
    """Test the write path."""

    @pytest.mark.asyncio
    async def test_turn_on_writes_mode_one(self, mock_coordinator):
        """Turning on writes mode 1 on the matching program."""
        mock_coordinator.data.modules = {"mod1": _module()}
        entity = _switch(mock_coordinator)

        with patch("custom_components.indygo_pool.switch.async_call_later"):
            await entity.async_turn_on()

        mock_coordinator.client.async_set_program_mode.assert_awaited_once_with(
            "mod1", SPOTLIGHT_PROGRAM, 1
        )
        mock_coordinator.async_request_refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_turn_off_writes_mode_zero(self, mock_coordinator):
        """Turning off writes a hard 0, like the vendor apps do."""
        mock_coordinator.data.modules = {"mod1": _module()}
        entity = _switch(mock_coordinator)

        with patch("custom_components.indygo_pool.switch.async_call_later"):
            await entity.async_turn_off()

        mock_coordinator.client.async_set_program_mode.assert_awaited_once_with(
            "mod1", SPOTLIGHT_PROGRAM, 0
        )

    @pytest.mark.asyncio
    async def test_no_program_does_not_call_the_api(self, mock_coordinator):
        """A circuit without a program cannot be commanded."""
        mock_coordinator.data.modules = {"mod1": _module()}
        entity = _switch(mock_coordinator, index=7)

        with patch("custom_components.indygo_pool.switch.async_call_later"):
            await entity.async_turn_on()

        mock_coordinator.client.async_set_program_mode.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delayed_refresh_is_rescheduled(self, mock_coordinator):
        """A second command cancels the pending delayed refresh."""
        mock_coordinator.data.modules = {"mod1": _module()}
        entity = _switch(mock_coordinator)
        entity.hass = MagicMock()

        cancel_cb = MagicMock()
        with patch(
            "custom_components.indygo_pool.switch.async_call_later",
            return_value=cancel_cb,
        ):
            await entity.async_turn_on()
            cancel_cb.assert_not_called()

            await entity.async_turn_off()
            cancel_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_delayed_refresh_callback(self, mock_coordinator):
        """The delayed callback refreshes and clears its handle."""
        mock_coordinator.data.modules = {"mod1": _module()}
        entity = _switch(mock_coordinator)

        with patch(
            "custom_components.indygo_pool.switch.async_call_later"
        ) as mock_call_later:
            await entity.async_turn_on()

        callback = mock_call_later.call_args[0][2]
        mock_coordinator.async_request_refresh.reset_mock()
        await callback(None)

        mock_coordinator.async_request_refresh.assert_awaited_once()
        assert entity._cancel_delayed_refresh is None


def test_unique_id_is_stable_per_circuit(mock_coordinator):
    """Unique IDs are built from the pool, module and circuit index."""
    mock_coordinator.data.modules = {"mod1": _module()}
    entity = _switch(mock_coordinator, index=2)

    assert entity.unique_id == "test_pool_id_mod1_circuit_2"
