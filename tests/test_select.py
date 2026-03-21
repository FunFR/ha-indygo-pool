"""Tests for the Indygo Pool select entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.indygo_pool.models import IndygoModuleData, IndygoPoolData
from custom_components.indygo_pool.select import (
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    IndygoPoolSelect,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
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
    """Test the IndygoPoolSelect entity."""

    def test_init(self, mock_coordinator):
        """Test initialization of the select entity."""
        module_id = "mod1"
        module_name = "Pool Pump"

        entity = IndygoPoolSelect(mock_coordinator, module_id, module_name)
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

        entity = IndygoPoolSelect(mock_coordinator, module_id, "Pump")
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

        entity = IndygoPoolSelect(mock_coordinator, module_id, "Pump")
        assert entity.current_option == MODE_AUTO

    def test_current_option_none(self, mock_coordinator):
        """Test current option None when data is missing."""
        module_id = "mod1"
        # Case 1: Module not in data
        mock_coordinator.data.modules = {}
        entity = IndygoPoolSelect(mock_coordinator, module_id, "Pump")
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

        entity = IndygoPoolSelect(mock_coordinator, module_id, "Pump")

        # Select Auto
        await entity.async_select_option(MODE_AUTO)

        # Verify API called with correct args (mode 2 for Auto)
        mock_coordinator.client.async_set_filtration_mode.assert_called_once_with(
            module_id, filtration_program, 2
        )
        # Verify refresh requested
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_option_invalid(self, mock_coordinator):
        """Test selecting an invalid option."""
        entity = IndygoPoolSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {
            "mod1": IndygoModuleData(
                id="mod1",
                type="lr-pc",
                name="Pump",
                filtration_program={"programCharacteristics": {"mode": 0}},
            )
        }

        await entity.async_select_option("InvalidMode")

        mock_coordinator.client.async_set_filtration_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_missing_module(self, mock_coordinator):
        """Test missing module in select option."""
        entity = IndygoPoolSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {}

        await entity.async_select_option(MODE_AUTO)
        mock_coordinator.client.async_set_filtration_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_option_no_filtration(self, mock_coordinator):
        """Test missing filtration program in select option."""
        entity = IndygoPoolSelect(mock_coordinator, "mod1", "Pump")
        mock_coordinator.data.modules = {
            "mod1": IndygoModuleData(
                id="mod1", type="lr-pc", name="Pump", filtration_program=None
            )
        }

        await entity.async_select_option(MODE_AUTO)
        mock_coordinator.client.async_set_filtration_mode.assert_not_called()

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

        # Should only add 1 entity (for mod1 which has a filtration program)
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert entities[0]._module_id == "mod1"

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
