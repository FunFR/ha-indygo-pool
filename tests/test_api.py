"""Tests for the Indygo Pool integration."""

import os

import aiohttp
import pytest

from custom_components.indygo_pool.api import IndygoPoolApiClient


def _verify_pool_data(pool_data):
    """Verify pool data key indicators."""
    print(f"Pool data keys: {list(pool_data.keys())}")
    if "temperature" in pool_data:
        print(f"Pool Temperature: {pool_data['temperature']}")
    if "ph" in pool_data:
        print(f"Pool pH: {pool_data['ph']}")


def _verify_sensor(name, value, is_tor):
    """Verify a single sensor's data."""
    sensor_type = "Binary Sensor" if is_tor else "Sensor"
    print(f"Found {sensor_type}: {name} = {value}")

    # Specific checks for expected sensors
    if "Température" in name or "Thermomètre" in name:
        assert value is not None, f"Temperature sensor {name} has no value"
    if "pH" in name:
        assert value is not None, f"pH sensor {name} has no value"
    if "Redox" in name or "ORP" in name:
        print(f"Redox/ORP found: {value}")
    if "Sel" in name or "Salt" in name:
        print(f"Salt sensor found: {value}")
    if "Volet" in name:
        print(f"Shutter (Volet) found: {value}")


def _verify_modules_data(modules_data):
    """Verify modules and their sensors."""
    print(f"Found {len(modules_data)} modules")
    for module in modules_data:
        if "inputs" in module:
            for sensor in module["inputs"]:
                name = sensor.get("name", "Unknown")
                value = sensor.get("value")
                if value is None and "lastValue" in sensor:
                    value = sensor["lastValue"].get("value")

                is_tor = sensor.get("typeIsTOR", False) == 1
                _verify_sensor(name, value, is_tor)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_client_authentication():
    """Test API client authentication with real credentials from env."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Credentials or pool_id not provided in environment")

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(use_dns_cache=False)
    ) as session:
        client = IndygoPoolApiClient(email, password, session, pool_id=pool_id)
        try:
            data = await client.async_get_data()
            assert data is not None
            print("Successfully reached the API endpoint and retrieved data!")
            # Print a small snippet of the data to verify it contains the expected JSON
            print(f"Data snippet (keys): {list(data.keys())}")

            # Verify pool data
            if "pool" in data:
                _verify_pool_data(data["pool"])

            # Verify modules/sensors data
            if "modules" in data:
                _verify_modules_data(data["modules"])

        except Exception as e:
            pytest.fail(f"API call failed: {e}")
