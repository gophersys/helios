"""Shared test fixtures for MTIB server tests.

Run tests from the mtib-server directory:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/ -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure src/ is importable
_server_root = Path(__file__).parent.parent
if str(_server_root / "src") not in sys.path:
    sys.path.insert(0, str(_server_root / "src"))


@pytest.fixture
def mock_logger():
    """Create a mock Logger that supports from_parent() chaining."""
    logger = MagicMock()
    logger.from_parent.return_value = logger
    return logger


@pytest.fixture
def mock_grpc_context():
    """Create a mock gRPC ServicerContext."""
    context = MagicMock()
    context.peer.return_value = "ipv4:127.0.0.1:12345"
    context.is_active.return_value = True
    return context
