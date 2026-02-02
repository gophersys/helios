"""Shared fixtures for integration tests."""

import os
import pytest
import sys

# Add paths for imports
sys.path.insert(0, "/home/mateo/work/concord/concord/libs")
sys.path.insert(0, "/home/mateo/work/concord/concord/libs/python")

from corekinect.mtib_client.v2 import MtibV2Client, NetConfig


@pytest.fixture(scope="module")
def server_address():
    """Get server address from environment."""
    host = os.environ.get("SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SERVER_PORT", "50052"))
    return host, port


@pytest.fixture(scope="module")
def client(server_address):
    """Create connected V2 client for tests.

    This fixture creates a client, connects to the server,
    and disconnects after all tests in the module complete.
    """
    host, port = server_address
    c = MtibV2Client(
        config=MtibV2Client.Config(
            net=NetConfig(addr=host, port=port)
        )
    )

    error = c.connect()
    if error:
        pytest.skip(f"Could not connect to server at {host}:{port}: {error}")

    yield c

    c.disconnect()
