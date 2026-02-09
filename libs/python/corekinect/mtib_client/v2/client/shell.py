"""Shell command helper for V2 UART communication.

Provides a reusable interface for sending Zephyr shell commands over UART
to target devices via the V2 gRPC UART service.

The manufacturing firmware shell has a ~2 second activation window after boot.
To use the shell, you must:
1. Open UART BEFORE powering on the device
2. Spam lock_shell immediately to catch the shell window
3. Disable debug output to reduce UART noise
4. Then send commands on the locked shell

Uses a **persistent bidirectional stream** for command execution.  After
locking, the stream stays open and all commands flow through it.  This
avoids per-command stream creation and the server-side stale-data drain
race condition that caused data from one command to leak into the next.

Command completion is detected by accumulating all UART data, stripping
Zephyr kernel log noise (which interleaves at the character level with
shell I/O on shared UART TX), then finding the command echo followed by
the shell prompt in the cleaned text.
"""

import re
import threading
import time
from queue import Empty as QueueEmpty, Queue
from typing import Dict, List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import UartStreamRequest


# Default shell prompt for manufacturing firmware
MFG_SHELL_PROMPT = "Mfg shell:"

# UART configuration
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 30.0
LOCK_SHELL_TIMEOUT = 15.0
STREAM_POLL_INTERVAL = 0.1

# ANSI escape code pattern for stripping color codes from shell output
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# Zephyr kernel log line pattern:
#   [HH:MM:SS.mmm,uuu] <level> module: message\r\n
# with optional tab-indented continuation lines.
# These interleave with shell I/O at the character level when the shell
# and log backend share the same UART TX.
ZEPHYR_LOG_LINE = re.compile(
    r"\[\d{2}:\d{2}:\d{2}\.\d{3}[,\.]\d{3}\][^\r\n]*\r?\n(?:\t[^\r\n]*\r?\n)*"
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


def strip_log_noise(text: str) -> str:
    """Remove Zephyr kernel log lines from text.

    Zephyr log entries have the format:
        [HH:MM:SS.mmm,uuu] <level> module: message
    and may have tab-indented continuation lines.  These interleave with
    shell I/O at the character level when the shell and log backend share
    the same UART TX, breaking echo/prompt detection.  Stripping them
    restores clean shell text for completion detection.
    """
    return ZEPHYR_LOG_LINE.sub("", text)


class ShellCommandHelper:
    """Helper to send shell commands to a target via UART.

    Uses an MtibV2Client's uart_open/uart_stream/uart_close methods to
    send commands and collect responses from the device's shell.

    After locking, a persistent bidirectional gRPC stream stays open for
    all subsequent commands.  This avoids per-command stream creation and
    the associated stale-drain race condition.

    Args:
        client: An MtibV2Client instance (must already be connected).
        target_id: Target device string (e.g. "nrf52840", "nrf9151").
        port_name: UART port name (e.g. "uart0", "uart1").
        prompt: Shell prompt string to detect command completion.
    """

    def __init__(
        self,
        client,
        target_id: str,
        port_name: str = "uart0",
        prompt: str = MFG_SHELL_PROMPT,
    ):
        self.client = client
        self.target_id = target_id
        self.port_name = port_name
        self.prompt = prompt
        self._stream_id: Optional[str] = None

        # Persistent stream state
        self._tx_queue: Queue = Queue()
        self._rx_lock = threading.Lock()
        self._rx_chunks: List[str] = []
        self._rx_event = threading.Event()  # Signalled on each RX chunk
        self._rx_cmd_offset: int = 0  # Offset into accumulated text for current command
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_stop = threading.Event()
        self._stream_error: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self._stream_id is not None

    def open(self) -> Optional[str]:
        """Open the UART connection.

        Returns:
            Error message, or None on success.
        """
        if self._stream_id:
            return None  # Already open
        err, conn = self.client.uart_open(
            target_id=self.target_id,
            port_name=self.port_name,
            baud=DEFAULT_BAUD,
        )
        if err:
            return err
        self._stream_id = conn.stream_id
        return None

    def close(self) -> Optional[str]:
        """Close the UART connection and persistent stream.

        Returns:
            Error message, or None on success.
        """
        self._stop_persistent_stream()
        if self._stream_id:
            err = self.client.uart_close(self._stream_id)
            self._stream_id = None
            return err
        return None

    # -- Persistent stream management ----------------------------------------

    def _start_persistent_stream(self) -> Optional[str]:
        """Start the persistent bidirectional stream if not already running."""
        if self._stream_thread and self._stream_thread.is_alive():
            return None  # Already running

        if not self._stream_id:
            return "UART not open"

        self._stream_stop.clear()
        self._stream_error = None

        # Drain any leftover data in the TX queue
        while not self._tx_queue.empty():
            try:
                self._tx_queue.get_nowait()
            except QueueEmpty:
                break

        self._stream_thread = threading.Thread(
            target=self._persistent_stream_worker,
            daemon=True,
            name=f"shell-stream-{self.target_id}",
        )
        self._stream_thread.start()

        # Wait briefly for the stream to initialize
        time.sleep(0.1)
        if self._stream_error:
            return self._stream_error
        return None

    def _stop_persistent_stream(self) -> None:
        """Stop the persistent stream."""
        self._stream_stop.set()
        # Push a sentinel to unblock the TX queue
        self._tx_queue.put(None)
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5.0)
        self._stream_thread = None

    def _restart_persistent_stream(self) -> Optional[str]:
        """Stop and restart the persistent stream for a fresh gRPC channel.

        Useful after long-running operations (like TX backlog drain) where
        the accumulated gRPC HTTP/2 state can cause latency.  The UART
        connection (stream_id) stays the same — only the gRPC bidirectional
        stream is recycled.
        """
        self._stop_persistent_stream()
        return self._start_persistent_stream()

    def _persistent_stream_worker(self) -> None:
        """Background thread running the persistent bidirectional stream."""
        stream_id = self._stream_id

        def tx_gen():
            """Yield TX requests from the queue until stopped.

            Sends keepalive empty frames every 0.2s when idle.  These
            don't write to the UART (the server's TX worker checks
            ``if request.data``) but they trigger HTTP/2 activity that
            flushes any buffered server-side responses — without this,
            gRPC Python holds server yields in the HTTP/2 framing buffer
            until the next client-to-server frame, causing multi-second
            latency on UART data delivery.
            """
            while not self._stream_stop.is_set():
                try:
                    item = self._tx_queue.get(timeout=0.2)
                except QueueEmpty:
                    # Keepalive — flush gRPC HTTP/2 write buffer
                    yield UartStreamRequest(stream_id=stream_id, data=b"")
                    continue

                if item is None:
                    break  # Sentinel — stop
                yield UartStreamRequest(stream_id=stream_id, data=item)

        try:
            for resp in self.client.uart_stream(tx_gen(), timeout=None):
                if self._stream_stop.is_set():
                    break

                if not resp.success and resp.message:
                    self._stream_error = resp.message
                    break

                if resp.data:
                    decoded = resp.data.decode("utf-8", errors="replace")
                    with self._rx_lock:
                        self._rx_chunks.append(decoded)
                    self._rx_event.set()

        except Exception as e:
            if not self._stream_stop.is_set():
                self._stream_error = str(e)

    def _send_data(self, data: bytes) -> None:
        """Queue data for transmission on the persistent stream."""
        self._tx_queue.put(data)

    def _clear_rx(self) -> None:
        """Clear the RX accumulator."""
        with self._rx_lock:
            self._rx_chunks.clear()
        self._rx_event.clear()

    def _get_rx_text(self) -> str:
        """Get accumulated RX text."""
        with self._rx_lock:
            return "".join(self._rx_chunks)

    # -- Shell operations ----------------------------------------------------

    def wait_for_quiet(
        self,
        timeout: float = 300.0,
        quiet_duration: float = 3.0,
    ) -> Optional[str]:
        """Wait until the device's UART TX backlog has fully drained.

        After boot, the device may have a large TX ring buffer full of log
        messages.  These drain at 115200 baud (~11.5 KB/s) but can take
        minutes if the backlog is large (100+ KB).  This method monitors
        the incoming data rate and returns when no new data arrives for
        *quiet_duration* seconds, indicating the backlog has drained.

        Must be called after open() and starts the persistent stream.

        Args:
            timeout: Maximum time to wait (seconds).
            quiet_duration: How long silence must last to consider
                the backlog drained (seconds).

        Returns:
            Error message, or None on success.
        """
        if not self._stream_id:
            err = self.open()
            if err:
                return f"Failed to open UART: {err}"

        err = self._start_persistent_stream()
        if err:
            return f"Failed to start stream: {err}"

        last_len = len(self._get_rx_text())
        quiet_start = time.time()
        deadline = time.time() + timeout

        while time.time() < deadline:
            self._rx_event.wait(timeout=1.0)
            self._rx_event.clear()

            current_len = len(self._get_rx_text())
            if current_len == last_len:
                if time.time() - quiet_start >= quiet_duration:
                    # TX backlog is drained — advance offset past all data
                    self._rx_cmd_offset = len(self._get_rx_text())
                    return None
            else:
                last_len = current_len
                quiet_start = time.time()

        # Timeout — still advance offset to skip whatever arrived
        self._rx_cmd_offset = len(self._get_rx_text())
        return f"TX backlog drain timeout ({timeout}s, {last_len} bytes received)"

    def lock_shell_race(self, timeout: float = LOCK_SHELL_TIMEOUT) -> Tuple[Optional[bool], Optional[str]]:
        """Race to lock the shell during boot.

        Must be called with UART already open. Spams lock_shell every 0.2s
        until the shell responds with "Shell locked" or timeout.

        Uses a dedicated short-lived stream (not the persistent stream)
        because this runs before the shell is ready for normal commands.

        Args:
            timeout: Max time to wait for lock.

        Returns:
            (success, error) tuple.
        """
        if not self._stream_id:
            return None, "UART not open"

        responses: List[str] = []
        start = time.time()

        def req_gen():
            while time.time() - start < timeout:
                yield UartStreamRequest(stream_id=self._stream_id, data=b"\r")
                time.sleep(0.05)
                yield UartStreamRequest(stream_id=self._stream_id, data=b"lock_shell\r")
                time.sleep(0.15)

        try:
            for resp in self.client.uart_stream(req_gen(), timeout=timeout + 5):
                if resp.data:
                    responses.append(resp.data.decode("utf-8", errors="replace"))
                    text = "".join(responses)
                    if "Shell locked" in text or "Locking shell" in text:
                        return True, None
        except Exception as e:
            return None, f"lock_shell_race error: {e}"

        text = "".join(responses)
        if "Shell locked" in text or "Locking shell" in text:
            return True, None
        total_bytes = sum(len(r) for r in responses)
        snippet = text[-200:] if text else "(no data)"
        if "Uninitializing the shell" in text:
            return None, (
                f"Shell deactivated before lock ({total_bytes} bytes received). "
                f"Last 200 chars: {snippet!r}"
            )
        return None, (
            f"Timeout ({timeout}s, {total_bytes} bytes received). "
            f"No lock confirmation. Last 200 chars: {snippet!r}"
        )

    def send_command(
        self,
        command: str,
        timeout: float = DEFAULT_TIMEOUT,
        completion_marker: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send a shell command and wait for prompt-based completion.

        Creates a fresh bidirectional gRPC stream per command with ``\\r``
        pings every 0.2 s.  The ``\\r`` causes the device to echo a
        prompt, which triggers the server to yield a response, which
        flushes the gRPC HTTP/2 write buffer.  Without this, the server
        holds small responses in the write buffer indefinitely — empty
        ``b""`` pings from the client do NOT flush the server-side buffer.

        Zephyr shell buffers input during command execution and processes
        it afterward, so the ``\\r`` pings only generate extra prompt
        lines after the command output — they do not interfere with the
        command's response.

        Args:
            command: Shell command string (e.g. "get_chip_ids").
            timeout: Maximum time to wait for response in seconds.
            completion_marker: Optional string to look for instead of the
                shell prompt to detect completion. If None, uses self.prompt.

        Returns:
            (error, response_text) tuple. error is None on success.
        """
        if not self._stream_id:
            err = self.open()
            if err:
                return f"Failed to open UART: {err}", None

        # Stop the persistent stream if running — we use fresh streams
        # per command with \r pings to flush the server's gRPC buffer.
        if self._stream_thread and self._stream_thread.is_alive():
            self._stop_persistent_stream()
            # Wait for the server-side stream to fully terminate.
            # The server's RX loop has a 0.5s queue.get timeout, so we
            # need to wait at least that long to avoid two server-side
            # streams reading from the same rx_queue simultaneously.
            time.sleep(1.0)

        marker = completion_marker or self.prompt
        cmd_keyword = command.split()[0] if command.strip() else command
        stream_id = self._stream_id

        # Accumulated response text
        rx_chunks: List[str] = []
        completed = threading.Event()
        result_holder: Dict[str, Optional[str]] = {"error": None, "text": None}

        def req_gen():
            """Generate: flush \\r, send command, keep-alive with \\r pings."""
            # Phase 1: flush — send \r to trigger any stale prompt
            yield UartStreamRequest(stream_id=stream_id, data=b"\r")
            time.sleep(0.3)

            # Phase 2: send the actual command
            yield UartStreamRequest(stream_id=stream_id, data=f"{command}\r".encode())

            # Phase 3: keep the stream alive with \r pings.
            # The device echoes a prompt for each \r, which triggers the
            # server to yield a response and flush the gRPC write buffer.
            deadline = time.time() + timeout
            while time.time() < deadline and not completed.is_set():
                yield UartStreamRequest(stream_id=stream_id, data=b"\r")
                time.sleep(0.2)

        try:
            for resp in self.client.uart_stream(req_gen(), timeout=timeout + 10):
                if completed.is_set():
                    break

                if not resp.success and resp.message:
                    result_holder["error"] = resp.message
                    completed.set()
                    break

                if resp.data:
                    chunk = resp.data.decode("utf-8", errors="replace")
                    rx_chunks.append(chunk)

                    # Check for completion in accumulated text
                    full_text = "".join(rx_chunks)
                    if _check_completion(full_text, cmd_keyword, marker):
                        cleaned = strip_log_noise(strip_ansi(full_text))
                        result_holder["text"] = cleaned
                        completed.set()
                        break

        except Exception as e:
            if not completed.is_set():
                result_holder["error"] = str(e)

        if result_holder["error"]:
            return result_holder["error"], None

        if result_holder["text"]:
            return None, result_holder["text"]

        # Timeout — build diagnostic
        full_text = strip_log_noise(strip_ansi("".join(rx_chunks)))
        total_bytes = len(full_text)
        snippet = repr(full_text[:300]) if full_text else "(no data)"
        if total_bytes == 0:
            diag = f"Timeout ({timeout}s): no UART data received"
        elif cmd_keyword not in full_text:
            diag = (
                f"Timeout ({timeout}s): received {total_bytes} bytes but "
                f"command echo '{cmd_keyword}' not found. "
                f"Data: {snippet}"
            )
        else:
            diag = (
                f"Timeout ({timeout}s): command echo found but shell prompt "
                f"'{marker}' not detected. Data: {snippet}"
            )
        return diag, full_text if full_text else None

    def send_command_oneshot(
        self,
        command: str,
        timeout: float = DEFAULT_TIMEOUT,
        completion_marker: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Open UART, send a command, get response, then close.

        Args:
            command: Shell command string.
            timeout: Maximum time to wait for response.
            completion_marker: Optional completion marker string.

        Returns:
            (error, response_text) tuple.
        """
        try:
            err, response = self.send_command(command, timeout, completion_marker)
            return err, response
        finally:
            self.close()


# ---------------------------------------------------------------------------
# Completion detection (V1-style)
# ---------------------------------------------------------------------------
def _check_completion(full_response: str, cmd_keyword: str, prompt: str) -> bool:
    """Check if the command echo and subsequent prompt are present.

    First strips Zephyr log noise (which can interleave at the character
    level with shell I/O), then scans line-by-line: finds a line containing
    the command keyword, then finds a line containing the prompt AFTER that.
    """
    cleaned = strip_log_noise(full_response)
    lines = cleaned.split("\n")
    command_found = False
    for line in lines:
        clean = strip_ansi(line).strip()
        if not command_found:
            if cmd_keyword in clean:
                command_found = True
        else:
            if prompt in clean:
                return True
    return False


# ---------------------------------------------------------------------------
# Boot & lock helper
# ---------------------------------------------------------------------------
def _attempt_lock(
    client,
    app_port: str,
    comms_port: str,
    boot_wait: float,
    do_jlink_reset: bool,
) -> Tuple[Optional[ShellCommandHelper], Optional[ShellCommandHelper], Optional[str]]:
    """Single attempt to power-cycle and lock both shells.

    Returns (app_shell, comms_shell, error).
    """
    if do_jlink_reset:
        # Ensure power is on so J-Link can communicate with targets.
        # Alpha B0: BQ25180 UVLO requires >= 4.5V on battery sim rail.
        client.power_enable(channel=0, voltage_v=4.5)
        client.power_enable(channel=1)
        time.sleep(1)

        # J-Link reset both processors for a clean boot
        err, probes = client.list_probes()
        if not err and probes:
            probe_serials = [p.serial for p in probes if p.serial]
            for probe_id in probe_serials:
                for target_id in ["nrf52840", "nrf9151"]:
                    err, session = client.debug_connect(
                        target_id=target_id, probe_id=probe_id
                    )
                    if not err and session:
                        client.debug_reset(session.session_id)
                        client.debug_disconnect(session.session_id)

    # Power off to fully de-energize
    client.power_disable(channel=0)
    client.power_disable(channel=1)
    time.sleep(2)

    # Open both UARTs BEFORE power-on
    app_shell = ShellCommandHelper(client, "nrf52840", app_port)
    comms_shell = ShellCommandHelper(client, "nrf9151", comms_port)

    err = app_shell.open()
    if err:
        return None, None, f"Failed to open app UART ({app_port}): {err}"
    err = comms_shell.open()
    if err:
        app_shell.close()
        return None, None, f"Failed to open comms UART ({comms_port}): {err}"

    if boot_wait > 0:
        time.sleep(boot_wait)

    # Power on — device will boot fresh after reset.
    # Alpha B0: BQ25180 UVLO requires >= 4.5V on battery sim rail.
    client.power_enable(channel=0, voltage_v=4.5)
    client.power_enable(channel=1)

    # Race to lock both shells simultaneously
    results: Dict[str, Tuple[Optional[bool], Optional[str]]] = {}

    def lock_thread(name, shell):
        results[name] = shell.lock_shell_race()

    t_app = threading.Thread(target=lock_thread, args=("app", app_shell))
    t_comms = threading.Thread(target=lock_thread, args=("comms", comms_shell))
    t_app.start()
    t_comms.start()
    t_app.join(timeout=20)
    t_comms.join(timeout=20)

    app_ok, app_err = results.get("app", (None, "Thread timeout"))
    comms_ok, comms_err = results.get("comms", (None, "Thread timeout"))

    errors = []
    if not app_ok:
        errors.append(f"app: {app_err}")
    if not comms_ok:
        errors.append(f"comms: {comms_err}")

    if errors:
        app_shell.close()
        comms_shell.close()
        return None, None, f"Shell lock failed: {'; '.join(errors)}"

    return app_shell, comms_shell, None


def boot_and_lock_shells(
    client,
    app_port: str = "uart1",
    comms_port: str = "uart0",
    boot_wait: float = 0.0,
    max_retries: int = 3,
) -> Tuple[Optional[ShellCommandHelper], Optional[ShellCommandHelper], Optional[str]]:
    """Power cycle device and lock both manufacturing shells.

    This handles the critical race: the mfg shell only stays active ~2s
    after boot, so we must have UARTs open and spamming lock_shell before
    the device powers on.

    Uses J-Link debug reset on the first attempt to ensure a clean boot.
    If the lock race fails, retries with a simple power cycle (no J-Link
    reset) up to *max_retries* times.

    After locking, sends ``debug_enable 0`` on each shell and waits for the
    prompt.  This naturally drains the UART TX backlog (lp5814 errors etc.)
    because the prompt can only arrive after the backlog has been transmitted.
    No fixed sleep — purely event-driven.

    Args:
        client: Connected MtibV2Client.
        app_port: UART port name for app processor (nRF52840).
        comms_port: UART port name for comms coproc (nRF9151).
        boot_wait: Extra delay before power-on (e.g. for GPIOs).
        max_retries: Number of lock attempts before giving up.

    Returns:
        (app_shell, comms_shell, error) tuple.
        On success, both shells are locked and ready for commands.
        Caller must close them when done.
    """
    last_err = None
    for attempt in range(max_retries):
        app_shell, comms_shell, err = _attempt_lock(
            client, app_port, comms_port, boot_wait,
            do_jlink_reset=(attempt == 0),
        )
        if err is None:
            if attempt > 0:
                import sys
                print(
                    f"  Shell lock succeeded on attempt {attempt + 1}/{max_retries}",
                    file=sys.stderr,
                )
            break
        last_err = err
        import sys
        print(
            f"  Shell lock attempt {attempt + 1}/{max_retries} failed: {err}",
            file=sys.stderr,
        )
    else:
        return None, None, last_err

    # Two-phase drain:
    #
    # Phase A — Wait for the device's UART TX ring buffer to drain.
    # After boot, the TX buffer may hold 100+ KB of log messages that
    # take 3+ minutes to transmit at 115200 baud.  wait_for_quiet()
    # monitors the data rate and returns when no new data arrives for
    # 3 seconds, indicating the backlog has cleared.
    #
    # Phase B — Send "debug_enable 0" to silence mfg shell debug output.
    # The response takes 60-90+ seconds because Zephyr kernel log
    # messages interleave with shell I/O at the character level.
    # Instead of prompt-based completion detection (which fails due to
    # echo characters being consumed by log noise stripping), we
    # monitor the LOG-STRIPPED text length and wait for it to stop
    # growing.  When the cleaned text is stable for SETTLE_QUIET
    # seconds, the response has fully arrived.
    QUIET_TIMEOUT = 300.0   # Max time to wait for TX backlog to drain

    def drain_thread(name, shell):
        import sys
        # Phase A: wait for TX backlog to drain using persistent stream.
        # During boot, high data volume naturally flushes the gRPC buffer.
        err = shell.wait_for_quiet(timeout=QUIET_TIMEOUT, quiet_duration=3.0)
        if err:
            print(f"  [{name}] TX drain: {err}", file=sys.stderr, flush=True)
        else:
            print(f"  [{name}] TX backlog drained", file=sys.stderr, flush=True)

        # Phase B: disable mfg shell debug output using send_command().
        # send_command() creates a fresh stream with \r pings that
        # flush the gRPC server buffer reliably.
        err, _resp = shell.send_command("debug_enable 0", timeout=30.0)
        if err:
            print(
                f"  [{name}] debug_enable 0: {err[:100]}",
                file=sys.stderr, flush=True,
            )

    t_app = threading.Thread(target=drain_thread, args=("app", app_shell))
    t_comms = threading.Thread(target=drain_thread, args=("comms", comms_shell))
    t_app.start()
    t_comms.start()
    t_app.join(timeout=QUIET_TIMEOUT + 60)
    t_comms.join(timeout=QUIET_TIMEOUT + 60)

    return app_shell, comms_shell, None


# ---------------------------------------------------------------------------
# Response parsing utilities
# ---------------------------------------------------------------------------
def parse_key_value(text: str, key: str) -> Optional[str]:
    """Parse a "Key: value" line from shell output.

    Searches line-by-line for a line containing *key* and a colon,
    then returns everything after the colon.  Noise lines are naturally
    skipped because they don't contain the key.

    Args:
        text: Full shell response text.
        key: Key to search for (e.g. "Ext flash chip ID").

    Returns:
        The value string, or None if not found.
    """
    for line in text.split("\n"):
        clean = strip_ansi(line)
        if key in clean and ":" in clean:
            idx = clean.find(key)
            after_key = clean[idx + len(key):]
            colon_idx = after_key.find(":")
            if colon_idx != -1:
                return after_key[colon_idx + 1:].strip()
    return None


def parse_numeric_value(text: str, key: str) -> Optional[float]:
    """Parse a numeric value from a "Key: value" line.

    Args:
        text: Full shell response text.
        key: Key to search for.

    Returns:
        The numeric value, or None if not found or unparseable.
    """
    raw = parse_key_value(text, key)
    if raw:
        try:
            cleaned = re.sub(r"[^0-9.\-]", "", raw)
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
    return None
