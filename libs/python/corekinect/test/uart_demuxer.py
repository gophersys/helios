"""Dual-target UART capture with command sending and crash-safe persistence.

Captures APP (nRF52840) and COMMS (nRF9151) UART streams in parallel
background threads. Lines are buffered in memory for test assertions
and written to local files incrementally as they arrive.

    demuxer = UartDemuxer(mtib, log_dir="/tmp/uart")
    demuxer.start()
    demuxer.send("comms", "lock_shell")
    line = demuxer.wait_for_log("mode ON", target="comms", timeout_s=10)
    demuxer.stop()
"""

from __future__ import annotations

import os
import queue
import re
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import Logger
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

# Target can be a HostType enum or a string shorthand ("app", "comms").
# HostType is a protobuf EnumTypeWrapper, not a standard type — use string
# annotation in Union to avoid runtime TypeError.
TargetType = Union["HostType", str]

log = Logger(log_name="uart_demuxer")


class UartDemuxer:
    """Dual-target UART capture with command sending and persistence.

    Args:
        mtib: Connected MtibV1Client.
        targets: HostType list. Defaults to [APP, COMMS].
        log_dir: If set, writes uart_app.log / uart_comms.log incrementally.
        pump_hz: gRPC request pump rate (default: 20 Hz).
    """

    APP = HostType.HOST_TYPE_NRF52840
    COMMS = HostType.HOST_TYPE_NRF9151

    TARGET_NAMES = {
        HostType.HOST_TYPE_NRF52840: "app",
        HostType.HOST_TYPE_NRF9151: "comms",
    }

    def __init__(
        self,
        mtib,
        targets: Optional[List[HostType]] = None,
        log_dir: Optional[str] = None,
        pump_hz: float = 20,
    ):
        self._mtib = mtib
        self._targets = targets if targets is not None else [self.APP, self.COMMS]
        self._log_dir = log_dir
        self._pump_interval = 1.0 / pump_hz

        # Per-target state
        self._buffers: Dict[HostType, List[Tuple[float, str]]] = {
            t: [] for t in self._targets
        }
        self._partial: Dict[HostType, str] = {t: "" for t in self._targets}
        self._cmd_queues: Dict[HostType, queue.Queue] = {
            t: queue.Queue() for t in self._targets
        }
        self._threads: Dict[HostType, threading.Thread] = {}
        self._log_files: Dict[HostType, object] = {}

        # Shared state
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._mono_start: Optional[float] = None
        self._posix_start: Optional[float] = None

        # Callback: on_line(target_name: str, posix_us: int, line: str)
        self.on_line: Optional[Callable[[str, int, str], None]] = None

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """Start background capture threads for all targets."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._mono_start = time.monotonic()
        self._posix_start = time.time()

        # Open local log files
        if self._log_dir:
            os.makedirs(self._log_dir, exist_ok=True)
            for target in self._targets:
                name = self.TARGET_NAMES.get(target, str(target))
                path = os.path.join(self._log_dir, f"uart_{name}.log")
                self._log_files[target] = open(path, "a", encoding="utf-8")

        # Start capture threads
        for target in self._targets:
            name = self.TARGET_NAMES.get(target, str(target))
            thread = threading.Thread(
                target=self._capture_loop,
                args=(target,),
                daemon=True,
                name=f"uart-{name}",
            )
            thread.start()
            self._threads[target] = thread

        targets_str = ", ".join(
            self.TARGET_NAMES.get(t, str(t)) for t in self._targets
        )
        log.info("UART capture started: [%s]", targets_str)

    def stop(self) -> None:
        """Stop all capture threads and close log files."""
        self._running = False
        self._stop_event.set()

        for thread in self._threads.values():
            thread.join(timeout=5)
        self._threads.clear()

        for f in self._log_files.values():
            try:
                f.close()
            except Exception as exc:
                log.warning("Failed to close UART log file: %s", exc)
        self._log_files.clear()

        log.info("UART capture stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def set_pump_rate(self, hz: float) -> None:
        """Change pump rate (Hz) for all capture threads. Immediate effect."""
        self._pump_interval = 1.0 / hz

    # ── Command sending ─────────────────────────────────────

    def send(self, target: TargetType, command: str) -> None:
        """Queue a shell command for the next pump cycle.

        Wraps with \\r. Use send_bytes() for raw data.
        """
        t = self._resolve_target(target)
        data = f"\r{command}\r".encode("utf-8")
        self._cmd_queues[t].put(data)

    def send_bytes(self, target: TargetType, data: bytes) -> None:
        """Queue raw bytes to send (no \\r wrapping)."""
        t = self._resolve_target(target)
        self._cmd_queues[t].put(data)

    # ── Log retrieval ───────────────────────────────────────

    def get_logs(
        self, target: Optional[TargetType] = None, since: Optional[float] = None
    ) -> Union[List[str], List[Tuple[str, str]]]:
        """Return captured log lines.

        With target: returns List[str]. Without: List[Tuple[target_name, line]].

        Args:
            since: Only include lines after this monotonic timestamp.
        """
        if target is not None:
            t = self._resolve_target(target)
            with self._lock:
                lines = self._buffers.get(t, [])
                if since is not None:
                    lines = [(ts, line) for ts, line in lines if ts >= since]
                return [line for _, line in lines]

        # All targets — merged by timestamp
        with self._lock:
            merged = []
            for t in self._targets:
                name = self.TARGET_NAMES.get(t, str(t))
                for ts, line in self._buffers.get(t, []):
                    if since is None or ts >= since:
                        merged.append((ts, name, line))
        merged.sort(key=lambda x: x[0])
        return [(name, line) for _, name, line in merged]

    def get_timeline(
        self, since: Optional[float] = None
    ) -> List[Tuple[float, str, str]]:
        """Return merged (monotonic_ts, target_name, line) tuples, sorted by time."""
        with self._lock:
            result = []
            for t in self._targets:
                name = self.TARGET_NAMES.get(t, str(t))
                for ts, line in self._buffers.get(t, []):
                    if since is None or ts >= since:
                        result.append((ts, name, line))
        result.sort(key=lambda x: x[0])
        return result

    def wait_for_log(
        self,
        pattern: str,
        target=None,
        timeout_s: float = 10,
        since: Optional[float] = None,
    ) -> str:
        """Wait for a log line matching the regex pattern.

        Returns the first matching line.

        Raises:
            TimeoutError: If no match within timeout_s.
        """
        t = self._resolve_target(target) if target is not None else None
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout_s
        check_from = since  # None means check all buffered lines

        while time.monotonic() < deadline:
            with self._lock:
                targets_to_check = [t] if t else self._targets
                for check_t in targets_to_check:
                    for ts, line in self._buffers.get(check_t, []):
                        if check_from is not None and ts < check_from:
                            continue
                        if compiled.search(line):
                            return line
            time.sleep(0.1)

        raise TimeoutError(
            f"No UART log matching '{pattern}' within {timeout_s}s"
        )

    # ── Buffer management ───────────────────────────────────

    def clear(self) -> None:
        """Clear in-memory buffers. Local log files are NOT affected."""
        with self._lock:
            for t in self._targets:
                self._buffers[t] = []

    def dump_to_file(self, path: str, target: Optional[TargetType] = None) -> None:
        """Write buffered logs to file. None target = merged timeline."""
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        if target is not None:
            t = self._resolve_target(target)
            with self._lock:
                lines = list(self._buffers.get(t, []))
            with open(path, "w", encoding="utf-8") as f:
                for ts, line in lines:
                    f.write(f"[{ts:.3f}] {line}\n")
        else:
            timeline = self.get_timeline()
            with open(path, "w", encoding="utf-8") as f:
                for ts, name, line in timeline:
                    f.write(f"[{ts:.3f}] [{name}] {line}\n")

        total = sum(len(self._buffers.get(t, [])) for t in self._targets)
        log.info("Dumped %d lines to %s", total, path)

    # ── Internal ────────────────────────────────────────────

    def _resolve_target(self, target: TargetType) -> HostType:
        """Convert string shorthand to HostType."""
        if isinstance(target, str):
            name_to_type = {v: k for k, v in self.TARGET_NAMES.items()}
            lower = target.lower()
            if lower in name_to_type:
                return name_to_type[lower]
            raise ValueError(
                f"Unknown target '{target}'. Use: {list(name_to_type.keys())}"
            )
        return target

    def _capture_loop(self, target: HostType) -> None:
        """Background thread: pump requests, process responses."""
        target_name = self.TARGET_NAMES.get(target, str(target))

        try:
            def request_gen():
                while not self._stop_event.is_set():
                    data = b""
                    try:
                        data = self._cmd_queues[target].get_nowait()
                    except queue.Empty:
                        pass

                    yield UartStreamRequest(target=target, data=data)
                    self._stop_event.wait(timeout=self._pump_interval)

            for resp in self._mtib.UartStream(target, request_gen()):
                if not self._running:
                    break
                if resp.data and len(resp.data) > 0:
                    self._process_data(target, resp.data)
        except Exception as e:
            if self._running:
                log.error("UART capture error [%s]: %s", target_name, e)

    def _process_data(self, target: HostType, data: bytes) -> None:
        """Assemble bytes into lines, handling partial data."""
        text = data.decode("utf-8", errors="replace")
        self._partial[target] += text

        while "\n" in self._partial[target]:
            line, self._partial[target] = self._partial[target].split("\n", 1)
            line = line.rstrip("\r")
            if line:
                self._emit_line(target, line)

    def _emit_line(self, target: HostType, line: str) -> None:
        """Buffer, persist, and notify for a complete line."""
        now = time.monotonic()
        target_name = self.TARGET_NAMES.get(target, str(target))

        # 1. In-memory buffer (for get_logs, wait_for_log)
        with self._lock:
            self._buffers[target].append((now, line))

        # 2. Local file (crash-safe, flushed immediately)
        if target in self._log_files and self._mono_start is not None:
            elapsed = now - self._mono_start
            posix_us = int((self._posix_start + elapsed) * 1_000_000)
            try:
                self._log_files[target].write(f"[{posix_us}] {line}\n")
                self._log_files[target].flush()
            except Exception as exc:
                log.warning("Failed to write UART line to log file: %s", exc)

        # 3. Callback (for ArtifactWriter / MinIO / WebSocket pipeline)
        if self.on_line:
            elapsed = now - self._mono_start
            posix_us = int((self._posix_start + elapsed) * 1_000_000)
            try:
                self.on_line(target_name, posix_us, line)
            except Exception as exc:
                log.warning("UART on_line callback failed: %s", exc)
