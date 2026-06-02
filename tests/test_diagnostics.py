"""Tests for Indygo Pool diagnostics."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indygo_pool.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POOL_ID,
    DOMAIN,
)
from custom_components.indygo_pool.diagnostics import async_get_config_entry_diagnostics
from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)

TEST_POOL_ID = "pool_diag_001"
TEST_POOL_ADDRESS = "SERIAL_GW_001"
TEST_DEVICE_SHORT_ID = "ABCDEF"
TEST_RELAY_ID = "relay_mock_001"

TEST_TEMP_VALUE = 28.5
TEST_PH_VALUE = 7.2
TEST_LRPC_INPUT_TYPE = 5
TEST_IPX_INPUT_TYPE = 6
TEST_SENSOR_STATE_RAW = 2850


def _make_coordinator(pool_data: IndygoPoolData | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = pool_data
    coordinator.client._pool_address = TEST_POOL_ADDRESS
    coordinator.client._device_short_id = TEST_DEVICE_SHORT_ID
    coordinator.client._relay_id = TEST_RELAY_ID
    return coordinator


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "s3cr3t",
            CONF_POOL_ID: TEST_POOL_ID,
        },
    )


@pytest.mark.asyncio
async def test_diagnostics_full(hass):
    """Verify PII redaction, noise removal, and novel-field passthrough."""
    entry = _make_entry()

    pool_data = IndygoPoolData(
        pool_id=TEST_POOL_ID,
        raw_data={
            "temperature": TEST_TEMP_VALUE,
            "temperatureTime": "2023-01-01T12:00:00Z",
            "sensorState": [{"index": 0, "value": TEST_SENSOR_STATE_RAW}],
            "pool": [{"index": 0, "value": 1}],
            # Must be dropped (noise)
            "addressWeather": {"cityName": "TestCity"},
            # Unknown future field — must pass through unchanged
            "futureUnknownField": "some_value",
        },
    )
    pool_data.modules["lrpc_1"] = IndygoModuleData(
        id="lrpc_1",
        type="lr-pc",
        name="LRPC-ABCDEF",
        sensors={
            "temperature": IndygoSensorData(key="temperature", value=TEST_TEMP_VALUE)
        },
        raw_data={
            "type": "lr-pc",
            "name": "LRPC-ABCDEF",
            "serialNumber": "SERIAL_LRPC_001",
            "softwareVersion": "7.0.9",
            "hardwareVersion": "B",
            "manufacturerType": "15",
            "defaultName": "LRPC3-ABCDEF",
            # PII — must be redacted
            "owner": "user_object_id_123",
            "macAddress": "C8:B9:61:F1:E8:1E",
            # Novel hardware field — must pass through
            "vs2CustomField": "vs2value",
            # Noise — must be dropped
            "addressWeather": {"cityName": "TestCity"},
            # Raw inputs/outputs for hardware discovery
            "inputs": [
                {
                    "type": TEST_LRPC_INPUT_TYPE,
                    "subType": 0,
                    "unit": 2,
                    "expression": "x/100.0",
                    "name": "",
                    "lastValue": {
                        "value": TEST_TEMP_VALUE,
                        "date": "2023-01-01T12:00:00Z",
                    },
                }
            ],
            "outputs": [{"index": 0, "name": "Station 1", "useSensor": True}],
        },
    )
    pool_data.modules["ipx_1"] = IndygoModuleData(
        id="ipx_1",
        type="ipx",
        name="IPX-MOCK",
        sensors={
            "ph": IndygoSensorData(key="ph", value=TEST_PH_VALUE),
            "ipx_salt": IndygoSensorData(key="ipx_salt", value=4.5),
        },
        raw_data={
            "type": "ipx",
            "name": "IPX-MOCK",
            "serialNumber": "SERIAL_IPX_001",
            "softwareVersion": "0.0",
            "hardwareVersion": "0",
            "manufacturerType": "FD",
            "defaultName": "IPX2-MOCK",
            "inputs": [
                {
                    "type": TEST_IPX_INPUT_TYPE,
                    "subType": 0,
                    "unit": 4,
                    "expression": "x/100.0",
                    "name": "",
                    "lastValue": {
                        "value": TEST_PH_VALUE,
                        "date": "2023-01-01T12:37:00Z",
                    },
                }
            ],
            "outputs": [
                {
                    "index": 0,
                    "name": "Station 1",
                    "useSensor": True,
                    "ipxData": {
                        "type": 1,
                        "pHSetpoint": TEST_PH_VALUE,
                        "pHHysteresis": 0.1,
                    },
                }
            ],
        },
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _make_coordinator(pool_data)

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Config entry: credentials redacted, pool_id intact
    assert result["config_entry"][CONF_POOL_ID] == TEST_POOL_ID
    assert result["config_entry"][CONF_EMAIL] == "**REDACTED**"
    assert result["config_entry"][CONF_PASSWORD] == "**REDACTED**"

    # Hardware IDs
    assert result["hardware_ids"]["pool_address"] == TEST_POOL_ADDRESS
    assert result["hardware_ids"]["device_short_id"] == TEST_DEVICE_SHORT_ID
    assert result["hardware_ids"]["relay_id"] == TEST_RELAY_ID

    assert len(result["modules"]) == len(pool_data.modules)
    lrpc = next(m for m in result["modules"] if m["type"] == "lr-pc")

    # PII redacted
    assert lrpc["owner"] == "**REDACTED**"
    assert lrpc["macAddress"] == "**REDACTED**"

    # Novel/unknown field passes through — essential for unsupported hardware
    assert lrpc["vs2CustomField"] == "vs2value"

    # Noise dropped
    assert "addressWeather" not in lrpc

    # Computed metadata present
    assert "temperature" in lrpc["sensors"]
    assert lrpc["has_filtration_program"] is False

    # Raw inputs present with full detail for hardware discovery
    assert lrpc["inputs"][0]["type"] == TEST_LRPC_INPUT_TYPE
    assert lrpc["inputs"][0]["lastValue"]["value"] == TEST_TEMP_VALUE

    # Raw outputs present
    assert lrpc["outputs"][0]["index"] == 0

    # IPX module: ipxData inside outputs
    ipx = next(m for m in result["modules"] if m["type"] == "ipx")
    assert ipx["outputs"][0]["ipxData"]["pHSetpoint"] == TEST_PH_VALUE
    assert "ph" in ipx["sensors"]
    assert "ipx_salt" in ipx["sensors"]

    # Root-level raw status: useful fields pass through, noise dropped
    assert result["raw_status"]["temperature"] == TEST_TEMP_VALUE
    assert result["raw_status"]["sensorState"][0]["value"] == TEST_SENSOR_STATE_RAW
    assert result["raw_status"]["futureUnknownField"] == "some_value"
    assert "addressWeather" not in result["raw_status"]


@pytest.mark.asyncio
async def test_diagnostics_no_data(hass):
    """Test diagnostics when coordinator has no data yet."""
    entry = _make_entry()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _make_coordinator(None)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["modules"] == []
    assert result["root_sensors"] == []
    assert result["root_pool_status_circuits"] == []
    assert result["raw_status"] == {}
