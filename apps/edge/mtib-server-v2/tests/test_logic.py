"""Tests for LogicHandler."""

import pytest

from src.providers.handlers.logic import LogicHandler
from src.shared.types import (
    AddDecoderRequest,
    GetDecodedDataRequest,
    LogicCaptureStartRequest,
    LogicCaptureStatusRequest,
    LogicCaptureStopRequest,
)


@pytest.fixture
def logic_handler(logger, hardware):
    return LogicHandler(logger, hardware)


class TestLogicCaptureStart:
    def test_start_returns_capture_id(self, logic_handler, context):
        """Starting a capture should return a capture ID."""
        response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        assert response.success is True
        assert len(response.capture_id) > 0

    def test_start_creates_session(self, logic_handler, context):
        """Starting a capture should create a session."""
        response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        assert response.capture_id in logic_handler._sessions


class TestLogicCaptureStatus:
    def test_status_of_active_capture(self, logic_handler, context):
        """Getting status of an active capture should succeed."""
        start_response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        response = logic_handler.capture_status(
            LogicCaptureStatusRequest(capture_id=start_response.capture_id),
            context,
        )
        assert response.success is True

    def test_status_of_unknown_capture(self, logic_handler, context):
        """Getting status of unknown capture should fail."""
        response = logic_handler.capture_status(
            LogicCaptureStatusRequest(capture_id="nonexistent"),
            context,
        )
        assert response.success is False
        assert "Unknown capture" in response.message


class TestLogicCaptureStop:
    def test_stop_active_capture(self, logic_handler, context):
        """Stopping an active capture should succeed."""
        start_response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        response = logic_handler.capture_stop(
            LogicCaptureStopRequest(capture_id=start_response.capture_id),
            context,
        )
        assert response.success is True
        assert start_response.capture_id not in logic_handler._sessions

    def test_stop_unknown_capture(self, logic_handler, context):
        """Stopping an unknown capture should fail."""
        response = logic_handler.capture_stop(
            LogicCaptureStopRequest(capture_id="nonexistent"),
            context,
        )
        assert response.success is False


class TestAddDecoder:
    def test_add_decoder_to_active_capture(self, logic_handler, context):
        """Adding a decoder to an active capture should succeed."""
        start_response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        response = logic_handler.add_decoder(
            AddDecoderRequest(
                capture_id=start_response.capture_id,
                decoder_name="spi",
                protocol=1,  # PROTOCOL_SPI
            ),
            context,
        )
        assert response.success is True
        assert len(response.decoder_id) > 0

    def test_add_decoder_to_unknown_capture(self, logic_handler, context):
        """Adding a decoder to unknown capture should fail."""
        response = logic_handler.add_decoder(
            AddDecoderRequest(
                capture_id="nonexistent",
                decoder_name="spi",
                protocol=1,  # PROTOCOL_SPI
            ),
            context,
        )
        assert response.success is False


class TestGetDecodedData:
    def test_decoded_data_from_active_capture(self, logic_handler, context):
        """Getting decoded data from active capture should succeed."""
        start_response = logic_handler.capture_start(
            LogicCaptureStartRequest(),
            context,
        )
        response = logic_handler.get_decoded_data(
            GetDecodedDataRequest(capture_id=start_response.capture_id),
            context,
        )
        assert response.success is True

    def test_decoded_data_from_unknown_capture(self, logic_handler, context):
        """Getting decoded data from unknown capture should fail."""
        response = logic_handler.get_decoded_data(
            GetDecodedDataRequest(capture_id="nonexistent"),
            context,
        )
        assert response.success is False
