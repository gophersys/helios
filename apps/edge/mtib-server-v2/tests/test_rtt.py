"""Tests for RttHandler."""

import pytest

from src.providers.handlers.rtt import RttHandler
from src.shared.types import (
    RttStartRequest,
    RttStopRequest,
    RttStreamRequest,
)


@pytest.fixture
def rtt_handler(logger, hardware):
    return RttHandler(logger, hardware)


class TestRttStart:
    def test_start_succeeds(self, rtt_handler, context):
        """Starting RTT should succeed and return channel counts."""
        response = rtt_handler.start(
            RttStartRequest(session_id="session1"),
            context,
        )
        assert response.success is True
        assert response.num_up_channels >= 1
        assert response.num_down_channels >= 1
        assert "session1" in rtt_handler._active_sessions

    def test_start_multiple_sessions(self, rtt_handler, context):
        """Starting multiple RTT sessions should work."""
        rtt_handler.start(RttStartRequest(session_id="s1"), context)
        rtt_handler.start(RttStartRequest(session_id="s2"), context)
        assert len(rtt_handler._active_sessions) == 2


class TestRttStop:
    def test_stop_active_session(self, rtt_handler, context):
        """Stopping an active session should succeed."""
        rtt_handler.start(RttStartRequest(session_id="session1"), context)
        response = rtt_handler.stop(
            RttStopRequest(session_id="session1"),
            context,
        )
        assert response.success is True
        assert "session1" not in rtt_handler._active_sessions

    def test_stop_nonexistent_session(self, rtt_handler, context):
        """Stopping a nonexistent session should fail."""
        response = rtt_handler.stop(
            RttStopRequest(session_id="nonexistent"),
            context,
        )
        assert response.success is False
        assert "No RTT session" in response.message


class TestRttStream:
    def test_stream_without_active_session(self, rtt_handler, context):
        """Streaming without an active session should return error."""
        requests = iter([
            RttStreamRequest(session_id="nonexistent", channel=0, data=b""),
        ])
        responses = list(rtt_handler.stream(requests, context))
        assert len(responses) > 0
        assert responses[0].success is False

    def test_stream_with_active_session(self, rtt_handler, context):
        """Streaming with an active session should return data."""
        rtt_handler.start(RttStartRequest(session_id="session1"), context)

        requests = iter([
            RttStreamRequest(session_id="session1", channel=0, data=b"hello"),
        ])
        responses = list(rtt_handler.stream(requests, context))
        assert len(responses) > 0
        assert responses[0].success is True
