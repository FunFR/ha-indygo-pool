"""Tests for the Indygo Pool Data Update Coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.indygo_pool.api import (
    IndygoPoolApiClient,
    IndygoPoolApiClientAuthenticationError,
    IndygoPoolApiClientError,
)
from custom_components.indygo_pool.coordinator import IndygoPoolDataUpdateCoordinator


@pytest.fixture
def mock_client():
    """Mock the API client."""
    client = MagicMock(spec=IndygoPoolApiClient)
    client.async_get_data = AsyncMock()
    return client


@pytest.fixture
def mock_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_id"
    return entry


def test_coordinator_init(hass, mock_client, mock_entry):
    """Test coordinator initialization."""
    coordinator = IndygoPoolDataUpdateCoordinator(hass, mock_client, mock_entry)
    assert coordinator.client == mock_client
    assert coordinator.name == "indygo_pool"
    expected_interval = 300
    assert coordinator.update_interval.total_seconds() == expected_interval


@pytest.mark.asyncio
async def test_coordinator_update_success(hass, mock_client, mock_entry):
    """Test successful data update via coordinator."""
    coordinator = IndygoPoolDataUpdateCoordinator(hass, mock_client, mock_entry)
    mock_data = MagicMock()
    mock_client.async_get_data.return_value = mock_data

    result = await coordinator._async_update_data()
    assert result == mock_data
    mock_client.async_get_data.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_update_auth_error(hass, mock_client, mock_entry):
    """Test auth error during data update."""
    coordinator = IndygoPoolDataUpdateCoordinator(hass, mock_client, mock_entry)
    mock_client.async_get_data.side_effect = IndygoPoolApiClientAuthenticationError

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_update_api_error(hass, mock_client, mock_entry):
    """Test api error during data update."""
    coordinator = IndygoPoolDataUpdateCoordinator(hass, mock_client, mock_entry)
    mock_client.async_get_data.side_effect = IndygoPoolApiClientError

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
