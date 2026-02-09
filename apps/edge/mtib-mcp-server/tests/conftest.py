"""Pytest fixtures for MTIB MCP server tests."""

from __future__ import annotations

import os
import sys

import pytest_asyncio

# Ensure the MCP server source is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from tests.mock_mtib_server import start_server
from mtib_mcp.grpc_client import MtibClient


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def mock_server():
    """Start the mock gRPC server once for the whole test session."""
    server, port = await start_server(port=0)
    yield server, port
    await server.stop(grace=0.5)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def grpc_client(mock_server):
    """Create an MtibClient connected to the mock server."""
    _, port = mock_server
    os.environ["MTIB_HOST"] = "localhost"
    os.environ["MTIB_PORT"] = str(port)
    client = MtibClient()
    await client.connect()
    yield client
    await client.close()
