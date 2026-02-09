"""Logic analyzer handler for V2 protocol."""

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict

from corekinect.utils import Logger
from src.shared.types import (
    AddDecoderRequest,
    AddDecoderResponse,
    GetDecodedDataRequest,
    GetDecodedDataResponse,
    LogicCaptureStartRequest,
    LogicCaptureStartResponse,
    LogicCaptureStatusRequest,
    LogicCaptureStatusResponse,
    LogicCaptureStopRequest,
    Response,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


@dataclass
class CaptureSession:
    """Tracks state for a logic capture session."""
    capture_id: str
    config: object  # LogicCaptureConfig
    status: int = 0  # STATUS_WAITING_TRIGGER
    progress: float = 0.0
    decoders: Dict[str, object] = field(default_factory=dict)  # decoder_id -> config


class LogicHandler:
    """Handles logic analyzer RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._sessions: Dict[str, CaptureSession] = {}

    def capture_start(self, request: LogicCaptureStartRequest, context) -> LogicCaptureStartResponse:
        """Start a logic capture session."""
        try:
            capture_id = str(uuid.uuid4())
            session = CaptureSession(
                capture_id=capture_id,
                config=request.config,
            )
            self._sessions[capture_id] = session

            # TODO: Start actual capture via sigrok/Saleae
            self.logger.info(f"Logic capture started: {capture_id}")
            return LogicCaptureStartResponse(success=True, message="", capture_id=capture_id)
        except Exception as e:
            return LogicCaptureStartResponse(success=False, message=str(e), capture_id="")

    def capture_status(self, request: LogicCaptureStatusRequest, context) -> LogicCaptureStatusResponse:
        """Get status of a logic capture session."""
        session = self._sessions.get(request.capture_id)
        if session is None:
            return LogicCaptureStatusResponse(
                success=False,
                message=f"Unknown capture: {request.capture_id}",
            )

        return LogicCaptureStatusResponse(
            success=True,
            message="",
            status=session.status,
            progress=session.progress,
        )

    def capture_stop(self, request: LogicCaptureStopRequest, context) -> Response:
        """Stop a logic capture session."""
        session = self._sessions.pop(request.capture_id, None)
        if session is None:
            return Response(success=False, message=f"Unknown capture: {request.capture_id}")

        # TODO: Stop actual capture via sigrok/Saleae
        self.logger.info(f"Logic capture stopped: {request.capture_id}")
        return Response(success=True, message="Capture stopped")

    def add_decoder(self, request: AddDecoderRequest, context) -> AddDecoderResponse:
        """Add a protocol decoder to a capture session."""
        session = self._sessions.get(request.capture_id)
        if session is None:
            return AddDecoderResponse(
                success=False,
                message=f"Unknown capture: {request.capture_id}",
                decoder_id="",
            )

        decoder_id = str(uuid.uuid4())
        session.decoders[decoder_id] = {
            "name": request.decoder_name,
            "protocol": request.protocol,
        }

        # TODO: Configure actual decoder via sigrok
        return AddDecoderResponse(success=True, message="", decoder_id=decoder_id)

    def get_decoded_data(self, request: GetDecodedDataRequest, context) -> GetDecodedDataResponse:
        """Get decoded protocol data from a capture session."""
        session = self._sessions.get(request.capture_id)
        if session is None:
            return GetDecodedDataResponse(
                success=False,
                message=f"Unknown capture: {request.capture_id}",
            )

        # TODO: Get actual decoded data from sigrok
        return GetDecodedDataResponse(success=True, message="", data=[])
