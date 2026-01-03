"""Global fixtures for Indygo Pool integration."""

import pytest

# This fixture enables loading custom integrations in all tests.
# Usually required for test_sensor.py to find the integration.
pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
