"""Tests for the Indygo Pool __init__."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indygo_pool import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.indygo_pool.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POOL_ID,
    DOMAIN,
)


@pytest.fixture
def mock_client_update():
    """Mock the API client data update."""
    with patch(
        "custom_components.indygo_pool.IndygoPoolApiClient.async_get_data",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_setup_and_unload_entry(hass: HomeAssistant, mock_client_update):
    """Test setting up and unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_POOL_ID: "123456",
        },
    )
    entry.add_to_hass(hass)

    # Mock entry state to SETUP_IN_PROGRESS to avoid first_refresh check failure
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as mock_forward:
        # Setup the entry
        setup_result = await async_setup_entry(hass, entry)

        assert setup_result is True
        mock_client_update.assert_called_once()
        mock_forward.assert_called_once_with(entry, PLATFORMS)
        assert entry.entry_id in hass.data[DOMAIN]

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        # Unload the entry
        unload_result = await async_unload_entry(hass, entry)

        assert unload_result is True
        mock_unload.assert_called_once_with(entry, PLATFORMS)
        assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_setup_entry_update_failed(hass: HomeAssistant):
    """Test setup entry when update fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_POOL_ID: "123456",
        },
    )
    entry.add_to_hass(hass)

    # Mock entry state to SETUP_IN_PROGRESS
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with patch(
        "custom_components.indygo_pool.IndygoPoolApiClient.async_get_data",
        side_effect=Exception("Test Error"),
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
