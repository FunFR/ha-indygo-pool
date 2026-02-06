"""Tests for the Indygo Pool integration."""

import json
import os

import aiohttp
import pytest
from dotenv import load_dotenv

try:
    from aioresponses import aioresponses
except ImportError:
    aioresponses = None

from yarl import URL

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


@pytest.mark.asyncio
async def test_set_filtration_mode():
    """Test setting filtration mode with mocked session."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    pool_id = "12345"
    module_id = "mod_123"
    relay_id = "relay_123"
    # Minimal filtration program data
    filt_program = {
        "id": "prog_1",
        "programCharacteristics": {"mode": 0, "programType": 4},
    }

    # Expected payload should have mode updated to 2 (Auto)
    expected_mode = 2

    with aioresponses() as m:
        # 1. Mock the program update (PUT)
        update_url = "https://myindygo.com/program/update"
        m.put(update_url, payload={"status": "ok"})

        # 2. Mock the remote sync (POST)
        sync_url = "https://myindygo.com/remote/module/configuration/and/programs"
        m.post(sync_url, payload={"status": "ok"})

        # 3. Mock the module report (POST)
        report_url = "https://myindygo.com/module/reportModuleDataSent"
        m.post(report_url, payload={"status": "ok"})

        # 4. Mock the programs report (POST)
        report_prog_url = "https://myindygo.com/program/reportProgramsDataSent"
        m.post(report_prog_url, payload={"status": "ok"})

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient("test@example.com", "pass", pool_id, session)
            # Inject relay_id and fake token
            client._relay_id = relay_id
            client._token = "fake_token"

            await client.async_set_filtration_mode(
                module_id, filt_program, expected_mode
            )

            # 1. Verify PUT exists and has correct payload
            update_key = ("PUT", URL(update_url))
            assert update_key in m.requests
            put_req = m.requests[update_key][0]
            payload_sent = json.loads(put_req.kwargs["data"])
            assert payload_sent["module"] == module_id
            assert (
                payload_sent["programs"][0]["programCharacteristics"]["mode"]
                == expected_mode
            )

            # 2. Verify POST sync exists and has correct payload
            sync_key = ("POST", URL(sync_url))
            assert sync_key in m.requests
            sync_req = m.requests[sync_key][0]
            sync_payload = json.loads(sync_req.kwargs["data"])
            assert sync_payload["moduleId"] == module_id
            assert sync_payload["relayId"] == relay_id

            # 3. Verify POST report module exists and has correct payload
            report_module_key = ("POST", URL(report_url))
            assert report_module_key in m.requests
            report_module_req = m.requests[report_module_key][0]
            report_module_payload = json.loads(report_module_req.kwargs["data"])
            assert report_module_payload["module"] == module_id

            # 4. Verify POST report programs exists and has correct payload
            report_prog_url = "https://myindygo.com/program/reportProgramsDataSent"
            report_prog_key = ("POST", URL(report_prog_url))
            assert report_prog_key in m.requests
            report_prog_req = m.requests[report_prog_key][0]
            report_prog_payload = json.loads(report_prog_req.kwargs["data"])
            assert report_prog_payload["module"] == module_id
            assert report_prog_payload["programs"][0]["id"] == filt_program["id"]
            assert (
                report_prog_payload["programs"][0]["programCharacteristics"]["mode"]
                == expected_mode
            )


@pytest.mark.asyncio
async def test_set_filtration_mode_sync_failure():
    """Test that main update succeeds even if remote sync calls fail."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    pool_id = "12345"
    module_id = "mod_123"
    relay_id = "relay_123"
    filt_program = {
        "id": "prog_1",
        "programCharacteristics": {"mode": 2, "programType": 4},
    }
    expected_mode = 0  # OFF

    with aioresponses() as m:
        # 1. Mock the program update (PUT) - SUCCESS
        update_url = "https://myindygo.com/program/update"
        m.put(update_url, payload={"status": "ok"})

        # 2. Mock the remote sync (POST) - FAILURE (500)
        sync_url = "https://myindygo.com/remote/module/configuration/and/programs"
        m.post(sync_url, status=500)

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient("test@example.com", "pass", pool_id, session)
            client._relay_id = relay_id
            client._token = "fake_token"

            # Should NOT raise exception because errors in sync are caught and logged
            await client.async_set_filtration_mode(
                module_id, filt_program, expected_mode
            )

            # Verify PUT was still called
            assert ("PUT", URL(update_url)) in m.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("new_mode", [0, 1, 2])
async def test_set_filtration_mode_parameterized(new_mode):
    """Test setting all filtration modes."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    pool_id = "12345"
    module_id = "mod_123"
    relay_id = "relay_123"
    mode_off = 0
    mode_auto = 2
    filt_program = {
        "id": "prog_1",
        "programCharacteristics": {
            "mode": mode_auto if new_mode != mode_auto else mode_off,
            "programType": 4,
        },
    }

    with aioresponses() as m:
        m.put("https://myindygo.com/program/update", payload={"status": "ok"})
        m.post(
            "https://myindygo.com/remote/module/configuration/and/programs",
            payload={"status": "ok"},
        )
        m.post(
            "https://myindygo.com/module/reportModuleDataSent", payload={"status": "ok"}
        )
        m.post(
            "https://myindygo.com/program/reportProgramsDataSent",
            payload={"status": "ok"},
        )

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient("test@example.com", "pass", pool_id, session)
            client._relay_id = relay_id
            client._token = "fake_token"

            await client.async_set_filtration_mode(module_id, filt_program, new_mode)

            # Basic verification that the mode reached the reporting calls
            report_prog_url = "https://myindygo.com/program/reportProgramsDataSent"
            report_prog_req = m.requests[("POST", URL(report_prog_url))][0]
            report_prog_payload = json.loads(report_prog_req.kwargs["data"])
            assert (
                report_prog_payload["programs"][0]["programCharacteristics"]["mode"]
                == new_mode
            )
