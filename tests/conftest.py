import pytest
from pytest_socket import enable_socket, socket_allow_hosts


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def allow_socket_fixture(request):
    """Enable socket for integration tests."""
    if request.node.get_closest_marker("integration"):
        enable_socket()
        socket_allow_hosts(
            ["127.0.0.1", "localhost", "::1", "62.210.52.36"],
            allow_unix_socket=True,
        )


pytest_plugins = "pytest_homeassistant_custom_component"
