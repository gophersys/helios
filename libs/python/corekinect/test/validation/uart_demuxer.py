"""UART line router for debug build log capture.

Stage 4 mode: all lines go to log_buffer (no harness prefixes).
Designed for Stage 3 extensibility: adding CONCORD prefix routing
is a future upgrade that adds response_queue and event_queue.
"""

import re
import threading
import time
from typing import List, Optional, Tuple

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import Logger
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

log = Logger(log_name="uart_demuxer")

# Stage 3 prefix constants (unused in Stage 4, defined for future use)
CONCORD_RSP_PREFIX = "[CONCORD:RSP] "
CONCORD_EVT_PREFIX = "[CONCORD:EVT] "


class UartDemuxer:
    """UART log capture for debug firmware builds.

    Subscribes to MTIB V1 UartStream RPC and captures all output
    to a timestamped log buffer. In Stage 4, there are no CONCORD
    harness prefixes — all lines are treated as log output.

    Args:
        mtib: Connected MtibV1Client instance.
        target: UART target (default: nRF52840 app processor).
        enable_harness_routing: Reserved for Stage 3 (default: False).
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        target: HostType = HostType.HOST_TYPE_NRF52840,
        enable_harness_routing: bool = False,
    ):
        self._mtib = mtib
        self._target = target
        self._enable_harness = enable_harness_routing
        self._log_buffer: List[Tuple[float, str]] = []
        self._lock = threading.Lock()
        self._stream_thread: Optional[threading.Thread] = None
        self._running = False
        self._partial_line = ""

    def start(self) -> None:
        """Start background UART capture thread."""
        if self._running:
            return
        self._running = True
        self._stream_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="uart-demuxer"
        )
        self._stream_thread.start()
        log.info("UART demuxer started for %s", self._target)

    def stop(self) -> None:
        """Stop UART capture thread."""
        self._running = False
        if self._stream_thread:
            self._stream_thread.join(timeout=5)
            self._stream_thread = None
        log.info("UART demuxer stopped")

    def _capture_loop(self) -> None:
        """Background thread that reads from UartStream and buffers lines."""
        try:
            def request_gen():
                while self._running:
                    yield UartStreamRequest(target=self._target, data=b"")
                    time.sleep(0.1)

            for resp in self._mtib.UartStream(self._target, request_gen()):
                if not self._running:
                    break
                if resp.data and len(resp.data) > 0:
                    self._process_data(resp.data)
        except Exception as e:
            if self._running:
                log.error("UART capture error: %s", e)

    def _process_data(self, data: bytes) -> None:
        """Split incoming bytes into lines and route them."""
        text = self._partial_line + data.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self._partial_line = lines[-1]  # incomplete line carried forward

        now = time.monotonic()
        with self._lock:
            for line in lines[:-1]:
                line = line.rstrip("\r")
                if line:
                    self._log_buffer.append((now, line))

    def get_logs(self, since: Optional[float] = None) -> List[str]:
        """Return captured log lines, optionally filtered by timestamp.

        Args:
            since: Monotonic time threshold. Only return lines after this time.

        Returns:
            List of log line strings.
        """
        with self._lock:
            if since is not None:
                return [line for ts, line in self._log_buffer if ts >= since]
            return [line for _, line in self._log_buffer]

    def wait_for_log(
        self, pattern: str, timeout_s: float = 10, since: Optional[float] = None
    ) -> str:
        """Wait for a log line matching the regex pattern (debug build only).

        Args:
            pattern: Regex pattern to match.
            timeout_s: Maximum wait time.
            since: Only consider lines after this monotonic timestamp.

        Returns:
            The first matching log line.

        Raises:
            TimeoutError: If no matching line arrives within timeout_s.
        """
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout_s
        check_from = since or time.monotonic()

        while time.monotonic() < deadline:
            with self._lock:
                for ts, line in self._log_buffer:
                    if ts >= check_from and compiled.search(line):
                        return line
            time.sleep(0.2)

        raise TimeoutError(
            f"No UART log matching '{pattern}' within {timeout_s}s"
        )

    def clear(self) -> None:
        """Clear the log buffer."""
        with self._lock:
            self._log_buffer.clear()
            self._partial_line = ""

    def dump_to_file(self, path: str) -> None:
        """Write all captured logs to file."""
        import os
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._lock:
            with open(path, "w") as f:
                for ts, line in self._log_buffer:
                    f.write(f"[{ts:.3f}] {line}\n")
        log.info("UART logs dumped to %s (%d lines)", path, len(self._log_buffer))
