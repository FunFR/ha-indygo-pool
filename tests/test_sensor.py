"""Tests for the Indygo Pool sensor entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)
from custom_components.indygo_pool.sensor import (
    IndygoPoolSensor,
    IndygoSensorEntityDescription,
    async_setup_entry,
)

TEMP_VALUE = 25.5
POWER_VALUE = 150.0
DUR_VALUE = 10
MIN_ENTITIES = 2


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = MagicMock(spec=IndygoPoolData)
    coordinator.data.sensors = {}
    coordinator.data.modules = {}
    coordinator.client = AsyncMock()
    # Mock config_entry for unique_id fallback
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.data.pool_id = "test_pool_id"
    return coordinator


def test_sensor_init_root(mock_coordinator):
    """Test initialization of a root sensor."""
    desc = IndygoSensorEntityDescription(
        key="temperature", translation_key="temperature"
    )
    entity = IndygoPoolSensor(mock_coordinator, desc)

    assert entity.entity_description == desc
    assert entity.unique_id == "test_pool_id_temperature"
    assert entity._module_id is None


def test_sensor_init_module(mock_coordinator):
    """Test initialization of a module sensor."""
    desc = IndygoSensorEntityDescription(key="power", translation_key="power")
    entity = IndygoPoolSensor(mock_coordinator, desc, module_id="mod1")

    assert entity.unique_id == "test_pool_id_mod1_power"
    assert entity._module_id == "mod1"


def test_sensor_value_root(mock_coordinator):
    """Test getting value for a root sensor."""
    mock_coordinator.data.sensors = {
        "temperature": IndygoSensorData(
            key="temperature", value=TEMP_VALUE, extra_attributes={"ts": "now"}
        )
    }
    desc = IndygoSensorEntityDescription(
        key="temperature", translation_key="temperature"
    )
    entity = IndygoPoolSensor(mock_coordinator, desc)

    assert entity.native_value == TEMP_VALUE
    assert entity.extra_state_attributes == {"ts": "now"}


def test_sensor_value_module(mock_coordinator):
    """Test getting value for a module sensor."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            type="lr-pc",
            name="Pump",
            sensors={
                "power": IndygoSensorData(
                    key="power", value=POWER_VALUE, extra_attributes={}
                )
            },
        )
    }
    desc = IndygoSensorEntityDescription(key="power", translation_key="power")
    entity = IndygoPoolSensor(mock_coordinator, desc, module_id="mod1")

    assert entity.native_value == POWER_VALUE
    assert entity.extra_state_attributes == {}


def test_sensor_value_missing(mock_coordinator):
    """Test getting value when data is missing."""
    desc = IndygoSensorEntityDescription(key="missing", translation_key="missing")
    entity = IndygoPoolSensor(mock_coordinator, desc)

    assert entity.native_value is None
    assert entity.extra_state_attributes is None


@pytest.mark.asyncio
async def test_async_setup_entry(mock_coordinator):
    """Test setup entry function."""
    mock_entry = MagicMock()
    mock_hass = MagicMock()

    # Mock hass data
    mock_hass.data = {"indygo_pool": {mock_entry.entry_id: mock_coordinator}}

    # Mock pool data
    mock_coordinator.data.sensors = {
        "temperature": IndygoSensorData(
            key="temperature", value=TEMP_VALUE, extra_attributes={}
        )
    }
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            type="lr-pc",
            name="Pump",
            sensors={
                "totalElectrolyseDuration": IndygoSensorData(
                    key="totalElectrolyseDuration", value=DUR_VALUE, extra_attributes={}
                )
            },
        )
    }

    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    # Check that entities were added
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # Should be at least 2 entities (1 root temperature, 1 module duration)
    assert len(entities) >= MIN_ENTITIES
    keys_added = [e.entity_description.key for e in entities]
    assert "temperature" in keys_added
    assert "totalElectrolyseDuration" in keys_added


@pytest.mark.asyncio
async def test_async_setup_entry_no_data(mock_coordinator):
    """Test setup entry function when no data exists."""
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.data = {"indygo_pool": {mock_entry.entry_id: mock_coordinator}}

    mock_coordinator.data = None

    async_add_entities = MagicMock()
    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    async_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_module_status(mock_coordinator):
    """Test setup entry with module status sensors."""
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.data = {"indygo_pool": {mock_entry.entry_id: mock_coordinator}}

    # "ph" is in SENSOR_TYPES (desc_map). "0" is filtration.
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            type="lr-pc",
            name="Pump",
            pool_status={"ph": IndygoSensorData(key="ph", value=7.2)},
        )
    }

    async_add_entities = MagicMock()
    await async_setup_entry(mock_hass, mock_entry, async_add_entities)
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    keys_added = [e.entity_description.key for e in entities]
    assert "ph" in keys_added


def test_sensor_value_coordinator_no_data(mock_coordinator):
    """Test native_value and extra_state_attributes when coordinator data is None."""
    desc = IndygoSensorEntityDescription(key="temperature", translation_key="temp")
    entity = IndygoPoolSensor(mock_coordinator, desc)

    mock_coordinator.data = None
    assert entity.native_value is None
    assert entity.extra_state_attributes is None
