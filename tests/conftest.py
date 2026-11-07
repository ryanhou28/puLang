"""Shared fixtures."""

from __future__ import annotations

import os

import pytest

from pypulang.backends.kaidaw.client import KaidawClient, WslTransport, default_transport
from tests.fake_kaidaw import FakeKaidaw


def _real_client() -> KaidawClient | None:
    """A client for a real server, if KAIDAW_TEST_PORT names one."""
    port = os.environ.get("KAIDAW_TEST_PORT")
    if not port:
        return None
    transport = (
        WslTransport(int(port))
        if os.environ.get("KAIDAW_TEST_WSL")
        else default_transport(int(port))
    )
    return KaidawClient(transport=transport)


def _clear(client: KaidawClient) -> None:
    projection = client.projection("detail")
    operations = [
        {"type": "DeleteTrack", "trackId": t["id"]}
        for t in projection["tracks"]
        if not t.get("isMaster")
    ]
    if operations:
        client.apply(operations, projection["revision"], "test reset")


@pytest.fixture(params=["fake", "real"])
def client(request) -> KaidawClient:
    """The same assertions, against a fake and against the real engine."""
    if request.param == "fake":
        return KaidawClient(transport=FakeKaidaw())
    real = _real_client()
    if real is None:
        pytest.skip("set KAIDAW_TEST_PORT to run against a real kaiDAW server")
    _clear(real)
    return real
