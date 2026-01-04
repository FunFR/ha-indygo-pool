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
async def test_live_data_structure_conformity():
    """Verify that live API data conforms to expected structure."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Missing credentials in .env")

    async with aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True)
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
            assert data.relay_id is not None, "Relay ID should be discovered"

            # 2. Critical Sensors (Must exist for a standard pool)
            # Water Temp and pH are almost always present
            assert "temperature" in data.sensors, "Missing water temperature sensor"
            assert isinstance(data.sensors["temperature"], IndygoSensorData)
            assert isinstance(data.sensors["temperature"].value, (float, int))

            assert "ph" in data.sensors, "Missing pH sensor"
            assert isinstance(data.sensors["ph"], IndygoSensorData)

            # 3. Helpers to check strictly positive values for crucial metrics
            # Constants for realistic range check
            min_temp = -10
            max_temp = 50

            temp = data.sensors["temperature"].value
            if temp is not None:
                assert temp > min_temp and temp < max_temp, (
                    f"Water temp {temp} out of realistic range"
                )

            # 4. Modules Check
            assert len(data.modules) > 0, "No modules found attached to pool"

            # Check for at least one known type (ipx or lr-mb-10)
            known_types = ["ipx", "lr-mb-10", "lr-pc"]
            found_known = any(m.type in known_types for m in data.modules.values())
            types_found = [m.type for m in data.modules.values()]
            assert found_known, f"No known module types found. Got: {types_found}"

        except Exception as e:
            pytest.fail(f"Live structure test failed: {e}")
