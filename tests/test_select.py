"""Tests for the Indygo Pool select entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.indygo_pool.models import IndygoModuleData, IndygoPoolData
from custom_components.indygo_pool.select import (
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    IndygoPoolSelect,
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

        assert entity._module_id == module_id
        assert entity.name == "Pool Pump Filtration Mode"
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

        await entity.async_select_option("InvalidMode")

        mock_coordinator.client.async_set_filtration_mode.assert_not_called()
