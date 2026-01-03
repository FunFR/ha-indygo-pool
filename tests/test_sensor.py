import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indygo_pool.const import DOMAIN


@pytest.mark.asyncio
async def test_sensors(hass: HomeAssistant):
    """Test sensor setup."""
    # Load fixture
    with open("tests/fixtures/data.json") as f:
        data = json.load(f)

    # Setup Mock Entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Indygo Pool",
        data={
            "email": "user@example.com",
            "password": "test_password",
            "pool_id": "FAKE_POOL_ID",  # Using ID from dump
        },
    )
    entry.add_to_hass(hass)

    # Patch the API client in coordinator
    # Note: The coordinator imports IndygoPoolApiClient from .api
    with patch(
        "custom_components.indygo_pool.coordinator.IndygoPoolApiClient"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.async_get_data = AsyncMock(return_value=data)
        mock_api.async_login = AsyncMock(return_value=True)

        # Start setup
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify Water Temperature
        # Name: "Temp. eau" -> slugify -> "temp_eau"
        # Since has_entity_name is not explicitly True, and name is "Temp. eau",
        # if the device name is "Indygo Pool", HA might just use "Temp. eau".
        # Let's search for the entity.
        entity_id = "sensor.temp_eau"
        state = hass.states.get(entity_id)

        # If not found, list all states to debug
        if not state:
            print("All states:", [s.entity_id for s in hass.states.async_all()])

        assert state
        assert state.state == "5.27"
        assert state.attributes.get("unit_of_measurement") == "°C"

        # Verify pH
        entity_id_ph = "sensor.ph"
        state_ph = hass.states.get(entity_id_ph)
        if not state_ph:
            # Try other naming
            state_ph = hass.states.get("sensor.indygo_pool_ph")

        assert state_ph
        assert state_ph.state == "7.2"

        # Verify Salt
        # Name might be "Sel" -> sensor.sel
        # Value 2.5 (from analysis) but strictly from fixture
        # Check what is in fixture for Salt.
