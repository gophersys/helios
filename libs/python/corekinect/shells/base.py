"""Shell command interface over MTIB UART with persistent streams.

Opens ONE gRPC UartStream per target at session start. A background reader
thread continuously fills a buffer with incoming data. Commands clear the
buffer, send via the stream's TX path, and pattern-match as data arrives.

This eliminates response bleeding, data loss between commands, and the need
for drain hacks — like being directly wired to the serial port.
"""

from __future__ import annotations

import queue
import re
import threading
import time
from typing import List, Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

# Standard ANSI escape: ESC [ <params> <letter>
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Orphan CSI sequences where ESC byte was lost in byte-by-byte delivery.
# Only SGR codes (m terminator) to avoid stripping legitimate brackets.
_ORPHAN_CSI_RE = re.compile(r"\[\d+(?:;\d+)*m")

# Zephyr log line: [HH:MM:SS.mmm,mmm] <level> module: message
_ZEPHYR_LOG_RE = re.compile(r"^\[\d+:\d+:\d+\.\d+")

# Both prompts seen in Alpha dual-processor output
_PROMPT_PATTERNS = ["Mfg shell:", "Comms Mfg:"]


def _strip(text: str) -> str:
    """Strip ANSI escapes and orphan CSI sequences from UART text."""
    text = _ANSI_RE.sub("", text)
    text = _ORPHAN_CSI_RE.sub("", text)
    return text


class BufferedUartStream:
    """Persistent gRPC UART stream with background reader.

    Keeps a single gRPC UartStream open for the session lifetime.
    Background thread reads all incoming data into a buffer.
    TX data is queued and sent through the same stream.
    Auto-reconnects if the stream dies unexpectedly.
    """

    def __init__(self, mtib, target: HostType, label: str = ""):
        self._mtib = mtib
        self._target = target
        self._label = label or str(target)
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._data_event = threading.Event()
        self._tx_queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._rx_bytes = 0
        self._last_data_time: Optional[float] = None
        self._stream_error: Optional[str] = None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def rx_bytes(self) -> int:
        return self._rx_bytes

    @property
    def last_error(self) -> Optional[str]:
        return self._stream_error

    def start(self):
        """Open the persistent gRPC stream and start background reader."""
        if self.is_alive:
            return
        # Fresh stop event — prevents old thread (if still dying) from
        # sharing our signal and continuing to write into our buffer.
        self._stop = threading.Event()
        self._buffer.clear()
        self._rx_bytes = 0
        self._last_data_time = None
        self._stream_error = None
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"uart-rx-{self._label}"
        )
        self._thread.start()
        # Give the stream a moment to establish
        time.sleep(0.1)

    def stop(self):
        """Close the stream and stop background reader."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def reset(self):
        """Close and reopen the gRPC stream.

        This clears the server-side client queue and in-flight gRPC data,
        which local clear() cannot reach. Call after lock/debug_off to
        flush the massive boot output backlog before running commands.
        """
        self.stop()
        time.sleep(0.3)
        self.start()

    def ensure_alive(self) -> bool:
        """Check stream health, restart if dead. Returns True if alive."""
        if self.is_alive:
            return True
        if self._stop.is_set():
            return False  # Intentionally stopped
        # Stream died unexpectedly — restart
        print(f"  [{self._label}] Stream died ({self._stream_error}), restarting...")
        self._stop.clear()
        # Drain stale TX queue
        while not self._tx_queue.empty():
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                break
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"uart-rx-{self._label}"
        )
        self._thread.start()
        time.sleep(0.3)  # Give reconnect a moment
        return self.is_alive

    def write(self, data: bytes):
        """Queue bytes for TX to device."""
        self._tx_queue.put(data)

    def clear(self):
        """Clear the RX buffer. Instant, no gRPC overhead."""
        with self._lock:
            self._buffer.clear()
        self._data_event.clear()

    def get_text(self) -> str:
        """Get buffer contents as ANSI-stripped text."""
        with self._lock:
            raw = bytes(self._buffer).decode("utf-8", errors="ignore")
        return _strip(raw)

    def wait_for(self, pattern: str, timeout_s: float = 30.0) -> bool:
        """Block until pattern appears in ANSI-stripped buffer."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if pattern in self.get_text():
                return True
            self._data_event.clear()
            remaining = deadline - time.time()
            if remaining > 0:
                self._data_event.wait(timeout=min(remaining, 0.05))
        return pattern in self.get_text()

    def _run(self):
        """Background: maintain gRPC stream, read RX into buffer."""

        def request_iter():
            # Initial request establishes the stream
            yield UartStreamRequest(target=self._target, data=b"")
            while not self._stop.is_set():
                try:
                    data = self._tx_queue.get(timeout=0.05)
                    yield UartStreamRequest(target=self._target, data=data)
                except queue.Empty:
                    # Pump empty request to trigger gRPC HTTP/2 WINDOW_UPDATE.
                    # Without this, the server's send window never recovers
                    # and RX throughput drops from ~1500 B/s to ~3 B/s.
                    yield UartStreamRequest(target=self._target, data=b"")

        try:
            for resp in self._mtib.UartStream(self._target, request_iter()):
                if self._stop.is_set():
                    break
                if resp.data:
                    with self._lock:
                        self._buffer.extend(resp.data)
                    self._rx_bytes += len(resp.data)
                    self._last_data_time = time.time()
                    self._data_event.set()
                # Check for gRPC-level error responses
                if hasattr(resp, 'success') and not resp.success:
                    self._stream_error = getattr(resp, 'message', 'unknown')
                    break
        except Exception as e:
            self._stream_error = str(e) or type(e).__name__
            if not self._stop.is_set():
                print(f"  [{self._label}] Stream error: {self._stream_error}")


class ShellCommander:
    """UART shell command interface using persistent buffered streams.

    Opens a persistent gRPC UartStream at start(). All commands
    (lock, debug_off, send) operate on the live buffer — no per-command
    stream open/close, no drains, no response bleeding.

    Usage:
        cmd = ShellCommander(mtib, HostType.HOST_TYPE_NRF52840)
        cmd.start()           # Opens persistent stream
        cmd.lock()            # Spam-based shell lock
        cmd.debug_off()       # Disable debug output
        lines, err = cmd.send("get_chip_ids", ["BLE MAC:"])
        cmd.stop()            # Closes stream
    """

    def __init__(self, mtib, target: HostType, label: str = ""):
        self._mtib = mtib
        self._target = target
        self._stream = BufferedUartStream(mtib, target, label=label)

    def start(self) -> None:
        """Open persistent UART stream. Call before any commands."""
        self._stream.start()

    def stop(self) -> None:
        """Close persistent UART stream."""
        self._stream.stop()

    def reset_stream(self) -> None:
        """Reset the persistent stream to clear server-side buffers.

        Call after lock+debug_off, before running real commands.
        Flushes stale boot output and BME280 warnings from the pipeline.
        """
        self._stream.reset()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ── Commands ──────────────────────────────────────

    def send(
        self,
        command: str,
        success_patterns: Optional[List[str]] = None,
        timeout_s: float = 30.0,
    ) -> Tuple[List[str], Optional[str]]:
        """Send command and wait for response from live buffer.

        Clears buffer, sends command, watches buffer fill at ~50Hz.
        Pattern matching runs on ANSI-stripped accumulated text.

        Returns:
            (lines, error) — clean response lines. error is None on success.
        """
        if not self._stream.ensure_alive():
            return [], f"Stream dead ({self._stream.last_error})"

        # Double-clear: flush any in-flight data, brief settle, flush again
        self._stream.clear()
        time.sleep(0.05)
        self._stream.clear()

        # Send ENTER + command as ONE write. Splitting them into separate
        # gRPC messages causes the Zephyr shell to lose the first character
        # of the command (the ENTER triggers prompt output whose ANSI codes
        # interfere with the command echo at the serial level).
        self._stream.write(f"\r{command}\r".encode())

        cmd_token = command.split()[0]
        echo_check = cmd_token[:-1] if len(cmd_token) > 3 else cmd_token
        deadline = time.time() + timeout_s
        echo_seen = False
        pattern_found_time = None

        while time.time() < deadline:
            text = self._stream.get_text()

            # Step 1: Wait for echo (proves device received command)
            if not echo_seen:
                if echo_check in text:
                    echo_seen = True
                else:
                    self._stream._data_event.clear()
                    self._stream._data_event.wait(timeout=0.05)
                    continue

            # Step 2: Check success patterns (only after echo)
            if success_patterns and not pattern_found_time:
                for p in success_patterns:
                    if p in text:
                        pattern_found_time = time.time()
                        break

            # Step 3: Exit conditions
            if pattern_found_time:
                # Pattern found — wait for prompt or 3s fallback
                if any(p in text for p in _PROMPT_PATTERNS):
                    return self._clean(text, cmd_token), None
                if time.time() - pattern_found_time > 3.0:
                    return self._clean(text, cmd_token), None
            elif not success_patterns:
                # No patterns required — just wait for prompt
                if any(p in text for p in _PROMPT_PATTERNS):
                    return self._clean(text, cmd_token), None

            self._stream._data_event.clear()
            self._stream._data_event.wait(timeout=0.05)

        # Timeout — final check
        text = self._stream.get_text()
        if success_patterns:
            for p in success_patterns:
                if p in text:
                    return self._clean(text, cmd_token), None
        alive = "alive" if self._stream.is_alive else f"DEAD({self._stream.last_error})"
        return [], f"Timeout ({timeout_s}s) stream={alive} rx={self._stream.rx_bytes}B. Got: {text[:300]}"

    @staticmethod
    def _clean(full: str, cmd_token: str) -> List[str]:
        """Extract response lines between echo and prompt.

        Handles dual-processor UART quirks:
        - Normalizes line endings (\\r\\n, bare \\r → \\n)
        - Falls back to noise-filtered output if echo is buried
        """
        # full is already ANSI-stripped (from get_text())
        normalized = full.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")

        # Primary: capture between echo and prompt
        result = []
        capturing = False
        for ln in lines:
            clean = ln.strip()
            if not clean:
                continue
            if not capturing and cmd_token in clean:
                capturing = True
                continue
            if capturing:
                if any(p in clean for p in _PROMPT_PATTERNS):
                    break
                result.append(clean)

        if result:
            return result

        # Fallback: echo buried in noise — return all non-noise lines
        for ln in lines:
            clean = ln.strip()
            if not clean:
                continue
            if any(p in clean for p in _PROMPT_PATTERNS):
                continue
            if cmd_token in clean:
                continue
            if _ZEPHYR_LOG_RE.match(clean):
                continue
            result.append(clean)

        return result

    def lock(self, timeout_s: float = 120.0) -> bool:
        """Lock manufacturing shell.

        Sends ONE lock_shell command, then watches the buffer for up to
        timeout_s. Minimizes TX messages to avoid degrading HTTP/2 stream
        throughput on the embedded gRPC server (even a handful of TX
        messages can permanently drop throughput to ~3 B/s).

        The shell activation window is ~6s after boot. The POST test
        sends lock_shell before boot output arrives, so one command
        queued early is sufficient. A second attempt fires only if the
        first produced no response after 8s.
        """
        if not self._stream.ensure_alive():
            return False

        self._stream.clear()
        self._stream.write(b"\rlock_shell\r")

        deadline = time.time() + timeout_s
        retry_at = time.time() + 8.0  # One retry if first attempt missed
        retried = False

        while time.time() < deadline:
            text = self._stream.get_text()
            if "mode ON" in text or "Mfg shell:" in text or "Comms Mfg:" in text:
                return True

            # Single retry after 8s if nothing detected
            if not retried and time.time() >= retry_at:
                self._stream.write(b"\rlock_shell\r")
                retried = True

            self._stream._data_event.clear()
            self._stream._data_event.wait(timeout=0.1)

        return False

    def debug_off(self, timeout_s: float = 30.0) -> bool:
        """Disable debug UART output."""
        lines, err = self.send(
            "debug_enable 0", ["Debug is not enabled"], timeout_s
        )
        return err is None
