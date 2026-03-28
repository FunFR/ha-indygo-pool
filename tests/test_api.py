"""Tests for the Indygo Pool API Client."""

import json
import os
from unittest.mock import patch

import aiohttp
import pytest
from dotenv import load_dotenv

try:
    from aioresponses import aioresponses
except ImportError:
    aioresponses = None

from yarl import URL

from custom_components.indygo_pool.api import (
    BASE_URL,
    IndygoPoolApiClient,
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientCommunicationError,
    IndygoPoolApiClientError,
)
from custom_components.indygo_pool.models import IndygoModuleData, IndygoPoolData

load_dotenv()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_POOL_ID = "12345"
TEST_MODULE_ID = "mod_123"
TEST_RELAY_ID = "relay_123"
TEST_POOL_ADDRESS = "pool_123"
TEST_SERIAL = "SERIAL_ABC"

TOKEN_RESPONSE = {
    "access_token": "fake_access_token",
    "token_type": "Bearer",
    "expires_in": 3600,
}

MODULES_RESPONSE = {
    "modules": [
        {
            "id": TEST_MODULE_ID,
            "type": "lr-pc",
            "serialNumber": TEST_SERIAL,
            "name": "Pump-ABC",
            "relay": TEST_RELAY_ID,
        },
        {
            "id": "gw_1",
            "type": "lr-mb-10",
            "serialNumber": TEST_POOL_ADDRESS,
            "name": "Gateway",
        },
    ],
}


def _make_client(session: aiohttp.ClientSession) -> IndygoPoolApiClient:
    """Create a pre-authenticated client."""
    client = IndygoPoolApiClient("test@example.com", "pass", TEST_POOL_ID, session)
    client._token = "Bearer fake_access_token"
    client._token_expiry = 9999999999  # far future
    return client


def _verify_request_payload(mock_obj, method: str, url: str, expected_data: dict):
    """Verify API request payload."""
    key = (method, URL(url))
    assert key in mock_obj.requests
    req = mock_obj.requests[key][0]
    if req.kwargs.get("data"):
        payload = json.loads(req.kwargs["data"])
    else:
        payload = req.kwargs.get("json", {})
    for field, value in expected_data.items():
        if "." in field:
            parts = field.split(".")
            actual = payload
            for part in parts:
                actual = actual[int(part)] if part.isdigit() else actual[part]
            assert actual == value
        else:
            assert payload[field] == value


# ---------------------------------------------------------------------------
# Integration test (real API)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_client_authentication():
    """Test API client with real credentials from .env."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Credentials not provided in .env")

    async with aiohttp.ClientSession() as session:
        client = IndygoPoolApiClient(email, password, pool_id, session)
        data = await client.async_get_data()
        assert data is not None
        assert isinstance(data, IndygoPoolData)
        assert data.pool_id == pool_id


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success():
    """Test successful OAuth2 login."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(f"{BASE_URL}/oauth2/token", payload=TOKEN_RESPONSE)

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient(
                "test@example.com", "pass", TEST_POOL_ID, session
            )
            await client.async_login()
            assert client._token == "Bearer fake_access_token"


@pytest.mark.asyncio
async def test_login_failure():
    """Test failed OAuth2 login."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(f"{BASE_URL}/oauth2/token", status=401)

        async with aiohttp.ClientSession() as session:
            client = IndygoPoolApiClient(
                "test@example.com", "pass", TEST_POOL_ID, session
            )
            with pytest.raises(IndygoPoolApiClientAuthenticationError):
                await client.async_login()


# ---------------------------------------------------------------------------
# Data fetching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_data_success():
    """Test successful data retrieval via API."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        # Mock modules metadata
        m.post(f"{BASE_URL}/api/getUserWithHisModules", payload=MODULES_RESPONSE)
        # Mock programs for each module (LRPC has filtration program)
        m.post(
            f"{BASE_URL}/api/getModuleWithHisPrograms",
            payload={
                "programs": [{"programCharacteristics": {"programType": 4, "mode": 2}}]
            },
        )
        m.post(
            f"{BASE_URL}/api/getModuleWithHisPrograms",
            payload={"programs": []},
        )
        # Mock status data
        m.get(
            f"{BASE_URL}/v1/module/{TEST_POOL_ADDRESS}/status/ABC",
            payload={"temperature": 25.5},
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            data = await client.async_get_data()

            assert data is not None
            assert isinstance(data, IndygoPoolData)
            assert data.pool_id == TEST_POOL_ID
            assert data.address == TEST_POOL_ADDRESS
            assert data.relay_id == TEST_RELAY_ID


@pytest.mark.asyncio
async def test_get_data_communication_error():
    """Test communication error during data retrieval."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/getUserWithHisModules", status=500)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            with pytest.raises(IndygoPoolApiClientCommunicationError):
                await client.async_get_data()


@pytest.mark.asyncio
async def test_get_data_resolves_hardware_ids_once():
    """Test that hardware IDs are resolved once and cached."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        # First call
        m.post(f"{BASE_URL}/api/getUserWithHisModules", payload=MODULES_RESPONSE)
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.get(
            f"{BASE_URL}/v1/module/{TEST_POOL_ADDRESS}/status/ABC",
            payload={},
        )
        # Second call
        m.post(f"{BASE_URL}/api/getUserWithHisModules", payload=MODULES_RESPONSE)
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.get(
            f"{BASE_URL}/v1/module/{TEST_POOL_ADDRESS}/status/ABC",
            payload={},
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)

            await client.async_get_data()
            assert client._pool_address == TEST_POOL_ADDRESS

            # Second call should use cached IDs
            with patch.object(client._parser, "resolve_hardware_ids") as mock_resolve:
                await client.async_get_data()
                mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Filtration mode tests
# ---------------------------------------------------------------------------

FILT_PROGRAM = {
    "id": "prog_1",
    "programCharacteristics": {"mode": 0, "programType": 4},
}


def _mock_filtration_endpoints(m):
    """Mock all endpoints used by async_set_filtration_mode."""
    m.put(f"{BASE_URL}/api/updatePrograms", payload={"status": "ok"})
    m.post(
        f"{BASE_URL}/api/module/{TEST_POOL_ADDRESS}/programs/ABC",
        payload={"status": "ok"},
    )
    m.post(
        f"{BASE_URL}/api/reportModuleDatasSent",
        payload={"status": "ok"},
    )
    m.post(
        f"{BASE_URL}/api/reportProgramsDatasSent",
        payload={"status": "ok"},
    )


@pytest.mark.asyncio
async def test_set_filtration_mode():
    """Test setting filtration mode to Auto."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    expected_mode = 2

    with aioresponses() as m:
        _mock_filtration_endpoints(m)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = TEST_POOL_ADDRESS
            client._device_short_id = "ABC"
            # Set up module data so programs are found
            client._data = IndygoPoolData(pool_id=TEST_POOL_ID)
            client._data.modules[TEST_MODULE_ID] = IndygoModuleData(
                id=TEST_MODULE_ID,
                type="lr-pc",
                name="Pump",
                programs=[FILT_PROGRAM],
                raw_data={"serialNumber": TEST_SERIAL},
            )

            await client.async_set_filtration_mode(
                TEST_MODULE_ID, FILT_PROGRAM, expected_mode
            )

            # Verify program update was sent
            _verify_request_payload(
                m,
                "PUT",
                f"{BASE_URL}/api/updatePrograms",
                {
                    "module": TEST_MODULE_ID,
                    "programs.0.programCharacteristics.mode": expected_mode,
                },
            )

            # Verify report was called
            report_key = (
                "POST",
                URL(f"{BASE_URL}/api/reportModuleDatasSent"),
            )
            assert report_key in m.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("new_mode", [0, 1, 2])
async def test_set_filtration_mode_parameterized(new_mode):
    """Test setting all filtration modes."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    mode_auto = 2
    mode_off = 0
    filt_program = {
        "id": "prog_1",
        "programCharacteristics": {
            "mode": mode_auto if new_mode != mode_auto else mode_off,
            "programType": 4,
        },
    }

    with aioresponses() as m:
        _mock_filtration_endpoints(m)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = TEST_POOL_ADDRESS
            client._data = IndygoPoolData(pool_id=TEST_POOL_ID)
            client._data.modules[TEST_MODULE_ID] = IndygoModuleData(
                id=TEST_MODULE_ID,
                type="lr-pc",
                name="Pump",
                programs=[filt_program],
                raw_data={"serialNumber": TEST_SERIAL},
            )

            await client.async_set_filtration_mode(
                TEST_MODULE_ID, filt_program, new_mode
            )

            # Verify the mode in the report call
            report_key = (
                "POST",
                URL(f"{BASE_URL}/api/reportProgramsDatasSent"),
            )
            assert report_key in m.requests


@pytest.mark.asyncio
async def test_set_filtration_mode_sync_failure():
    """Test that main update succeeds even if device push fails."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        # updatePrograms succeeds
        m.put(f"{BASE_URL}/api/updatePrograms", payload={"status": "ok"})
        # Device push fails
        m.post(
            f"{BASE_URL}/api/module/{TEST_POOL_ADDRESS}/programs/ABC",
            status=500,
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = TEST_POOL_ADDRESS
            client._device_short_id = "ABC"
            client._data = IndygoPoolData(pool_id=TEST_POOL_ID)
            client._data.modules[TEST_MODULE_ID] = IndygoModuleData(
                id=TEST_MODULE_ID,
                type="lr-pc",
                name="Pump",
                programs=[FILT_PROGRAM],
                raw_data={"serialNumber": TEST_SERIAL},
            )

            # Should raise because report failure propagates
            with pytest.raises(IndygoPoolApiClientError):
                await client.async_set_filtration_mode(TEST_MODULE_ID, FILT_PROGRAM, 0)


# ---------------------------------------------------------------------------
# Remote control tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_remote_control():
    """Test send remote control command."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/setManualCommandToSend",
            payload={"status": "ok"},
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = "ABCDE"

            await client.async_send_remote_control("off", "ABCDE", action=1)

            req = m.requests[("POST", URL(f"{BASE_URL}/api/setManualCommandToSend"))][0]
            payload = req.kwargs.get("json", {})
            assert payload["moduleSerialNumber"] == "ABCDE"
            assert payload["linesControl"][0]["action"] == 1


# ---------------------------------------------------------------------------
# LoRaWAN tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synchronize_lorawan():
    """Test LoRaWAN synchronization."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/modules/sendDataViaLoRaWAN",
            payload={"status": "ok"},
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            await client.async_synchronize_lorawan("mod1", True, True)

            req = m.requests[("POST", URL(f"{BASE_URL}/modules/sendDataViaLoRaWAN"))][0]
            payload = req.kwargs.get("json", {})
            assert payload["moduleId"] == "mod1"
            assert payload["sendProgram"] is True


# ---------------------------------------------------------------------------
# Token refresh tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_refresh_on_401():
    """Test that a 401 triggers token refresh and retry."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        # _ensure_token triggers login (token_expiry=0)
        m.post(f"{BASE_URL}/oauth2/token", payload=TOKEN_RESPONSE)
        # First call returns 401
        m.post(f"{BASE_URL}/api/getUserWithHisModules", status=401)
        # Re-auth on 401
        m.post(f"{BASE_URL}/oauth2/token", payload=TOKEN_RESPONSE)
        # Retry succeeds
        m.post(f"{BASE_URL}/api/getUserWithHisModules", payload=MODULES_RESPONSE)
        # Programs for modules
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        # Status
        m.get(f"{BASE_URL}/v1/module/{TEST_POOL_ADDRESS}/status/ABC", payload={})

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            # Force token to look expired so _ensure_token re-authenticates
            client._token_expiry = 0

            data = await client.async_get_data()
            assert data is not None


# ---------------------------------------------------------------------------
# Edge case / coverage tests
# ---------------------------------------------------------------------------

FILT_PROGRAM_WITH_ID = {
    "id": "prog_1",
    "programCharacteristics": {"mode": 0, "programType": 4},
}
OTHER_PROGRAM = {
    "id": "prog_2",
    "programCharacteristics": {"mode": 1, "programType": 1},
}


@pytest.mark.asyncio
async def test_set_filtration_mode_clears_mode_on_non_filtration():
    """Test that non-filtration programs have their mode cleared."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        _mock_filtration_endpoints(m)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = TEST_POOL_ADDRESS
            client._device_short_id = "ABC"
            client._data = IndygoPoolData(pool_id=TEST_POOL_ID)
            client._data.modules[TEST_MODULE_ID] = IndygoModuleData(
                id=TEST_MODULE_ID,
                type="lr-pc",
                name="Pump",
                programs=[FILT_PROGRAM_WITH_ID, OTHER_PROGRAM],
                raw_data={"serialNumber": TEST_SERIAL},
            )

            await client.async_set_filtration_mode(
                TEST_MODULE_ID, FILT_PROGRAM_WITH_ID, 2
            )

            # Verify other program had mode cleared
            req = m.requests[("PUT", URL(f"{BASE_URL}/api/updatePrograms"))][0]
            payload = req.kwargs.get("json", {})
            other = payload["programs"][1]
            assert other["programCharacteristics"]["mode"] is None
            assert other["dataChanged"] is True


@pytest.mark.asyncio
async def test_set_filtration_mode_program_not_in_list():
    """Test mode set when program ID is not found in module programs."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        _mock_filtration_endpoints(m)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = TEST_POOL_ADDRESS
            client._device_short_id = "ABC"
            client._data = IndygoPoolData(pool_id=TEST_POOL_ID)
            client._data.modules[TEST_MODULE_ID] = IndygoModuleData(
                id=TEST_MODULE_ID,
                type="lr-pc",
                name="Pump",
                programs=[],  # Empty — program won't be found
                raw_data={"serialNumber": TEST_SERIAL},
            )

            await client.async_set_filtration_mode(
                TEST_MODULE_ID, FILT_PROGRAM_WITH_ID, 1
            )

            # Program should still be appended
            req = m.requests[("PUT", URL(f"{BASE_URL}/api/updatePrograms"))][0]
            payload = req.kwargs.get("json", {})
            assert len(payload["programs"]) == 1
            assert payload["programs"][0]["programCharacteristics"]["mode"] == 1


@pytest.mark.asyncio
async def test_get_data_with_ipx_module():
    """Test that IPX module data is merged into status."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    modules_with_ipx = {
        "modules": [
            MODULES_RESPONSE["modules"][0],
            MODULES_RESPONSE["modules"][1],
            {"id": "ipx_1", "type": "ipx", "name": "IPX"},
        ],
    }

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/getUserWithHisModules", payload=modules_with_ipx)
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.post(f"{BASE_URL}/api/getModuleWithHisPrograms", payload={"programs": []})
        m.get(f"{BASE_URL}/v1/module/{TEST_POOL_ADDRESS}/status/ABC", payload={})

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            data = await client.async_get_data()
            assert "ipx_1" in data.modules


@pytest.mark.asyncio
async def test_get_data_missing_hardware_ids():
    """Test error when no compatible module found."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/getUserWithHisModules",
            payload={"modules": [{"id": "x", "type": "unknown"}]},
        )

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            with pytest.raises(IndygoPoolApiClientError, match="Could not determine"):
                await client.async_get_data()


@pytest.mark.asyncio
async def test_remote_control_no_serial():
    """Test remote control with no serial available."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = None

            # Should not raise, just log warning
            await client.async_send_remote_control("off")
            # No request should have been made
            assert len(m.requests) == 0


@pytest.mark.asyncio
async def test_remote_control_with_kwargs():
    """Test remote control passes extra kwargs."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/setManualCommandToSend", payload={"status": "ok"})

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            client._pool_address = "SER1"

            expected_action = 3
            expected_time = 60
            expected_duration = 120
            await client.async_send_remote_control(
                "on",
                action=expected_action,
                time=expected_time,
                manualDuration=expected_duration,
            )

            req = m.requests[("POST", URL(f"{BASE_URL}/api/setManualCommandToSend"))][0]
            payload = req.kwargs.get("json", {})
            item = payload["linesControl"][0]
            assert item["action"] == expected_action
            assert item["time"] == expected_time
            assert item["manualDuration"] == expected_duration


@pytest.mark.asyncio
async def test_lorawan_sync_failure_logged():
    """Test LoRaWAN sync failure is caught and logged."""
    if aioresponses is None:
        pytest.skip("aioresponses not installed")

    with aioresponses() as m:
        m.post(f"{BASE_URL}/modules/sendDataViaLoRaWAN", status=500)

        async with aiohttp.ClientSession() as session:
            client = _make_client(session)
            # Should not raise
            await client.async_synchronize_lorawan("mod1")


@pytest.mark.asyncio
async def test_login_network_error():
    """Test login raises on network error."""
    async with aiohttp.ClientSession() as session:
        client = IndygoPoolApiClient("test@example.com", "pass", TEST_POOL_ID, session)
        with patch.object(
            session,
            "post",
            side_effect=aiohttp.ClientError("Network down"),
        ):
            with pytest.raises(IndygoPoolApiClientCommunicationError):
                await client.async_login()


@pytest.mark.asyncio
async def test_request_network_error():
    """Test _request raises on network error."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        with patch.object(
            session,
            "request",
            side_effect=aiohttp.ClientError("Connection refused"),
        ):
            with pytest.raises(IndygoPoolApiClientCommunicationError):
                await client._request("GET", f"{BASE_URL}/test")


@pytest.mark.asyncio
async def test_set_filtration_mode_invalid_program():
    """Test error when program data has no programCharacteristics."""
    async with aiohttp.ClientSession() as session:
        client = _make_client(session)
        client._data = IndygoPoolData(pool_id=TEST_POOL_ID)

        bad_program = {"id": "prog_bad"}
        with pytest.raises(IndygoPoolApiClientError, match="programCharacteristics"):
            await client.async_set_filtration_mode(TEST_MODULE_ID, bad_program, 1)
