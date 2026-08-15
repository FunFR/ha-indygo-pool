"""Test the Indygo Pool config flow."""

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indygo_pool.api import (
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientCommunicationError,
    IndygoPoolApiClientError,
)
from custom_components.indygo_pool.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

CUSTOM_SCAN_INTERVAL = 120

original_iterdir = pathlib.Path.iterdir


def safe_iterdir(self):
    try:
        return original_iterdir(self)
    except FileNotFoundError:
        return iter([])


pathlib.Path.iterdir = safe_iterdir


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.indygo_pool.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.mark.asyncio
async def test_form_success(hass: HomeAssistant) -> None:
    """Test we get the form and it creates an entry on successful validation."""
    # Test just getting the form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Test submitting the form
    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "test_email",
                CONF_PASSWORD: "test_password",
                CONF_POOL_ID: "test_pool",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test_email"
    assert result2["data"] == {
        CONF_EMAIL: "test_email",
        CONF_PASSWORD: "test_password",
        CONF_POOL_ID: "test_pool",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (IndygoPoolApiClientAuthenticationError, "auth"),
        (IndygoPoolApiClientCommunicationError, "connection"),
        (IndygoPoolApiClientError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test we handle various errors during validation."""
    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        side_effect=exception("test error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_EMAIL: "test_email",
                CONF_PASSWORD: "test_password",
                CONF_POOL_ID: "test_pool",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.asyncio
async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that we abort if the unique id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing pool",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "test_password",
            CONF_POOL_ID: "test_pool",
        },
        source=config_entries.SOURCE_USER,
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_EMAIL: "any_email",
            CONF_PASSWORD: "any_password",
            CONF_POOL_ID: "test_pool",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test a successful reauthentication flow updates the stored password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_EMAIL] == "test_email"


@pytest.mark.asyncio
async def test_reauth_wrong_password(hass: HomeAssistant) -> None:
    """Test reauthentication with an invalid password shows an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        side_effect=IndygoPoolApiClientAuthenticationError("test error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "auth"}
    assert entry.data[CONF_PASSWORD] == "old_password"


@pytest.mark.asyncio
async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Test a successful reconfiguration updates email, password and pool ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "new_email",
                CONF_PASSWORD: "new_password",
                CONF_POOL_ID: "new_pool",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_EMAIL] == "new_email"
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_POOL_ID] == "new_pool"
    assert entry.unique_id == "new_pool"


@pytest.mark.asyncio
async def test_reconfigure_wrong_password(hass: HomeAssistant) -> None:
    """Test reconfiguration with an invalid password shows an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "custom_components.indygo_pool.config_flow.IndygoPoolApiClient.async_get_data",
        side_effect=IndygoPoolApiClientAuthenticationError("test error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test_email",
                CONF_PASSWORD: "wrong_password",
                CONF_POOL_ID: "test_pool",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "auth"}
    assert entry.data[CONF_PASSWORD] == "old_password"


@pytest.mark.asyncio
async def test_reconfigure_pool_id_conflict(hass: HomeAssistant) -> None:
    """Test reconfiguring to a pool ID already used by another entry is rejected."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="other_email",
        data={
            CONF_EMAIL: "other_email",
            CONF_PASSWORD: "other_password",
            CONF_POOL_ID: "other_pool",
        },
        unique_id="other_pool",
    )
    other_entry.add_to_hass(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "old_password",
            CONF_POOL_ID: "other_pool",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "already_configured"}
    assert entry.data[CONF_POOL_ID] == "test_pool"


@pytest.mark.asyncio
async def test_options_flow_default_value(hass: HomeAssistant) -> None:
    """Test the options flow shows the default scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "test_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    (scan_interval_key,) = [key for key in schema if key == CONF_SCAN_INTERVAL]
    assert scan_interval_key.default() == DEFAULT_SCAN_INTERVAL


@pytest.mark.asyncio
async def test_options_flow_changed_interval(hass: HomeAssistant) -> None:
    """Test a changed scan interval is stored in the entry options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_email",
        data={
            CONF_EMAIL: "test_email",
            CONF_PASSWORD: "test_password",
            CONF_POOL_ID: "test_pool",
        },
        unique_id="test_pool",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: CUSTOM_SCAN_INTERVAL},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == CUSTOM_SCAN_INTERVAL
