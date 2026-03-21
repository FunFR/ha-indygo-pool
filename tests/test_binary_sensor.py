"""Tests for the Indygo Pool binary sensor entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.indygo_pool.binary_sensor import (
    IndygoBinarySensorEntityDescription,
    IndygoPoolBinarySensor,
    async_setup_entry,
)
from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = MagicMock(spec=IndygoPoolData)
    coordinator.data.modules = {}
    coordinator.data.pool_status = {}
    coordinator.client = AsyncMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.data.pool_id = "test_pool_id"
    return coordinator


def test_binary_sensor_init(mock_coordinator):
    """Test initialization of binary sensor."""
    desc = IndygoBinarySensorEntityDescription(
        key="isOnline", translation_key="is_online"
    )
    entity = IndygoPoolBinarySensor(
        mock_coordinator, desc, module_id="mod1", module_name="IPX"
    )

    assert entity.entity_description == desc
    assert entity.unique_id == "test_pool_id_mod1_isOnline"
    assert entity._module_id == "mod1"
    # Should format translation placeholders
    assert entity._attr_translation_placeholders == {"module": "IPX"}


def test_is_on_pool_status_root(mock_coordinator):
    """Test is_on for root pool status."""
    mock_coordinator.data.pool_status = {
        "0": IndygoSensorData(key="0", value=1.0, extra_attributes={"foo": "bar"}),
        "1": IndygoSensorData(key="1", value=0.0, extra_attributes={}),
    }

    desc_on = IndygoBinarySensorEntityDescription(
        key="0", is_pool_status=True, translation_key="0"
    )
    entity_on = IndygoPoolBinarySensor(mock_coordinator, desc_on)

    assert entity_on.is_on is True
    assert entity_on.extra_state_attributes == {"foo": "bar"}

    desc_off = IndygoBinarySensorEntityDescription(
        key="1", is_pool_status=True, translation_key="1"
    )
    entity_off = IndygoPoolBinarySensor(mock_coordinator, desc_off)

    assert entity_off.is_on is False
    assert entity_off.extra_state_attributes == {}


def test_is_on_pool_status_module(mock_coordinator):
    """Test is_on for module pool status."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            name="Pump",
            type="lr-pc",
            pool_status={
                "0": IndygoSensorData(key="0", value=1.0, extra_attributes={})
            },
        )
    }
    desc = IndygoBinarySensorEntityDescription(
        key="0", is_pool_status=True, translation_key="0"
    )
    entity = IndygoPoolBinarySensor(mock_coordinator, desc, module_id="mod1")

    assert entity.is_on is True
    assert entity.extra_state_attributes == {}


def test_is_on_raw_data_boolean(mock_coordinator):
    """Test is_on for boolean raw data like isOnline."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            name="Pump",
            type="lr-pc",
            raw_data={"isOnline": True, "isError": False},
        )
    }

    desc_true = IndygoBinarySensorEntityDescription(
        key="isOnline", translation_key="is_online"
    )
    entity_true = IndygoPoolBinarySensor(mock_coordinator, desc_true, module_id="mod1")
    assert entity_true.is_on is True

    desc_false = IndygoBinarySensorEntityDescription(
        key="isError", translation_key="is_error"
    )
    entity_false = IndygoPoolBinarySensor(
        mock_coordinator, desc_false, module_id="mod1"
    )
    assert entity_false.is_on is False

    # Test inverted logic
    desc_inverted = IndygoBinarySensorEntityDescription(
        key="isOnline", translation_key="is_online", is_inverted=True
    )
    entity_inverted = IndygoPoolBinarySensor(
        mock_coordinator, desc_inverted, module_id="mod1"
    )
    assert entity_inverted.is_on is False


def test_is_on_sub_path(mock_coordinator):
    """Test is_on using sub_path logic."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            name="IPX",
            type="ipx",
            raw_data={
                "ipxData": {"deviceState": {"shutterEntry": 1.0, "flowEntry": 0.0}}
            },
        )
    }

    # Not inverted
    desc_flow = IndygoBinarySensorEntityDescription(
        key="flowEntry", sub_path="ipxData.deviceState", translation_key="flow"
    )
    entity_flow = IndygoPoolBinarySensor(mock_coordinator, desc_flow, module_id="mod1")
    assert entity_flow.is_on is False

    # Inverted
    desc_shutter = IndygoBinarySensorEntityDescription(
        key="shutterEntry",
        sub_path="ipxData.deviceState",
        is_inverted=True,
        translation_key="shutter",
    )
    entity_shutter = IndygoPoolBinarySensor(
        mock_coordinator, desc_shutter, module_id="mod1"
    )
    assert entity_shutter.is_on is False


def test_is_on_missing_data(mock_coordinator):
    """Test is_on when data is missing gracefully."""
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(id="mod1", name="Pump", type="lr-pc", raw_data={})
    }

    desc = IndygoBinarySensorEntityDescription(
        key="isOnline", translation_key="is_online"
    )
    entity = IndygoPoolBinarySensor(mock_coordinator, desc, module_id="mod1")

    assert entity.is_on is None
    assert entity.extra_state_attributes is None


@pytest.mark.asyncio
async def test_async_setup_entry(mock_coordinator):
    """Test setup entry function."""
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.data = {"indygo_pool": {mock_entry.entry_id: mock_coordinator}}

    # Prepopulating all required conditions
    mock_coordinator.data.pool_status = {"0": IndygoSensorData(key="0", value=1.0)}
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            name="IPX",
            type="ipx",
            pool_status={"0": IndygoSensorData(key="0", value=0.0)},
            raw_data={
                "isOnline": True,
                "ipxData": {"deviceState": {"shutterEntry": 1.0}},
            },
        )
    }

    async_add_entities = MagicMock()
    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    keys_added = [(e.entity_description.key, e._module_id) for e in entities]

    assert ("isOnline", "mod1") in keys_added
    assert ("shutterEntry", "mod1") in keys_added
    assert ("0", "mod1") in keys_added
    assert ("0", None) in keys_added


@pytest.mark.asyncio
async def test_async_setup_entry_no_data(mock_coordinator):
    """Test setup entry function with no data."""
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.data = {"indygo_pool": {mock_entry.entry_id: mock_coordinator}}

    mock_coordinator.data = None

    async_add_entities = MagicMock()
    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    async_add_entities.assert_not_called()


def test_is_on_invalid_values(mock_coordinator):
    """Test is_on with invalid float conversion values."""
    # Pool status test
    mock_coordinator.data.pool_status = {
        "0": IndygoSensorData(key="0", value="invalid_string")
    }
    desc_on = IndygoBinarySensorEntityDescription(
        key="0", is_pool_status=True, translation_key="0"
    )
    entity_on = IndygoPoolBinarySensor(mock_coordinator, desc_on)
    assert entity_on.is_on is None

    # Module raw data test
    mock_coordinator.data.modules = {
        "mod1": IndygoModuleData(
            id="mod1",
            name="Pump",
            type="lr-pc",
            raw_data={"ipxData": {"deviceState": {"flowEntry": "cannot_float"}}},
        )
    }
    desc_flow = IndygoBinarySensorEntityDescription(
        key="flowEntry", sub_path="ipxData.deviceState", translation_key="flow"
    )
    entity_flow = IndygoPoolBinarySensor(mock_coordinator, desc_flow, module_id="mod1")
    assert entity_flow.is_on is None
