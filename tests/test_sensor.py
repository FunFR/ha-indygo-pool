"""Indygo Pool sensors tests."""

from homeassistant.core import HomeAssistant
from custom_components.indygo_pool.const import DOMAIN

async def test_sensor_init(hass: HomeAssistant):
    """Test sensor initialization."""
    # This is a placeholder for actual tests
    assert DOMAIN == "indygo_pool"
