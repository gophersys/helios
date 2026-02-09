"""Shared test fixtures for MTIB V2 client tests."""

import pytest

from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig
from .mock_server import create_mock_server


@pytest.fixture(scope="session")
def mock_server():
    """Start a mock MTIB V2 gRPC server for the test session."""
    server, port = create_mock_server()
    yield port
    server.stop(grace=0)


@pytest.fixture
def client(mock_server):
    """Create an MtibV2Client connected to the mock server."""
    config = ClientConfig(
        net=NetConfig(addr="127.0.0.1", port=mock_server),
        timeout_s=5.0,
    )
    c = MtibV2Client(config)
    err = c.connect()
    assert err is None, f"Failed to connect to mock server: {err}"
    yield c
    c.disconnect()
