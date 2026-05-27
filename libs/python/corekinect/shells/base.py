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
from typing import List, Optional, Tuple, Union

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

log = logging.getLogger(__name__)
# Dedicated UART-evidence logger. Every successful or failing shell
# call writes a one-line summary here PLUS the trailing buffer tail.
# StepReporter's log capture pipes Python ``logging`` into the
# ``TestStep.logOutput`` column at the platform — so any test step that
# fails inside a shell call lands the actual UART bytes in the DB
# alongside the failure, no per-test instrumentation needed.
uart_log = logging.getLogger("corekinect.shells.uart")


def hex_addr(address: Union[int, str]) -> str:
    """Format an address for a firmware shell command.

    Callers pass ``int`` addresses for readability; the firmware
    accepts decimal or 0x-prefixed hex. Normalise to ``0x{:08x}`` so the
    wire format is deterministic and matches what the firmware logs
    back on the response line.
    """
    if isinstance(address, int):
        return f"0x{address:08x}"
    return str(address)

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

        Sets ``_stop`` so the request-generator stops yielding; the
        server sees the request stream end and closes its side; the
        response iterator exits cleanly; ``_run`` returns. Idempotent.
        """
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

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

    def check_alive(self) -> Optional[str]:
        """Return an error string if the stream is dead, None if alive."""
        if self.is_alive:
            return None
        if self._stop.is_set():
            return "stream closed by caller"
        return self._stream_error or "rx thread exited without raising"

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

        # Track the loop's exit reason so callers see a real cause
        # instead of an empty ``last_error``. The gRPC iterator can
        # exit cleanly (server closed the stream) without raising;
        # we record that too.
        exit_reason: Optional[str] = None
        try:
            for resp in self._mtib.UartStream(self._target, request_iter()):
                if self._stop.is_set():
                    exit_reason = "stopped by caller"
                    break
                if resp.data:
                    with self._lock:
                        self._buffer.extend(resp.data)
                    self._rx_bytes += len(resp.data)
                    self._last_data_time = time.time()
                    self._data_event.set()
                if hasattr(resp, 'success') and not resp.success:
                    self._stream_error = getattr(resp, 'message', 'unknown')
                    exit_reason = f"server error: {self._stream_error}"
                    break
            else:
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

        The buffer is double-cleared then settled-and-cleared a third time
        so a slow trailing prompt from the *previous* command (still in
        flight on the wire when ``clear()`` ran) can't masquerade as the
        prompt for THIS command. Beyond the clears, success-pattern and
        prompt matching are scoped to the substring AFTER our own command
        echo — a stale prompt arriving in between clear() and the echo is
        ignored. Without that scoping, e.g. ``read_ext_flash`` issued right
        after ``write_ext_flash`` (whose 64-byte hex-dump is still draining)
        sees the write's trailing prompt the instant the read echo arrives
        and returns the write's tail rows as the read's data.

        Returns:
            (lines, error) — clean response lines. error is None on success.
        """
        # The stream either works or it doesn't. If the rx thread
        # exited for any reason (server closed, network hiccup,
        # anything), fail the command with the real cause — don't try
        # to reconnect and race with pytest/fixture teardown.
        err = self._stream.check_alive()
        if err is not None:
            return [], f"Stream dead ({err})"

        # Triple-clear with settles between: each pass eats whatever
        # arrived during the previous settle. Two clears (the old shape)
        # only drained data that was already buffered; a slow prompt
        # arriving 100–300 ms after the previous command finished its
        # SPI work would land between clear #2 and the new echo, fooling
        # the prompt-match below. Three passes with 50 ms settles cover
        # the observed cadence in failed runs (see run cmpob5vz on panel
        # 0AW6, test_13 slot-0).
        self._stream.clear()
        time.sleep(0.05)
        self._stream.clear()
        time.sleep(0.05)
        self._stream.clear()

        # Send ENTER + command as ONE write. Splitting them into separate
        # gRPC messages causes the Zephyr shell to lose the first character
        # of the command (the ENTER triggers prompt output whose ANSI codes
        # interfere with the command echo at the serial level).
        wire_command = f"\r{command}\r".encode()
        self._stream.write(wire_command)

        cmd_token = command.split()[0]
        echo_check = cmd_token[:-1] if len(cmd_token) > 3 else cmd_token
        deadline = time.time() + timeout_s
        echo_pos: Optional[int] = None  # index of THIS command's echo in text
        pattern_found_time = None
        # Echo-loss retry: if the gRPC pump fragments our write so the
        # firmware never sees a complete line (run cmpoen8zu on panel
        # 0AW2: slot-0 got ``Mfg shell: get_chip_id`` with the trailing
        # ``s\\r`` chopped, no execution, hence 30 s timeout waiting
        # for ``BLE MAC:``), the shell will sit silent forever. Re-write
        # the command every 4 s while we still have budget so the second
        # attempt's frame boundaries differ from the first's and at
        # least one lands intact.
        next_rewrite_at = time.time() + 4.0
        rewrites = 0

        while time.time() < deadline:
            text = self._stream.get_text()

            # Step 1: Wait for echo (proves device received command).
            # Record the echo position so subsequent pattern/prompt
            # matching only considers bytes that arrived after it. We
            # rfind() so the LAST occurrence wins — if the previous
            # command happened to contain ``cmd_token`` (unlikely but
            # possible for repeated commands like a re-send), we still
            # latch onto OUR echo, not the previous one.
            if echo_pos is None:
                idx = text.rfind(echo_check)
                if idx >= 0:
                    echo_pos = idx
                else:
                    # No echo yet. If 4 s have passed since the last
                    # write and we still have budget, re-issue. Capped
                    # at 4 rewrites to bound the firmware's command-
                    # queue depth.
                    if (
                        rewrites < 4
                        and time.time() >= next_rewrite_at
                        and (deadline - time.time()) > 1.0
                    ):
                        self._stream.write(wire_command)
                        rewrites += 1
                        next_rewrite_at = time.time() + 4.0
                    self._stream._data_event.clear()
                    self._stream._data_event.wait(timeout=0.05)
                    continue

            # Everything we care about lives after the echo. Slicing
            # here is what blocks a stale ``Mfg shell:`` prompt — left
            # behind by the previous command's late drain — from being
            # accepted as THIS command's terminator.
            post_echo = text[echo_pos:]

            # Step 2: Check success patterns (only after echo)
            if success_patterns and not pattern_found_time:
                for p in success_patterns:
                    if p in post_echo:
                        pattern_found_time = time.time()
                        break

            # Step 3: Exit conditions
            if pattern_found_time:
                # Pattern found — wait for prompt or 3s fallback
                if any(p in post_echo for p in _PROMPT_PATTERNS):
                    return self._clean(text, cmd_token), None
                if time.time() - pattern_found_time > 3.0:
                    return self._clean(text, cmd_token), None
            elif not success_patterns:
                # No patterns required — just wait for prompt
                if any(p in post_echo for p in _PROMPT_PATTERNS):
                    return self._clean(text, cmd_token), None

            self._stream._data_event.clear()
            self._stream._data_event.wait(timeout=0.05)

        # Timeout — final check (still post-echo if we ever saw it).
        text = self._stream.get_text()
        scope = text[echo_pos:] if echo_pos is not None else text
        if success_patterns:
            for p in success_patterns:
                if p in scope:
                    return self._clean(text, cmd_token), None
        alive = "alive" if self._stream.is_alive else f"DEAD({self._stream.last_error})"
        # Dump the full buffer tail to the UART log on timeout. This is
        # the evidence the operator needs when debugging — without it,
        # ``debug_off`` and ``send`` failures are blind. The platform's
        # StepReporter pipes everything we log into ``TestStep.logOutput``
        # so this text shows up next to the failed step in the UI.
        uart_log.warning(
            "[%s] send(%r) TIMEOUT after %.1fs (stream=%s rx=%dB echo_pos=%s success_patterns=%s)\n"
            "==== UART buffer tail (last 4096 B) ====\n%s\n==== /UART buffer ====",
            getattr(self._stream, "_label", "?"),
            command,
            timeout_s,
            alive,
            self._stream.rx_bytes,
            echo_pos,
            success_patterns,
            text[-4096:],
        )
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

        Spams ``lock_shell`` at a 200 ms cadence for the first
        ``min(timeout_s, 6.0)`` seconds, then continues polling the
        buffer at 100 ms for the remainder of the deadline. Returns
        as soon as ``mode ON`` / ``Mfg shell:`` / ``Comms Mfg:`` is
        seen.

        Why spam instead of "one shot + one retry": the firmware shell
        runs a 20 s expiration timer (``CONFIG_SHELL_TIMEOUT_SEC=20`` in
        sigma5_mfg_fw/prj.conf). The ``lock_shell`` handler in
        ``shell_handler.c`` only prints ``Locking shell mode ON`` while
        that timer is still alive — once it expires, ``deactivate_shell``
        runs and ``uart_rx_disable`` cuts the wire entirely. The test
        side gets exactly one 20 s budget shared with the firmware: any
        gRPC/HTTP/2 hiccup that loses a TX frame on the single shot is
        fatal. The previous "one shot + one retry at 8 s" path was even
        worse — the 8 s retry was guarded by ``if text == ""`` so any
        boot banner suppressed it. Run cmpoawlf500ob on panel 0AW6
        showed every slot stuck at exactly 21.2 s (the 20 s deadline +
        ~1 s overhead) while same-panel re-runs immediately afterward
        passed in 3–17 s — the signature of a sub-second race against
        the firmware deadline.

        The bandwidth cost is trivial: ``lock_shell`` is 12 bytes and we
        stop spamming the moment the confirmation arrives, which is
        usually well under 1 s. The 6 s cap on the spam window bounds
        the worst-case TX volume well under the HTTP/2 throughput
        sensitivity threshold called out in ``BufferedUartStream._run``.
        """
        if self._stream.check_alive() is not None:
            return False

        self._stream.clear()

        deadline = time.time() + timeout_s
        spam_until = time.time() + min(timeout_s, 6.0)
        # Cadence backoff. Aggressive first 400 ms (two near-back-to-back
        # writes — if either gRPC frame lands the lock arms), then space
        # out so we don't pile lock_shell commands into the firmware's
        # Zephyr shell line buffer. Run cmpodbsac on panel 0AW2 showed
        # what happens when we don't back off: 17 queued lock_shells
        # were still being drained when the very next command
        # (debug_enable 0) arrived, and the firmware shell missed it —
        # every slot's debug_off step then timed out at 15 s. Eight
        # writes spaced across 6 s wins the gRPC-frame race without
        # over-stuffing the firmware.
        send_intervals = [0.2, 0.4, 0.6, 0.8, 1.0, 1.0, 1.0, 1.0]
        next_send_idx = 0
        next_send = 0.0
        # Post-success settle: after we see the confirmation, give the
        # firmware ~250 ms to finish processing whatever lock_shell
        # writes are still in its UART RX line buffer (each one prints
        # a fresh ``Mfg shell:`` prompt). Returning early leaves those
        # tail bytes in flight, and the next send()'s clear() runs
        # while they're still arriving — corrupting the next command's
        # echo / prompt match.
        success_settle_until = None

        t_start = time.time()
        while time.time() < deadline:
            text = self._stream.get_text()
            if "mode ON" in text or "Mfg shell:" in text or "Comms Mfg:" in text:
                if success_settle_until is None:
                    success_settle_until = time.time() + 0.25
                if time.time() >= success_settle_until:
                    uart_log.info(
                        "[%s] lock() OK in %.2fs after %d write(s); tail=%r",
                        getattr(self._stream, "_label", "?"),
                        time.time() - t_start,
                        next_send_idx,
                        text[-256:],
                    )
                    return True
                self._stream._data_event.clear()
                self._stream._data_event.wait(timeout=0.05)
                continue

            now = time.time()
            if (
                now < spam_until
                and now >= next_send
                and next_send_idx < len(send_intervals)
            ):
                self._stream.write(b"\rlock_shell\r")
                next_send = now + send_intervals[next_send_idx]
                next_send_idx += 1

            self._stream._data_event.clear()
            self._stream._data_event.wait(timeout=0.1)

        # Timeout — dump the buffer so the operator can see what the
        # firmware was actually emitting (or not).
        final_text = self._stream.get_text()
        uart_log.warning(
            "[%s] lock() TIMEOUT after %.1fs (writes=%d rx=%dB stream=%s)\n"
            "==== UART buffer tail (last 4096 B) ====\n%s\n==== /UART buffer ====",
            getattr(self._stream, "_label", "?"),
            timeout_s,
            next_send_idx,
            self._stream.rx_bytes,
            "alive" if self._stream.is_alive else f"DEAD({self._stream.last_error})",
            final_text[-4096:],
        )
        return False

    def debug_off(self, timeout_s: float = 30.0) -> bool:
        """Disable debug UART output.

        The firmware's Zephyr LOG backend (gps_thread @1 Hz, watchdog,
        ck_ipc, …) floods the UART continuously until we successfully
        disable it — and that flood frequently chops the command echo
        in half. Captured UART from run cmpodyfob on panel 0AW2, slot 0:

            Mfg shell: debug_enable[00:00:10.148,498] <inf> app: Feeding watchdog
            ...lots more log lines...
            Mfg shell:

        The shell saw ``debug_enable`` then a log-line stream then the
        next prompt — no ``0`` argument, no execution. So we cannot rely
        on the standard ``send()`` echo+pattern handshake. Instead:

          1. Write ``\\rdebug_enable 0\\r`` at a 1-Hz cadence — once per
             gps_thread tick — for up to ``timeout_s`` seconds.
          2. After each write, poll the buffer for ``Debug is not
             enabled``. The firmware's ``shell_warn`` for that string
             is the FIRST line of the handler, BEFORE
             ``log_backend_disable``. If we see that line, the command
             executed cleanly and we're done.

        No echo check. The buffer can be (and usually is) full of log
        spam; we don't care. The presence of the success string is the
        only thing that matters.

        Once any attempt succeeds, the firmware disables the log
        backend and subsequent UART traffic is quiet — so later commands
        (``get_chip_ids``, ``read_ext_flash``, etc.) get clean echo +
        prompt sequences.
        """
        if self._stream.check_alive() is not None:
            return False

        t_start = time.time()
        deadline = t_start + timeout_s
        next_write = 0.0
        write_count = 0
        while time.time() < deadline:
            # Re-issue the command once per second — phased between
            # gps_thread @1 Hz ticks, so half our writes land in a
            # quiet window and avoid the chop.
            now = time.time()
            if now >= next_write:
                self._stream.write(b"\rdebug_enable 0\r")
                next_write = now + 1.0
                write_count += 1

            text = self._stream.get_text()
            if "Debug is not enabled" in text:
                # Give the firmware ~250 ms to actually flush
                # log_backend_disable() before we return — so the next
                # command's send() doesn't race the tail end of the
                # log stream.
                time.sleep(0.25)
                uart_log.info(
                    "[%s] debug_off() OK in %.2fs after %d write(s); tail=%r",
                    getattr(self._stream, "_label", "?"),
                    time.time() - t_start,
                    write_count,
                    text[-256:],
                )
                # Clear the buffer of accumulated log spam so the next
                # send()'s echo detection isn't searching megabytes.
                self._stream.clear()
                return True

            self._stream._data_event.clear()
            self._stream._data_event.wait(timeout=0.2)

        final_text = self._stream.get_text()
        uart_log.warning(
            "[%s] debug_off() TIMEOUT after %.1fs (writes=%d rx=%dB)\n"
            "==== UART buffer tail (last 4096 B) ====\n%s\n==== /UART buffer ====",
            getattr(self._stream, "_label", "?"),
            timeout_s,
            write_count,
            self._stream.rx_bytes,
            final_text[-4096:],
        )
        return False
