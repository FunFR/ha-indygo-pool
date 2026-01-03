"""Tests for the Indygo Pool integration."""

import os

import aiohttp
import pytest

from custom_components.indygo_pool.api import IndygoPoolApiClient


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
            if "pool" in data:
                print(f"Pool data keys: {list(data['pool'].keys())}")
        except Exception as e:
            pytest.fail(f"API call failed: {e}")
