from unittest.mock import MagicMock

import pytest

from custom_components.indygo_pool.binary_sensor import (
    BINARY_SENSOR_TYPES,
    IndygoPoolBinarySensor,
)
from custom_components.indygo_pool.models import IndygoModuleData, IndygoPoolData


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.data = IndygoPoolData(
        pool_id="pool123", address="addr123", relay_id="relay123", raw_data={}
    )
    return coordinator


def test_ipx_binary_sensors(mock_coordinator):
    """Test IPX binary sensors."""
    ipx_module = IndygoModuleData(
        id="ipx123",
        type="ipx",
        name="IPX Module",
        raw_data={
            "ipxData": {
                "deviceState": {
                    "shutterEntry": True,
                    "flowEntry": False,
                    "cmdEntry": True,
                    "canPhEntry": False,
                    "boostEnabled": True,
                    "testProd": False,
                    "pHInjection": True,
                    "cellPolaruty": False,
                    "prodStatus": True,
                }
            }
        },
    )
    mock_coordinator.data.modules["ipx123"] = ipx_module

    desc_map = {desc.key: desc for desc in BINARY_SENSOR_TYPES}

    # Test Shutter (Inverted: True -> OFF)
    shutter = IndygoPoolBinarySensor(
        mock_coordinator, desc_map["shutterEntry"], "ipx123"
    )
    assert shutter.is_on is False
    assert shutter.unique_id == "pool123_ipx123_shutterEntry"
    assert shutter.device_info["name"] == "IPX Module"
    assert shutter.device_info["via_device"] == ("indygo_pool", "pool123")

    # Test Flow
    flow = IndygoPoolBinarySensor(mock_coordinator, desc_map["flowEntry"], "ipx123")
    assert flow.is_on is False
    assert flow.unique_id == "pool123_ipx123_flowEntry"

    # Test Cmd Entry
    cmd = IndygoPoolBinarySensor(mock_coordinator, desc_map["cmdEntry"], "ipx123")
    assert cmd.is_on is True

    # Test pH Entry
    ph_entry = IndygoPoolBinarySensor(
        mock_coordinator, desc_map["canPhEntry"], "ipx123"
    )
    assert ph_entry.is_on is False

    # Test Boost
    boost = IndygoPoolBinarySensor(mock_coordinator, desc_map["boostEnabled"], "ipx123")
    assert boost.is_on is True

    # Test pH Injection
    ph_inj = IndygoPoolBinarySensor(mock_coordinator, desc_map["pHInjection"], "ipx123")
    assert ph_inj.is_on is True

    # Test Cell Polarity
    cell_pol = IndygoPoolBinarySensor(
        mock_coordinator, desc_map["cellPolaruty"], "ipx123"
    )
    assert cell_pol.is_on is False

    # Test Production Status
    prod_status = IndygoPoolBinarySensor(
        mock_coordinator, desc_map["prodStatus"], "ipx123"
    )
    assert prod_status.is_on is True
