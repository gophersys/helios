"""Pytest fixtures for MTIB V2 handler tests."""

import os
import sys
import tempfile

import pytest

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
