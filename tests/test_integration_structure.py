"""Integration test for Indygo Pool data structure."""

import os

import aiohttp
import pytest
from dotenv import load_dotenv

from custom_components.indygo_pool.api import (
    IndygoPoolApiClient,
    IndygoPoolApiClientError,
)
from custom_components.indygo_pool.models import IndygoPoolData, IndygoSensorData

# Load environment variables
load_dotenv()


@pytest.mark.asyncio
@pytest.mark.integration
async def _verify_critical_sensors(data: IndygoPoolData):
    """Verify critical sensors like temperature."""
    assert "temperature" in data.sensors, "Missing water temperature sensor"
    assert isinstance(data.sensors["temperature"], IndygoSensorData)
    assert isinstance(data.sensors["temperature"].value, (float, int))
    print(f"DEBUG: Water Temperature = {data.sensors['temperature'].value} °C")

    # Check for last_measurement_time attribute
    if "last_measurement_time" in data.sensors["temperature"].extra_attributes:
        val = data.sensors["temperature"].extra_attributes["last_measurement_time"]
        print(f"DEBUG: Temperature timestamp: {val}")
    else:
        print("WARNING: Temperature sensor missing last_measurement_time")


async def _verify_ph_sensor(data: IndygoPoolData):
    """Verify pH sensor and derived attributes."""
    if "ph" in data.sensors:
        ph_sensor = data.sensors["ph"]
        print(f"DEBUG: pH found: {ph_sensor.value}")
        assert ph_sensor.value is not None

        if "last_measurement_time" in ph_sensor.extra_attributes:
            ts = ph_sensor.extra_attributes["last_measurement_time"]
            print(f"DEBUG: pH timestamp: {ts}")
        else:
            print(
                "WARNING: pH sensor found but missing last_measurement_time"
                " (scraping might have failed to find input)"
            )
    else:
        pytest.fail("ph sensor not found in live data")


async def _verify_ipx_sensors(data: IndygoPoolData):
    """Verify other IPX related sensors."""
    expected_sensors = [
        "ipx_salt",
        "ph_setpoint",
        "production_setpoint",
        "electrolyzer_mode",
    ]

    for sensor_key in expected_sensors:
        if sensor_key in data.sensors:
            val = data.sensors[sensor_key].value
            print(f"DEBUG: {sensor_key} found: {val}")
            assert val is not None
        else:
            print(f"WARNING: {sensor_key} not found (optional/unavailable)")


async def _verify_module_sensors(data: IndygoPoolData):
    """Verify module specific sensors."""
    found_duration = False
    for m in data.modules.values():
        if "totalElectrolyseDuration" in m.sensors:
            val = m.sensors["totalElectrolyseDuration"].value
            print(f"DEBUG: totalElectrolyseDuration found on module {m.id}: {val}")
            assert val is not None
            found_duration = True

    if not found_duration:
        print("WARNING: totalElectrolyseDuration not found on any module")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_live_data_structure_conformity():
    """Verify that live API data conforms to expected structure."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Missing credentials in .env")

    async with aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True, quote_cookie=False)
    ) as session:
        client = IndygoPoolApiClient(email, password, pool_id=pool_id, session=session)

        try:
            data: IndygoPoolData = await client.async_get_data()
        except IndygoPoolApiClientError as e:
            pytest.skip(f"Integration test skipped due to API/Auth failure: {e}")

        # 1. Top Level Structure
        assert isinstance(data, IndygoPoolData)
        assert data.pool_id == pool_id
        assert data.address is not None, "Pool address should be discovered"
        print(f"DEBUG: Pool Address = {data.address}")
        assert data.relay_id is not None, "Relay ID should be discovered"
        print(f"DEBUG: Relay ID = {data.relay_id}")

        # 2. Critical Sensors (Must exist for a standard pool)
        await _verify_critical_sensors(data)

        # 4. Modules Check
        assert len(data.modules) > 0, "No modules found attached to pool"

        # 5. pH Check (Enhanced with scraping)
        await _verify_ph_sensor(data)

        # 6. Other IPX Sensors
        await _verify_ipx_sensors(data)

        # 7. Module Sensors
        await _verify_module_sensors(data)
