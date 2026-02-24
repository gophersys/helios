"""Pytest fixtures for MTIB V2 handler tests."""

import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# Mock hardware dependencies before any imports
_mock_gpiod = MagicMock()
_mock_gpiod.line.Direction.INPUT = "input"
_mock_gpiod.line.Direction.OUTPUT = "output"
_mock_gpiod.line.Value.ACTIVE = 1
_mock_gpiod.line.Value.INACTIVE = 0
sys.modules.setdefault("gpiod", _mock_gpiod)
sys.modules.setdefault("gpiod.line", _mock_gpiod.line)

_mock_smbus = MagicMock()
sys.modules.setdefault("smbus", _mock_smbus)
sys.modules.setdefault("smbus2", _mock_smbus)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.mocks.hardware import MockGrpcContext, MockHardwareContext, MockLogger
from src.hardware.revision import HardwareRevision


@pytest.fixture
def logger():
    """Create a mock logger."""
    return MockLogger()


@pytest.fixture
def hardware():
    """Create a mock hardware context (REV 1.1)."""
    return MockHardwareContext()


@pytest.fixture
def context():
    """Create a mock gRPC context."""
    return MockGrpcContext()


@pytest.fixture
def hardware_rev12():
    """Create a mock hardware context (REV 1.2)."""
    return MockHardwareContext(revision=HardwareRevision.REV_1_2)


@pytest.fixture
def assets_dir():
    """Create a temporary assets directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
