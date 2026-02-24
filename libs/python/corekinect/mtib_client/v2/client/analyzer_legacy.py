from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    AddDecoderRequest,
    GetDecodedDataRequest,
    AnalyzerCaptureConfig,
    AnalyzerCaptureStartRequest,
    AnalyzerCaptureStatusRequest,
    AnalyzerCaptureStopRequest,
    AnalyzerChannelConfig,
)

from ._base import BaseClient


class LogicMixin(BaseClient):
    """Logic analyzer operations."""

    def logic_capture_start(
        self, config: AnalyzerCaptureConfig
    ) -> Tuple[Optional[str], Optional[str]]:
        """Start a logic capture.

        Args:
            config: AnalyzerCaptureConfig protobuf message with channel and trigger settings.

        Returns:
            (error, capture_id) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "AnalyzerCaptureStart", AnalyzerCaptureStartRequest(config=config)
            )
            if not resp.success:
                return resp.message, None
            return None, resp.capture_id
        except Exception as e:
            return f"logic_capture_start error: {e}", None

    def logic_capture_status(
        self, capture_id: str
    ) -> Tuple[Optional[str], Optional[int], Optional[float]]:
        """Get logic capture status.

        Args:
            capture_id: Capture ID from logic_capture_start.

        Returns:
            (error, status, progress) tuple. error is None on success.
            status: 0=WAITING_TRIGGER, 1=CAPTURING, 2=COMPLETE, 3=ERROR.
            progress: 0.0 to 1.0.
        """
        try:
            resp = self._call(
                "AnalyzerCaptureStatus", AnalyzerCaptureStatusRequest(capture_id=capture_id)
            )
            if not resp.success:
                return resp.message, None, None
            return None, resp.status, resp.progress
        except Exception as e:
            return f"logic_capture_status error: {e}", None, None

    def logic_capture_stop(self, capture_id: str) -> Optional[str]:
        """Stop a logic capture.

        Args:
            capture_id: Capture ID from logic_capture_start.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "AnalyzerCaptureStop", AnalyzerCaptureStopRequest(capture_id=capture_id)
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"logic_capture_stop error: {e}"

    def add_decoder(
        self, capture_id: str, decoder_name: str, protocol: int, **kwargs
    ) -> Tuple[Optional[str], Optional[str]]:
        """Add a protocol decoder to a capture.

        Args:
            capture_id: Capture ID from logic_capture_start.
            decoder_name: Human-readable decoder name.
            protocol: Protocol enum value (0=I2C, 1=SPI, 2=UART, etc.).
            **kwargs: Protocol-specific config passed as keyword arguments.

        Returns:
            (error, decoder_id) tuple. error is None on success.
        """
        try:
            req = AddDecoderRequest(
                capture_id=capture_id, decoder_name=decoder_name, protocol=protocol
            )
            resp = self._call("AddDecoder", req)
            if not resp.success:
                return resp.message, None
            return None, resp.decoder_id
        except Exception as e:
            return f"add_decoder error: {e}", None

    def get_decoded_data(
        self, capture_id: str, decoder_id: str = ""
    ) -> Tuple[Optional[str], list]:
        """Get decoded protocol data from a capture.

        Args:
            capture_id: Capture ID from logic_capture_start.
            decoder_id: Decoder ID (empty for all decoders).

        Returns:
            (error, decoded_data) tuple. error is None on success.
            decoded_data is a list of DecodedData protobuf messages.
        """
        try:
            resp = self._call(
                "GetDecodedData",
                GetDecodedDataRequest(capture_id=capture_id, decoder_id=decoder_id),
            )
            if not resp.success:
                return resp.message, []
            return None, list(resp.data)
        except Exception as e:
            return f"get_decoded_data error: {e}", []
