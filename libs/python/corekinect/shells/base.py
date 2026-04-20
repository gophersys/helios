"""Shell command interface over MTIB UART with persistent streams.

Opens ONE gRPC UartStream per target at session start. A background reader
thread continuously fills a buffer with incoming data. Commands clear the
buffer, send via the stream's TX path, and pattern-match as data arrives.

This eliminates response bleeding, data loss between commands, and the need
for drain hacks — like being directly wired to the serial port.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from typing import List, Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

log = logging.getLogger(__name__)

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
        """  init  ."""
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
        # Handle to the raw gRPC call so ``close()`` / ``ensure_alive``
        # can hard-cancel the bidi stream. Without this, setting
        # ``_stop`` only tells our request-generator to stop yielding;
        # the server-side handler keeps the stream registered until its
        # ``for request in request_iterator`` loop finally sees
        # StopIteration — which on a LAN to an edge MTIB can take
        # multiple seconds. Rapid boot-retry + reconnect cycles then
        # accumulate 4-5 stale streams per target, which collapses
        # broadcast throughput and causes fresh reconnects to die
        # within a few hundred ms. ``call.cancel()`` delivers
        # CANCELLED to the server immediately.
        self._grpc_call: Optional[object] = None

    @property
    def is_alive(self) -> bool:
        """Is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def rx_bytes(self) -> int:
        """Rx bytes."""
        return self._rx_bytes

    @property
    def last_error(self) -> Optional[str]:
        """Last error."""
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

    def close(self):
        """Close the stream and stop the background reader.

        Hard-cancels the underlying gRPC call so the server releases
        the client slot immediately (see ``_grpc_call`` docstring for
        why setting ``_stop`` alone leaks stale streams). Idempotent —
        safe to call from teardown paths that may have partially-
        initialised state.
        """
        self._stop.set()
        self._cancel_grpc_call()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _cancel_grpc_call(self) -> None:
        """Cancel the current gRPC UartStream if one is active."""
        call = self._grpc_call
        if call is None:
            return
        try:
            call.cancel()
        except Exception:
            pass
        self._grpc_call = None

    # Back-compat alias — ``stop()`` predates the convention shift to
    # ``close()`` (which matches stdlib io / sqlite3 / sshtunnel and the
    # ``CoreCloudDBInterface.close`` already in this codebase). Existing
    # callers keep working; new code should call ``close()``.
    stop = close

    def reset(self):
        """Close and reopen the gRPC stream.

        This clears the server-side client queue and in-flight gRPC data,
        which local clear() cannot reach. Call after lock/debug_off to
        flush the massive boot output backlog before running commands.
        """
        self.stop()
        time.sleep(0.3)
        self.start()

    # Total wall-clock budget for a reconnect attempt. A fresh gRPC
    # bidirectional-streaming call against an MTIB regularly takes
    # 1-2 s to establish (TCP handshake + TLS on slow edges + initial
    # metadata frame). The previous 300 ms budget guaranteed a
    # "Stream dead (None)" return every time the rx thread actually
    # went down between commands — which is what blew up the
    # test_11_rekey_ipc panel run.
    _RECONNECT_BUDGET_S = 3.0
    _RECONNECT_POLL_S = 0.05

    def ensure_alive(self) -> bool:
        """Check stream health, restart if dead. Returns True if alive.

        Wait up to ``_RECONNECT_BUDGET_S`` for the restarted worker
        thread to finish its initial gRPC establish. We poll at 50 ms
        to return as soon as the thread is up — typical local-cluster
        reconnects finish in 200-600 ms, office-LAN MTIB ~1-2 s.

        Also records a diagnostic ``_stream_error`` when the old
        thread died silently (no error set), so callers aren't
        surfaced ``Stream dead (None)`` and left without a cause.
        """
        if self.is_alive:
            return True
        if self._stop.is_set():
            return False  # Intentionally stopped

        # Old thread vanished without logging an error — make the
        # symptom visible so logs never show ``Stream dead (None)``.
        if self._stream_error is None:
            self._stream_error = "rx thread exited without raising"

        log.warning(
            "[%s] UART stream died (%s); restarting",
            self._label, self._stream_error,
        )
        # Hard-cancel any lingering gRPC call from the previous run —
        # the old thread exited but its handle may still hold the
        # stream open until the server-side for-loop unwinds. Without
        # this, rapid reconnects stack up 4-5 "ghost" clients per
        # target on the MTIB server and broadcast throughput collapses.
        self._cancel_grpc_call()
        self._stop.clear()
        # Drain stale TX queue so a stuck write from before the death
        # doesn't get replayed against the new stream.
        while not self._tx_queue.empty():
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                break
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"uart-rx-{self._label}"
        )
        self._thread.start()

        # Poll until the thread actually comes up (it might still be in
        # gRPC-connect) or the budget runs out.
        deadline = time.time() + self._RECONNECT_BUDGET_S
        while time.time() < deadline:
            if self.is_alive:
                return True
            time.sleep(self._RECONNECT_POLL_S)
        log.warning(
            "[%s] UART stream restart gave up after %.1fs (%s)",
            self._label, self._RECONNECT_BUDGET_S, self._stream_error,
        )
        return False

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
            """Request iter."""
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

        # Track the loop's exit reason so callers never see "Stream dead
        # (None)". The gRPC iterator can exit cleanly (server closed the
        # stream, keepalive missed, or the client cancelled) without
        # raising — the old code treated that identical to "we stopped
        # intentionally", which left ``_stream_error`` as None and any
        # downstream reconnect diagnosis completely blind.
        exit_reason: Optional[str] = None
        # Call the raw stub so we get back a cancellable call handle.
        # ``self._mtib.UartStream`` is a generator wrapper that hides
        # the handle; going directly to ``self._mtib.client`` lets
        # ``close()`` / ``ensure_alive`` hard-cancel the bidi stream
        # and stop accumulating stale clients on the MTIB server.
        call = self._mtib.client.UartStream(request_iter())
        self._grpc_call = call
        try:
            for resp in call:
                if self._stop.is_set():
                    exit_reason = "stopped by caller"
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
                    exit_reason = f"server error: {self._stream_error}"
                    break
            else:
                # Iterator exhausted without ``break`` — gRPC closed the
                # stream cleanly. No exception, but the stream is dead.
                if self._rx_bytes == 0:
                    exit_reason = "stream closed by server before any data arrived"
                else:
                    secs_since_data = (
                        time.time() - self._last_data_time
                        if self._last_data_time else float("inf")
                    )
                    exit_reason = (
                        f"stream closed by server ({self._rx_bytes} B received, "
                        f"{secs_since_data:.1f}s since last data)"
                    )
        except Exception as e:
            exit_reason = str(e) or type(e).__name__
            if not self._stop.is_set():
                log.warning(
                    "[%s] UART stream error: %s",
                    self._label, exit_reason,
                )
        finally:
            # Drop our reference so ensure_alive's cancel call is a no-op
            # once the thread has already torn the call down on its own.
            if self._grpc_call is call:
                self._grpc_call = None

        # Record the reason so ``ensure_alive`` and ``send`` surface a
        # real cause rather than ``(None)``. We deliberately don't
        # overwrite a reason already set above (server-error branch).
        if self._stream_error is None and exit_reason is not None:
            self._stream_error = exit_reason


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
        """  init  ."""
        self._mtib = mtib
        self._target = target
        self._stream = BufferedUartStream(mtib, target, label=label)

    def start(self) -> None:
        """Open persistent UART stream. Call before any commands."""
        self._stream.start()

    def close(self) -> None:
        """Close persistent UART stream."""
        self._stream.close()

    # Back-compat alias — see BufferedUartStream.stop above.
    stop = close

    def reset_stream(self) -> None:
        """Reset the persistent stream to clear server-side buffers.

        Call after lock+debug_off, before running real commands.
        Flushes stale boot output and BME280 warnings from the pipeline.
        """
        self._stream.reset()

    def __enter__(self):
        """  enter  ."""
        self.start()
        return self

    def __exit__(self, *_):
        """  exit  ."""
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
        # The stream may have died between our last command and this
        # one — server-side cancel, keepalive miss, or just a lull. The
        # reconnect attempt inside ensure_alive() has a 3s budget, and
        # if it doesn't come back we give up with the real reason
        # rather than the old ``Stream dead (None)`` mystery.
        if not self._stream.ensure_alive():
            return [], f"Stream dead ({self._stream.last_error})"

        # Reconnect might have wiped the shell's prompt state. Write a
        # bare newline before the command echo-probe so the device has
        # a chance to print its prompt into our freshly-reconnected
        # buffer; the double-clear below then strips it cleanly.
        if self._stream.rx_bytes == 0:
            self._stream.write(b"\r")
            time.sleep(0.1)

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
