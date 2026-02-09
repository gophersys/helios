from typing import Iterator, Optional

from protocols.mtib_v2.mtib_v2_pb2 import Empty, SwoStartRequest, SwoStreamResponse

from ._base import BaseClient


class SwoMixin(BaseClient):
    """SWO/ITM trace operations."""

    def swo_start(
        self,
        session_id: str,
        cpu_freq_hz: int,
        swo_freq_hz: int,
        port_mask: int = 0xFFFFFFFF,
    ) -> Optional[str]:
        """Start SWO/ITM trace capture.

        Args:
            session_id: Active debug session ID.
            cpu_freq_hz: Target CPU frequency in Hz.
            swo_freq_hz: SWO clock frequency in Hz.
            port_mask: Bitmask of ITM stimulus ports to enable.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "SwoStart",
                SwoStartRequest(
                    session_id=session_id,
                    cpu_freq_hz=cpu_freq_hz,
                    swo_freq_hz=swo_freq_hz,
                    port_mask=port_mask,
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"swo_start error: {e}"

    def swo_stop(self) -> Optional[str]:
        """Stop SWO/ITM trace capture.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("SwoStop", Empty())
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"swo_stop error: {e}"

    def swo_stream(self, timeout: float = None) -> Iterator[SwoStreamResponse]:
        """Stream SWO/ITM trace data.

        Args:
            timeout: Stream timeout in seconds.

        Returns:
            Iterator of SwoStreamResponse messages with port, data, and timestamp.
        """
        return self._server_stream("SwoStream", Empty(), timeout=timeout)
