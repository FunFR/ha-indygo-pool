"""Tests for the Indygo Pool integration."""

import os
import pytest
from dotenv import load_dotenv
from custom_components.indygo_pool.api import IndygoPoolApiClient

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

    import aiohttp

    async with aiohttp.ClientSession() as session:
        client = IndygoPoolApiClient(email, password, pool_id=pool_id, session=session)
        try:
            data = await client.async_get_data()
            assert data is not None
            print("Successfully reached the API endpoint and retrieved data!")
            print(f"Data snippet (keys): {list(data.keys())}")

            if "pool" in data:
                print(f"Pool ID: {data['pool'].get('id')}")

        except Exception as e:
            pytest.fail(f"API call failed: {e}")
