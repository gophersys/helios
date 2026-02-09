"""Tests for SwoHandler."""

import pytest

from src.providers.handlers.swo import SwoHandler
from src.shared.types import (
    Empty,
    SwoStartRequest,
)


@pytest.fixture
def swo_handler(logger, hardware):
    return SwoHandler(logger, hardware)


class TestSwoStart:
    def test_start_succeeds(self, swo_handler, context):
        """Starting SWO capture should succeed."""
        response = swo_handler.start(
            SwoStartRequest(
                cpu_freq_hz=64000000,
                swo_freq_hz=4000000,
                port_mask=0x0001,
            ),
            context,
        )
        assert response.success is True
        assert swo_handler._running is True
        assert swo_handler._port_mask == 0x0001


class TestSwoStop:
    def test_stop_succeeds(self, swo_handler, context):
        """Stopping SWO capture should succeed."""
        swo_handler.start(
            SwoStartRequest(cpu_freq_hz=64000000, swo_freq_hz=4000000, port_mask=0x0001),
            context,
        )
        response = swo_handler.stop(Empty(), context)
        assert response.success is True
        assert swo_handler._running is False

    def test_stop_when_not_running(self, swo_handler, context):
        """Stopping when not running should still succeed."""
        response = swo_handler.stop(Empty(), context)
        assert response.success is True


class TestSwoStream:
    def test_stream_when_not_running_exits_immediately(self, swo_handler, context):
        """Streaming when not running should exit immediately."""
        # SWO stream exits when _running is False
        responses = list(swo_handler.stream(Empty(), context))
        assert len(responses) == 0

    def test_stream_stops_when_context_inactive(self, swo_handler, context):
        """Streaming should stop when context becomes inactive."""
        swo_handler._running = True
        context.cancel()  # Make context inactive
        responses = list(swo_handler.stream(Empty(), context))
        assert len(responses) == 0
