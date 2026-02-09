from typing import Iterator, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import RttStartRequest, RttStopRequest, RttStreamRequest

from ._base import BaseClient


class RttMixin(BaseClient):
    """RTT (Real-Time Transfer) operations."""

    def rtt_start(
        self, session_id: str, control_block_address: int = 0
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Start RTT on a debug session.

        Args:
            session_id: Active debug session ID.
            control_block_address: RTT control block address (0 for auto-detect).

        Returns:
            (error, num_up_channels, num_down_channels) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "RttStart",
                RttStartRequest(
                    session_id=session_id, control_block_address=control_block_address
                ),
            )
            if not resp.success:
                return resp.message, None, None
            return None, resp.num_up_channels, resp.num_down_channels
        except Exception as e:
            return f"rtt_start error: {e}", None, None

    def rtt_stop(self, session_id: str) -> Optional[str]:
        """Stop RTT on a debug session.

        Args:
            session_id: Active debug session ID.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("RttStop", RttStopRequest(session_id=session_id))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"rtt_stop error: {e}"

    def rtt_stream(
        self, request_iterator: Iterator[RttStreamRequest], timeout: float = None
    ) -> Iterator:
        """Open a bidirectional RTT stream.

        Args:
            request_iterator: Iterator of RttStreamRequest messages to send.
            timeout: Stream timeout in seconds.

        Returns:
            Iterator of RttStreamResponse messages from the server.
        """
        return self._bidi_stream("RttStream", request_iterator, timeout=timeout)
