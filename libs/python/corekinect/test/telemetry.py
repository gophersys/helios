"""Real-time telemetry streaming for device data (UART, power, sensors).

Dual-path delivery:
  1. WebSocket relay (live) — batched POST to backend every 200ms
  2. MinIO storage (persistent) — per-test JSONL files flushed on test completion

Every sample is timestamped (POSIX seconds with microsecond precision) and
tagged with the active test step name, enabling:
  - Live rendering in the frontend during test execution
  - Post-run reconstruction from artifacts
  - Per-test-step filtering (click a step → see its telemetry slice)

Usage:
    streamer = TelemetryStreamer(run_id, api_url, api_key)
    streamer.start()

    # Wire data sources
    uart_demuxer.on_line = streamer.push_uart
    # power_profiler.on_sample = streamer.push_power  # when ready

    # Track test steps (called by pytest lifecycle hooks)
    streamer.set_test("test_02_flash_firmware")
    # ... test runs, UART/power data flows ...
    streamer.set_test("test_03_verify_boot")  # flushes previous test to MinIO
    # ...
    streamer.set_test(None)  # flushes last test

    streamer.stop()  # final flush + cleanup
"""

import io
import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from corekinect.utils import Logger

log = Logger(log_name="telemetry")

# Attempt to import requests; if not installed, WebSocket relay is disabled.
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


class TelemetryStreamer:
    """Batched telemetry streaming with dual-path delivery.

    Args:
        run_id: Validation run ID (for MinIO paths and WebSocket routing).
        api_url: Concord API base URL (for WebSocket relay).
        api_key: API key for authentication.
        on_flush_storage: Callback to write JSONL content to persistent storage.
            Signature: (object_path: str, content_bytes: bytes) -> None
            If None, persistent storage is disabled (live-only mode).
        flush_interval_s: How often to flush WebSocket batches (seconds).
            Lower = more real-time but more HTTP overhead.
    """

    def __init__(
        self,
        run_id: str,
        api_url: str = "",
        api_key: str = "",
        on_flush_storage: Optional[Callable[[str, bytes], None]] = None,
        flush_interval_s: float = 0.2,
    ):
        self._run_id = run_id
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._on_flush_storage = on_flush_storage
        self._flush_interval = flush_interval_s

        # Current test step (set by pytest hooks)
        self._current_test: Optional[str] = None

        # WebSocket batch buffer (flushed every flush_interval_s)
        self._ws_buffer: List[Dict[str, Any]] = []
        self._ws_lock = threading.Lock()

        # Per-test accumulator (flushed to MinIO on test step change)
        self._test_data: Dict[str, List[Dict[str, Any]]] = {}
        self._test_lock = threading.Lock()

        # Flush thread
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

        # Stats
        self._total_samples = 0
        self._total_flushes = 0

        self.enabled = bool(run_id)

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start the background flush thread."""
        if self._started or not self.enabled:
            return

        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="telemetry-flush"
        )
        self._flush_thread.start()
        self._started = True
        log.info("Telemetry streamer started (run_id=%s, interval=%.0fms)",
                 self._run_id, self._flush_interval * 1000)

    def stop(self) -> None:
        """Stop the flush thread and flush remaining data."""
        if not self._started:
            return

        self._stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

        # Final WebSocket flush
        self._flush_ws_batch()

        # Flush any remaining test data to storage
        if self._current_test:
            self._flush_test_to_storage(self._current_test)
            self._current_test = None

        self._started = False
        log.info("Telemetry streamer stopped (%d samples, %d flushes)",
                 self._total_samples, self._total_flushes)

    # ── Test step tracking ────────────────────────────────────

    def set_test(self, test_name: Optional[str]) -> None:
        """Set the current test step. Flushes previous test's data to storage.

        Called by pytest lifecycle hooks:
          - set_test("test_02_flash") on test start
          - set_test("test_03_boot") on next test (flushes test_02 data)
          - set_test(None) on session end (flushes last test)
        """
        prev_test = self._current_test
        self._current_test = test_name

        # Flush previous test's data to persistent storage
        if prev_test:
            self._flush_test_to_storage(prev_test)

    # ── Data ingestion ────────────────────────────────────────

    def push_uart(self, target_name: str, posix_us: int, line: str) -> None:
        """Push a UART line. Called by UartDemuxer.on_line callback.

        Args:
            target_name: "app" or "comms"
            posix_us: POSIX timestamp in microseconds
            line: UART line content
        """
        sample = {
            "t": posix_us / 1_000_000,
            "type": "uart",
            "target": target_name,
            "test": self._current_test,
            "line": line,
        }
        self._push(sample)

    def push_power(self, timestamp_s: float, current_ma: float, voltage_mv: float) -> None:
        """Push a power measurement sample.

        Args:
            timestamp_s: POSIX timestamp in seconds
            current_ma: Current in milliamps
            voltage_mv: Voltage in millivolts
        """
        sample = {
            "t": timestamp_s,
            "type": "power",
            "test": self._current_test,
            "mA": round(current_ma, 2),
            "mV": round(voltage_mv, 1),
        }
        self._push(sample)

    def push(self, sample_type: str, data: Dict[str, Any],
             target: Optional[str] = None) -> None:
        """Push a generic telemetry sample (for future sensor types).

        Args:
            sample_type: e.g., "accel", "temp", "gps"
            data: Payload dict (e.g., {"x": 0.02, "y": -0.98, "z": 0.01})
            target: Optional target identifier
        """
        sample = {
            "t": time.time(),
            "type": sample_type,
            "test": self._current_test,
            **data,
        }
        if target:
            sample["target"] = target
        self._push(sample)

    # ── Internal ──────────────────────────────────────────────

    def _push(self, sample: Dict[str, Any]) -> None:
        """Add a sample to both WebSocket buffer and test accumulator."""
        self._total_samples += 1

        # WebSocket batch buffer
        with self._ws_lock:
            self._ws_buffer.append(sample)

        # Per-test accumulator for MinIO storage
        test = sample.get("test")
        if test:
            with self._test_lock:
                if test not in self._test_data:
                    self._test_data[test] = []
                self._test_data[test].append(sample)

    def _flush_loop(self) -> None:
        """Background thread: flush WebSocket batch at regular intervals."""
        while not self._stop_event.wait(self._flush_interval):
            self._flush_ws_batch()
        # Final flush on stop
        self._flush_ws_batch()

    def _flush_ws_batch(self) -> None:
        """Send buffered samples to backend for WebSocket broadcast."""
        with self._ws_lock:
            if not self._ws_buffer:
                return
            batch = self._ws_buffer
            self._ws_buffer = []

        if not self._api_url or not _HAS_REQUESTS:
            return

        self._total_flushes += 1

        try:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                if self._api_key.startswith("ck_"):
                    headers["Authorization"] = f"ApiKey {self._api_key}"
                else:
                    headers["Authorization"] = f"Bearer {self._api_key}"

            # Include Host header override if configured
            host_header = os.environ.get("CONCORD_API_HOST")
            if host_header:
                headers["Host"] = host_header

            _requests.post(
                f"{self._api_url}/v2/sessions/{self._run_id}/report/telemetry",
                json={"samples": batch},
                headers=headers,
                timeout=2,
                verify=_TLS_VERIFY,
            )
        except Exception:
            pass  # Fire-and-forget — never fail tests on telemetry errors

    def _flush_test_to_storage(self, test_name: str) -> None:
        """Write a test's accumulated telemetry to persistent storage as JSONL."""
        with self._test_lock:
            data = self._test_data.pop(test_name, [])

        if not data or not self._on_flush_storage:
            return

        # Build JSONL content
        lines = [json.dumps(s, separators=(",", ":")) for s in data]
        content = "\n".join(lines) + "\n"
        content_bytes = content.encode("utf-8")

        object_path = f"telemetry/{test_name}.jsonl"

        try:
            self._on_flush_storage(object_path, content_bytes)
            log.debug("Flushed %d samples for %s (%d bytes)",
                      len(data), test_name, len(content_bytes))
        except Exception as e:
            log.warning("Failed to flush telemetry for %s: %s", test_name, e)
