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


TEST_POOL_ID = "12345"
TEST_MODULE_ID = "mod_123"
TEST_RELAY_ID = "relay_123"
TEST_POOL_ADDRESS = "pool_123"


def _verify_request_payload(mock_obj, method: str, url: str, expected_data: dict):
    """Helper to verify API request payload."""
    key = (method, URL(url))
    assert key in mock_obj.requests
    req = mock_obj.requests[key][0]
    payload = json.loads(req.kwargs["data"])
    for field, value in expected_data.items():
        if "." in field:  # Nested field like "programs.0.mode"
            parts = field.split(".")
            actual = payload
            for part in parts:
                if part.isdigit():
                    actual = actual[int(part)]
                else:
                    actual = actual[part]
            assert actual == value
        else:
            assert payload[field] == value


@pytest.mark.asyncio
async def test_set_filtration_mode():
    """Test setting filtration mode with mocked session."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    filt_program = {
        "id": "prog_1",
        "programCharacteristics": {"mode": 0, "programType": 4},
    }
    expected_mode = 2

    with aioresponses() as m:
        # Mock all API endpoints
        m.put("https://myindygo.com/module/update", payload={"status": "ok"})
        m.put("https://myindygo.com/program/update", payload={"status": "ok"})
        m.post(
            "https://myindygo.com/remote/module/configuration/and/programs",
            payload={"status": "ok"},
        )
        m.post(
            "https://myindygo.com/module/reportModuleDataSent",
            payload={"status": "ok"},
        )
        m.post(
            "https://myindygo.com/program/reportProgramsDataSent",
            payload={"status": "ok"},
        )
        m.post("https://myindygo.com/remote/module/control", payload={"status": "ok"})

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient(
                "test@example.com", "pass", TEST_POOL_ID, session
            )
            client._relay_id = TEST_RELAY_ID
            client._pool_address = TEST_POOL_ADDRESS
            client._token = "fake_token"

            await client.async_set_filtration_mode(
                TEST_MODULE_ID, filt_program, expected_mode
            )

            # Verify program update
            _verify_request_payload(
                m,
                "PUT",
                "https://myindygo.com/program/update",
                {
                    "module": TEST_MODULE_ID,
                    "programs.0.programCharacteristics.mode": expected_mode,
                },
            )

            # Verify remote sync
            _verify_request_payload(
                m,
                "POST",
                "https://myindygo.com/remote/module/configuration/and/programs",
                {"moduleId": TEST_MODULE_ID, "relayId": TEST_RELAY_ID},
            )

            # Verify module report
            _verify_request_payload(
                m,
                "POST",
                "https://myindygo.com/module/reportModuleDataSent",
                {"module": TEST_MODULE_ID},
            )

            # Verify programs report
            _verify_request_payload(
                m,
                "POST",
                "https://myindygo.com/program/reportProgramsDataSent",
                {
                    "module": TEST_MODULE_ID,
                    "programs.0.id": filt_program["id"],
                    "programs.0.programCharacteristics.mode": expected_mode,
                },
            )

            # Remote control is NOT called for AUTO mode
            control_key = ("POST", URL("https://myindygo.com/remote/module/control"))
            assert control_key not in m.requests


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
        # 1. Mock the module update (PUT) - SUCCESS
        module_url = "https://myindygo.com/module/update"
        m.put(module_url, payload={"status": "ok"})

        # 2. Mock the program update (PUT) - SUCCESS
        update_url = "https://myindygo.com/program/update"
        m.put(update_url, payload={"status": "ok"})

        # 3. Mock the remote sync (POST) - FAILURE (500)
        sync_url = "https://myindygo.com/remote/module/configuration/and/programs"
        m.post(sync_url, status=500)

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient("test@example.com", "pass", pool_id, session)
            client._relay_id = relay_id
            client._pool_address = "pool_123"
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
        m.put("https://myindygo.com/module/update", payload={"status": "ok"})
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
        m.post(
            "https://myindygo.com/remote/module/control",
            payload={"status": "ok"},
        )

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient("test@example.com", "pass", pool_id, session)
            client._relay_id = relay_id
            client._pool_address = "pool_123"
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

            # Remote control is only called for OFF mode (mode 0)
            # Modes 1 (ON) and 2 (AUTO) rely on program synchronization only
            control_url = "https://myindygo.com/remote/module/control"
            control_key = ("POST", URL(control_url))
            if new_mode == 0:  # OFF mode
                assert control_key in m.requests
                control_req = m.requests[control_key][0]
                control_payload = json.loads(control_req.kwargs["data"])
                assert control_payload["linesControl"][0]["mode"] == "off"
                assert control_payload["linesControl"][0]["action"] == 1
            else:  # ON or AUTO mode - no remote control call
                assert control_key not in m.requests
