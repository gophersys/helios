"""Tests for CanHandler."""

from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.can import CanHandler
from src.shared.types import (
    CanConfig,
    CanFrame,
    CanSendRequest,
    CanSetFilterRequest,
    Empty,
)


@pytest.fixture
def can_handler(logger, hardware):
    return CanHandler(logger, hardware)


class TestCanConfigure:
    def test_configure_without_python_can_returns_error(self, can_handler, context):
        """When python-can is not installed, configure should return an error."""
        with patch.dict("sys.modules", {"can": None}):
            response = can_handler.configure(
                CanConfig(bus=0, bitrate=500000),
                context,
            )
            # Will raise ImportError since we patched 'can' to None
            assert response.success is False
            assert "not available" in response.message or "None" in response.message

    def test_configure_stores_bus(self, can_handler, context):
        """Verify configure creates the bus object."""
        mock_can = MagicMock()
        mock_bus = MagicMock()
        mock_can.interface.Bus.return_value = mock_bus

        with patch.dict("sys.modules", {"can": mock_can}):
            response = can_handler.configure(
                CanConfig(bus=0, bitrate=500000),
                context,
            )

        assert response.success is True
        assert can_handler._bus is mock_bus

    def test_reconfigure_shuts_down_previous_bus(self, can_handler, context):
        """Reconfiguring should shut down the previous bus."""
        old_bus = MagicMock()
        can_handler._bus = old_bus

        mock_can = MagicMock()
        mock_new_bus = MagicMock()
        mock_can.interface.Bus.return_value = mock_new_bus

        with patch.dict("sys.modules", {"can": mock_can}):
            response = can_handler.configure(
                CanConfig(bus=0, bitrate=250000),
                context,
            )

        assert response.success is True
        old_bus.shutdown.assert_called_once()
        assert can_handler._bus is mock_new_bus


class TestCanSend:
    def test_send_without_bus_returns_error(self, can_handler, context):
        """Sending without configuring the bus should fail."""
        response = can_handler.send(
            CanSendRequest(frame=CanFrame(id=0x100, data=b"\x01\x02")),
            context,
        )
        assert response.success is False
        assert "not configured" in response.message

    def test_send_with_configured_bus(self, can_handler, context):
        """Sending with a configured bus should succeed."""
        mock_can = MagicMock()
        mock_bus = MagicMock()
        can_handler._bus = mock_bus

        with patch.dict("sys.modules", {"can": mock_can}):
            response = can_handler.send(
                CanSendRequest(frame=CanFrame(id=0x100, data=b"\x01\x02")),
                context,
            )

        assert response.success is True
        mock_bus.send.assert_called_once()


class TestCanSetFilter:
    def test_filter_without_bus_returns_error(self, can_handler, context):
        """Setting filters without configuring the bus should fail."""
        response = can_handler.set_filter(
            CanSetFilterRequest(filters=[]),
            context,
        )
        assert response.success is False
        assert "not configured" in response.message


class TestCanReceive:
    def test_receive_without_bus_returns_error(self, can_handler, context):
        """Receiving without configuring the bus should fail."""
        responses = list(can_handler.receive(Empty(), context))
        assert len(responses) == 1
        assert responses[0].success is False
        assert "not configured" in responses[0].message
