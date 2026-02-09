"""RTT (Real-Time Transfer) handler for Segger RTT protocol."""

import time
from typing import TYPE_CHECKING, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    Response,
    RttStartRequest,
    RttStartResponse,
    RttStopRequest,
    RttStreamRequest,
    RttStreamResponse,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class RttHandler:
    """Handles RTT RPCs (RttStart, RttStop, RttStream)."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._active_sessions: dict[str, bool] = {}  # session_id -> running

    def start(self, request: RttStartRequest, context) -> RttStartResponse:
        """Start RTT on a debug session."""
        try:
            # TODO: Start RTT via pylink/pyocd using request.control_block_address
            self._active_sessions[request.session_id] = True
            self.logger.info(f"RTT started for session {request.session_id}")
            return RttStartResponse(
                success=True,
                message="RTT started",
                num_up_channels=1,
                num_down_channels=1,
            )
        except Exception as e:
            return RttStartResponse(success=False, message=str(e), num_up_channels=0, num_down_channels=0)

    def stop(self, request: RttStopRequest, context) -> Response:
        """Stop RTT on a debug session."""
        if request.session_id in self._active_sessions:
            self._active_sessions[request.session_id] = False
            del self._active_sessions[request.session_id]
            self.logger.info(f"RTT stopped for session {request.session_id}")
            return Response(success=True, message="RTT stopped")
        return Response(success=False, message=f"No RTT session: {request.session_id}")

    def stream(self, request_iterator: Iterator[RttStreamRequest], context) -> Iterator[RttStreamResponse]:
        """Bidirectional RTT streaming."""
        session_id = None
        try:
            for request in request_iterator:
                if not context.is_active():
                    break

                if session_id is None:
                    session_id = request.session_id
                    if session_id not in self._active_sessions:
                        yield RttStreamResponse(
                            success=False,
                            message=f"RTT not started for session {session_id}",
                        )
                        return

                # Handle outgoing data (host -> target)
                if request.data:
                    # TODO: Write data to RTT down channel via pylink/pyocd
                    self.logger.debug(f"RTT TX: {len(request.data)} bytes on channel {request.channel}")

                # TODO: Read data from RTT up channel via pylink/pyocd
                # For now, yield empty response to keep stream alive
                now = time.time()
                yield RttStreamResponse(
                    success=True,
                    message="",
                    channel=request.channel,
                    data=b"",
                    timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                )

        except Exception as e:
            self.logger.error(f"RTT stream error: {e}")
        finally:
            self.logger.info(f"RTT stream ended for session {session_id}")
