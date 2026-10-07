"""Tests for the Indygo Pool select entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.indygo_pool.coordinator import IndygoPoolDataUpdateCoordinator
from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)
from custom_components.indygo_pool.select import (
    DELAYED_REFRESH_SECONDS,
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    IndygoPoolBoostSelect,
    IndygoPoolFiltrationModeSelect,
    IndygoPoolManagementSelect,
    IndygoPoolSpeedSelect,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock(spec=IndygoPoolDataUpdateCoordinator)
    coordinator.pool_device_id = None
    coordinator.data = MagicMock(spec=IndygoPoolData)
    coordinator.data.modules = {}
    coordinator.client = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    # Mock config_entry for unique_id fallback
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.data.pool_id = "test_pool_id"
    return coordinator


class TestIndygoPoolSelect:
    """Test the IndygoPoolFiltrationModeSelect entity."""

    def test_init(self, mock_coordinator):
        """Test initialization of the select entity."""
        module_id = "mod1"
        module_name = "Pool Pump"

        entity = IndygoPoolFiltrationModeSelect(
            mock_coordinator, module_id, module_name
        )
        entity.platform = MagicMock()
        entity.platform.platform_name = "indygo_pool"
        entity.platform.domain = "select"

        # Test basic properties that don't depend on translation logic
        assert entity._module_id == module_id
        assert entity.unique_id == "test_pool_id_mod1_filtration_mode"
        assert entity.options == [MODE_OFF, MODE_ON, MODE_AUTO]

    def test_current_option_off(self, mock_coordinator):
        """Test current option OFF (0)."""
        module_id = "mod1"
        filtration_program = {"programCharacteristics": {"mode": 0}}

        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id,
                type="lr-pc",
                name="Pump",
                filtration_program=filtration_program,
            )
        }

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")
        assert entity.current_option == MODE_OFF

    def test_current_option_auto(self, mock_coordinator):
        """Test current option AUTO (2)."""
        module_id = "mod1"
        filtration_program = {"programCharacteristics": {"mode": 2}}

        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id,
                type="lr-pc",
                name="Pump",
                filtration_program=filtration_program,
            )
        }

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")
        assert entity.current_option == MODE_AUTO

    def test_current_option_none(self, mock_coordinator):
        """Test current option None when data is missing."""
        module_id = "mod1"
        # Case 1: Module not in data
        mock_coordinator.data.modules = {}
        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")
        assert entity.current_option is None

        # Case 2: No filtration program
        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id, type="lr-pc", name="Pump", filtration_program=None
            )
        }
        assert entity.current_option is None

    @pytest.mark.asyncio
    async def test_select_option_success(self, mock_coordinator):
        """Test successfully selecting an option."""
        module_id = "mod1"
        filtration_program = {"programCharacteristics": {"mode": 0}}
        module_data = IndygoModuleData(
            id=module_id,
            type="lr-pc",
            name="Pump",
            filtration_program=filtration_program,
        )
        mock_coordinator.data.modules = {module_id: module_data}

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")

        with patch(
            "custom_components.indygo_pool.select.async_call_later"
        ) as mock_call_later:
            await entity.async_select_option(MODE_AUTO)

        # Verify API called with correct args (mode 2 for Auto)
        mock_coordinator.client.async_update_program_characteristics.assert_called_once_with(
            module_id, filtration_program, mode=2
        )
        # Verify immediate refresh requested
        mock_coordinator.async_request_refresh.assert_called_once()
        # Verify delayed refresh scheduled
        mock_call_later.assert_called_once()
        args = mock_call_later.call_args
        assert args[0][1] == DELAYED_REFRESH_SECONDS

    @pytest.mark.asyncio
    async def test_delayed_refresh_cancels_previous(self, mock_coordinator):
        """Test that a new mode change cancels the previous delayed refresh."""
        module_id = "mod1"
        filtration_program = {"programCharacteristics": {"mode": 0}}
        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id,
                type="lr-pc",
                name="Pump",
                filtration_program=filtration_program,
            )
        }

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")

        cancel_cb = MagicMock()
        with patch(
            "custom_components.indygo_pool.select.async_call_later",
            return_value=cancel_cb,
        ):
            await entity.async_select_option(MODE_ON)
            # First delayed refresh scheduled, not cancelled yet
            cancel_cb.assert_not_called()

            await entity.async_select_option(MODE_AUTO)
            # Previous delayed refresh should have been cancelled
            cancel_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_delayed_refresh_callback(self, mock_coordinator):
        """The timer target must work the way HA invokes it: a plain call.

        ``async_call_later`` expects a synchronous ``@callback``, not a
        coroutine function. Awaiting the target directly only proves a
        coroutine can be awaited, not that the scheduler's synchronous call
        works.
        """
        module_id = "mod1"
        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id,
                type="lr-pc",
                name="Pump",
                filtration_program={"programCharacteristics": {"mode": 0}},
            )
        }

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")
        entity.hass = MagicMock()

        with patch(
            "custom_components.indygo_pool.select.async_call_later"
        ) as mock_call_later:
            await entity.async_select_option(MODE_ON)

        timer_target = mock_call_later.call_args[0][2]
        assert timer_target(None) is None

        assert entity._cancel_delayed_refresh is None
        entity.hass.async_create_task.assert_called_once()
        # Close the coroutine handed to the task so it is not left un-awaited.
        entity.hass.async_create_task.call_args[0][0].close()

    @pytest.mark.asyncio
    async def test_removal_cancels_pending_refresh(self, mock_coordinator):
        """Unloading during the delay window disarms the timer."""
        module_id = "mod1"
        mock_coordinator.data.modules = {
            module_id: IndygoModuleData(
                id=module_id,
                type="lr-pc",
                name="Pump",
                filtration_program={"programCharacteristics": {"mode": 0}},
            )
        }

        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, module_id, "Pump")
        entity.hass = MagicMock()

        cancel_cb = MagicMock()
        with patch(
            "custom_components.indygo_pool.select.async_call_later",
            return_value=cancel_cb,
        ):
            await entity.async_select_option(MODE_ON)

        await entity.async_will_remove_from_hass()

        cancel_cb.assert_called_once()
        assert entity._cancel_delayed_refresh is None

    @pytest.mark.asyncio
    async def test_removal_without_pending_refresh_is_a_no_op(self, mock_coordinator):
        """Removing an idle entity must not raise."""
        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, "mod1", "Pump")

        await entity.async_will_remove_from_hass()

        assert entity._cancel_delayed_refresh is None

    @pytest.mark.asyncio
    async def test_select_option_invalid(self, mock_coordinator):
        """Test selecting an invalid option."""
        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {
            "mod1": IndygoModuleData(
                id="mod1",
                type="lr-pc",
                name="Pump",
                filtration_program={"programCharacteristics": {"mode": 0}},
            )
        }

        await entity.async_select_option("InvalidMode")

        mock_coordinator.client.async_update_program_characteristics.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_missing_module(self, mock_coordinator):
        """Test missing module in select option."""
        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {}

        await entity.async_select_option(MODE_AUTO)
        mock_coordinator.client.async_update_program_characteristics.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_filtration(self, mock_coordinator):
        """Test missing filtration program in select option."""
        entity = IndygoPoolFiltrationModeSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {
            "mod1": IndygoModuleData(
                id="mod1", type="lr-pc", name="Pump", filtration_program=None
            )
        }

        await entity.async_select_option(MODE_AUTO)
        mock_coordinator.client.async_update_program_characteristics.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_data(self, mock_coordinator):
        """Test setting up the select platform with data."""
        hass = MagicMock(spec=HomeAssistant)
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        hass.data = {"indygo_pool": {"test_entry_id": mock_coordinator}}

        mock_coordinator.data.modules = {
            "mod1": IndygoModuleData(
                id="mod1",
                type="lr-pc",
                name="Pump",
                filtration_program={"id": "prog1"},
            ),
            "mod2": IndygoModuleData(
                id="mod2", type="ipx", name="Electrolyzer", filtration_program=None
            ),
        }

        async_add_entities = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        # Only mod1 has a filtration program
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert sorted(e.unique_id for e in entities) == [
            "test_pool_id_mod1_filtration_boost",
            "test_pool_id_mod1_filtration_mode",
        ]

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_data(self, mock_coordinator):
        """Test setting up the select platform when coordinator has no data."""
        hass = MagicMock(spec=HomeAssistant)
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        hass.data = {"indygo_pool": {"test_entry_id": mock_coordinator}}

        mock_coordinator.data = None
        async_add_entities = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_not_called()


VS_PROGRAM = {
    "id": "prog_vs",
    "programCharacteristics": {
        "mode": 2,
        "programType": 4,
        "rule": 1,
        "defaultProgramSpeed": 2,
        "onSpeed": 2,
    },
}


@pytest.fixture
def vs_coordinator(mock_coordinator):
    """Coordinator holding a variable-speed pump module."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            type="lr-pc-vs2",
            name="Pump",
            filtration_program=VS_PROGRAM,
        )
    }
    return mock_coordinator


class TestVariableSpeedSelects:
    """Speed and management type selects of variable-speed pumps."""

    def test_speed_reflects_program(self, vs_coordinator):
        """The speed select shows the configured program speed."""
        entity = IndygoPoolSpeedSelect(vs_coordinator, "mod1", "Pump")

        assert entity.options == ["speed_1", "speed_2", "speed_3"]
        assert entity.current_option == "speed_2"
        assert entity.unique_id == "test_pool_id_mod1_filtration_speed"

    @pytest.mark.asyncio
    async def test_speed_writes_both_speed_fields(self, vs_coordinator):
        """Like the vendor app, both speed fields are written together."""
        entity = IndygoPoolSpeedSelect(vs_coordinator, "mod1", "Pump")

        with patch("custom_components.indygo_pool.select.async_call_later"):
            await entity.async_select_option("speed_3")

        vs_coordinator.client.async_update_program_characteristics.assert_awaited_once_with(
            "mod1", VS_PROGRAM, defaultProgramSpeed=3, onSpeed=3
        )

    def test_management_reflects_rule(self, vs_coordinator):
        """The management select maps rule 1 to thermo-adaptive."""
        entity = IndygoPoolManagementSelect(vs_coordinator, "mod1", "Pump")

        assert entity.options == ["schedule", "thermo_adaptive", "variable_speed"]
        assert entity.current_option == "thermo_adaptive"

    @pytest.mark.asyncio
    async def test_management_writes_rule_only(self, vs_coordinator):
        """Changing the management type only patches the rule."""
        entity = IndygoPoolManagementSelect(vs_coordinator, "mod1", "Pump")

        with patch("custom_components.indygo_pool.select.async_call_later"):
            await entity.async_select_option("schedule")

        vs_coordinator.client.async_update_program_characteristics.assert_awaited_once_with(
            "mod1", VS_PROGRAM, rule=0
        )

    def test_single_speed_management_has_no_variable_speed(self, mock_coordinator):
        """Variable-speed management is only offered on variable-speed pumps."""
        mock_coordinator.data.modules = {
            "pc": IndygoModuleData(
                id="pc", type="lr-pc", name="PC", filtration_program=VS_PROGRAM
            )
        }
        entity = IndygoPoolManagementSelect(mock_coordinator, "pc", "PC")

        assert entity.options == ["schedule", "thermo_adaptive"]

    @pytest.mark.asyncio
    async def test_setup_adds_speed_select_only_for_vs_modules(self, mock_coordinator):
        """Plain LR-PC programs carry speed fields too: the module type decides."""
        hass = MagicMock(spec=HomeAssistant)
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        hass.data = {"indygo_pool": {"test_entry_id": mock_coordinator}}
        mock_coordinator.data.modules = {
            "vs": IndygoModuleData(
                id="vs", type="lr-pc-vs2", name="VS", filtration_program=VS_PROGRAM
            ),
            "pc": IndygoModuleData(
                id="pc", type="lr-pc", name="PC", filtration_program=VS_PROGRAM
            ),
            "old": IndygoModuleData(
                id="old",
                type="lr-pc",
                name="Old",
                filtration_program={"programCharacteristics": {"mode": 2}},
            ),
        }
        async_add_entities = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        assert sorted(
            e.unique_id for e in entities if not isinstance(e, IndygoPoolBoostSelect)
        ) == [
            "test_pool_id_old_filtration_mode",
            "test_pool_id_pc_filtration_management",
            "test_pool_id_pc_filtration_mode",
            "test_pool_id_vs_filtration_management",
            "test_pool_id_vs_filtration_mode",
            "test_pool_id_vs_filtration_speed",
        ]


@pytest.fixture
def boost_coordinator(mock_coordinator):
    """Coordinator holding a Pool Command whose live status shows no boost."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            type="lr-pc",
            name="Pump",
            filtration_program={"programCharacteristics": {"mode": 2}},
            sensors={"pump_boost": IndygoSensorData(key="pump_boost", value=False)},
        )
    }
    return mock_coordinator


class TestBoostSelect:
    """Filtration boost select."""

    def test_options_match_the_app(self, boost_coordinator):
        """Durations offered by the MyIndygo app, plus off."""
        entity = IndygoPoolBoostSelect(boost_coordinator, "mod1", "Pump")

        assert entity.options == [
            "off",
            "2h",
            "4h",
            "8h",
            "12h",
            "24h",
            "36h",
            "48h",
            "72h",
        ]
        assert entity.unique_id == "test_pool_id_mod1_filtration_boost"

    def test_off_without_boost(self, boost_coordinator):
        """No running boost reads as off."""
        entity = IndygoPoolBoostSelect(boost_coordinator, "mod1", "Pump")

        assert entity.current_option == "off"

    @pytest.mark.asyncio
    async def test_start(self, boost_coordinator):
        """Picking a duration starts a boost of that many hours."""
        entity = IndygoPoolBoostSelect(boost_coordinator, "mod1", "Pump")

        with patch("custom_components.indygo_pool.select.async_call_later"):
            await entity.async_select_option("36h")

        boost_coordinator.client.async_start_boost.assert_awaited_once_with(36)
        boost_coordinator.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_running_boost_shows_the_picked_duration(self, boost_coordinator):
        """The API does not return the duration, so the last pick is shown."""
        entity = IndygoPoolBoostSelect(boost_coordinator, "mod1", "Pump")
        boost_coordinator.data.modules["mod1"].sensors["pump_boost"].value = True
        assert entity.current_option is None

        with patch("custom_components.indygo_pool.select.async_call_later"):
            await entity.async_select_option("4h")

        assert entity.current_option == "4h"

    @pytest.mark.asyncio
    async def test_stop(self, boost_coordinator):
        """Off stops the boost."""
        entity = IndygoPoolBoostSelect(boost_coordinator, "mod1", "Pump")

        with patch("custom_components.indygo_pool.select.async_call_later"):
            await entity.async_select_option("off")

        boost_coordinator.client.async_stop_boost.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_setup_adds_boost_for_pool_command(self, boost_coordinator):
        """Every module with a filtration program gets the boost select."""
        hass = MagicMock(spec=HomeAssistant)
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        hass.data = {"indygo_pool": {"test_entry_id": boost_coordinator}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        unique_ids = {e.unique_id for e in async_add_entities.call_args[0][0]}
        assert "test_pool_id_mod1_filtration_boost" in unique_ids
