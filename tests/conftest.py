import inspect
import socket
from unittest.mock import Mock

import aiohttp
import pytest

# aiohttp 3.14 made ``stream_writer`` a required keyword-only argument of
# ``ClientResponse.__init__``. aioresponses (0.7.9, latest) builds its mocked
# responses without it, so every mocked request raises a TypeError. aiohttp only
# reads ``stream_writer.output_size``, so a mock exposing that is enough.
# Tracked upstream in https://github.com/pnuckowski/aioresponses/issues/289;
# the signature guard turns this into a no-op once a release supplies it.
_response_init = aiohttp.ClientResponse.__init__
if "stream_writer" in inspect.signature(_response_init).parameters:

    def _patched_response_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("stream_writer", Mock(output_size=0))
        _response_init(self, *args, **kwargs)

    aiohttp.ClientResponse.__init__ = _patched_response_init  # type: ignore[method-assign]

try:
    from pytest_socket import enable_socket, socket_allow_hosts
except ImportError:
    # If pytest-socket is not installed/loaded, define dummy functions
    def enable_socket():
        pass

    def socket_allow_hosts(*args, **kwargs):
        pass


# pytest-homeassistant-custom-component patches socket.getaddrinfo/gethostbyname
# before every test (unconditionally, with no fixture to opt back in) to block
# accidental DNS resolution. Capture the pristine functions now, at collection
# time, before that patch is ever applied, so integration tests can restore real
# DNS resolution for the real MyIndygo hostname.
_real_getaddrinfo = socket.getaddrinfo
_real_gethostbyname = socket.gethostbyname


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def allow_socket_fixture(request, monkeypatch):
    """Enable real networking for tests marked `integration`.

    Restoring the real resolver must happen before `socket_allow_hosts`, which
    itself calls `socket.getaddrinfo` to resolve "myindygo.com" into the
    allow-list — with the patched resolver still active it raises
    "DNS resolution disabled in tests" instead of returning an address.
    """
    if request.node.get_closest_marker("integration"):
        monkeypatch.setattr(socket, "getaddrinfo", _real_getaddrinfo)
        monkeypatch.setattr(socket, "gethostbyname", _real_gethostbyname)
        enable_socket()
        socket_allow_hosts(
            ["127.0.0.1", "localhost", "::1", "myindygo.com"],
            allow_unix_socket=True,
        )


pytest_plugins = "pytest_homeassistant_custom_component"
