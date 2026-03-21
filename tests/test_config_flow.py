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
    DOMAIN,
)

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
