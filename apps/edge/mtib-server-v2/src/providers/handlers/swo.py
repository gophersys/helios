"""SWO (Serial Wire Output) trace handler."""

import time
from typing import TYPE_CHECKING, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    Empty,
    Response,
    SwoStartRequest,
    SwoStreamResponse,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class SwoHandler:
    """Handles SWO RPCs (SwoStart, SwoStop, SwoStream)."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._running = False
        self._port_mask = 0

    def start(self, request: SwoStartRequest, context) -> Response:
        """Start SWO trace capture."""
        try:
            # TODO: Configure SWO via pyocd/pylink
            self._running = True
            self._port_mask = request.port_mask
            self.logger.info(
                f"SWO started: cpu_freq={request.cpu_freq_hz}Hz, "
                f"swo_freq={request.swo_freq_hz}Hz, port_mask=0x{request.port_mask:04X}"
            )
            return Response(success=True, message="SWO started")
        except Exception as e:
            return Response(success=False, message=str(e))

    def stop(self, request: Empty, context) -> Response:
        """Stop SWO trace capture."""
        self._running = False
        self.logger.info("SWO stopped")
        return Response(success=True, message="SWO stopped")

    def stream(self, request: Empty, context) -> Iterator[SwoStreamResponse]:
        """Server-streaming SWO trace data."""
        self.logger.info("SWO stream started")
        try:
            while self._running and context.is_active():
                # TODO: Read SWO data from debug probe
                # For now, sleep to avoid busy-waiting
                time.sleep(0.01)

                # TODO: Yield actual SWO data from pyocd/pylink when available
        except Exception as e:
            self.logger.error(f"SWO stream error: {e}")
        finally:
            self.logger.info("SWO stream ended")
        # Ensure this is a generator function even when no data is yielded
        return
        yield  # pragma: no cover
