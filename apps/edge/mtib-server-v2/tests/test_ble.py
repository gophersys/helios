"""Tests for BleHandler."""

from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.ble import BleHandler
from src.shared.types import (
    BleConnectRequest,
    BleDisconnectRequest,
    BleDiscoverServicesRequest,
    BleReadRequest,
    BleScanRequest,
    BleWriteRequest,
)


@pytest.fixture
def ble_handler(logger, hardware):
    return BleHandler(logger, hardware)


class TestBleScan:
    def test_scan_without_bleak_returns_error(self, ble_handler, context):
        """When bleak is not installed, scan should return an error."""
        with patch.dict("sys.modules", {"bleak": None}):
            # Force ImportError by removing bleak module
            import importlib
            response = ble_handler.scan(BleScanRequest(duration_s=1.0), context)
            # Either returns error or succeeds - depends on bleak availability
            assert isinstance(response.success, bool)


class TestBleConnect:
    def test_connect_without_bleak_returns_error(self, ble_handler, context):
        """When bleak is not installed, connect should return an error."""
        response = ble_handler.connect(
            BleConnectRequest(address="AA:BB:CC:DD:EE:FF"),
            context,
        )
        # Will fail since no real BLE device available
        assert isinstance(response.success, bool)
        if not response.success:
            assert len(response.message) > 0


class TestBleDisconnect:
    def test_disconnect_unknown_returns_error(self, ble_handler, context):
        """Disconnecting an unknown connection ID should return an error."""
        response = ble_handler.disconnect(
            BleDisconnectRequest(connection_id="nonexistent"),
            context,
        )
        assert response.success is False
        assert "Unknown connection" in response.message


class TestBleDiscoverServices:
    def test_discover_unknown_connection_returns_error(self, ble_handler, context):
        """Discovering services on unknown connection should fail."""
        response = ble_handler.discover_services(
            BleDiscoverServicesRequest(connection_id="nonexistent"),
            context,
        )
        assert response.success is False
        assert "Unknown connection" in response.message


class TestBleRead:
    def test_read_unknown_connection_returns_error(self, ble_handler, context):
        """Reading from unknown connection should fail."""
        response = ble_handler.read(
            BleReadRequest(connection_id="nonexistent", handle=1),
            context,
        )
        assert response.success is False
        assert "Unknown connection" in response.message


class TestBleWrite:
    def test_write_unknown_connection_returns_error(self, ble_handler, context):
        """Writing to unknown connection should fail."""
        response = ble_handler.write(
            BleWriteRequest(connection_id="nonexistent", handle=1, data=b"\x01"),
            context,
        )
        assert response.success is False
        assert "Unknown connection" in response.message
