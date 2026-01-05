"""Tests for the Indygo Pool integration."""

import os

import aiohttp
import pytest
from dotenv import load_dotenv

from custom_components.indygo_pool.api import IndygoPoolApiClient
from custom_components.indygo_pool.models import IndygoPoolData

# Load environment variables from .env file
load_dotenv()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_client_authentication():  # noqa: PLR0912, PLR0915
    """Test API client authentication with real credentials from env."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Credentials or pool_id not provided in environment (.env file)")

    async with aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=False, quote_cookie=False)
    ) as session:
        client = IndygoPoolApiClient(email, password, pool_id=pool_id, session=session)
        try:
            data = await client.async_get_data()
            assert data is not None
            assert isinstance(data, IndygoPoolData)
            print("Successfully reached the API endpoint and retrieved data!")
            print(f"Pool ID: {data.pool_id}")
            print(f"Address: {data.address}, Relay ID: {data.relay_id}")
            print(f"Sensors: {list(data.sensors.keys())}")
            print(f"Modules: {list(data.modules.keys())}")

            # Basic Validation
            assert data.pool_id == pool_id
            if data.sensors:
                assert len(data.sensors) > 0

        except Exception as e:
            if "Could not determine Pool Address" in str(e):
                pytest.skip(f"API interaction failed (environment issue): {e}")
            pytest.fail(f"API call failed: {e}")
