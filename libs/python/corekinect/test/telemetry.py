"""Real-time telemetry streaming for device data (UART, power, sensors).

Dual-path delivery:
  1. WebSocket relay (live) -- batched POST to backend every 200ms
  2. MinIO storage (persistent) -- per-channel JSONL files + manifest

Channels are auto-discovered from sample types. Adding a new data stream
is just ``streamer.push("adc", {"value": 3.3}, target="ch0")``.

    streamer = TelemetryStreamer(run_id, api_url, api_key)
    streamer.start()
    uart_demuxer.on_line = streamer.push_uart
    streamer.set_test("test_02_flash_firmware")
    # ... test runs, data flows ...
    streamer.stop()  # writes channel files + manifest to MinIO
"""

import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from corekinect.utils import Logger

log = Logger(log_name="telemetry")

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


class TelemetryStreamer:
    """Batched telemetry streaming with live + persistent delivery.

    Args:
        on_flush_storage: Callback (object_path, content_bytes) -> None
            for MinIO writes. None = live-only mode.
        flush_interval_s: WebSocket batch flush interval.
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
        self._current_module: Optional[str] = None

        # WebSocket batch buffer (flushed every flush_interval_s)
        self._ws_buffer: List[Dict[str, Any]] = []
        self._ws_lock = threading.Lock()

        # Per-channel accumulators (flushed to MinIO on stop)
        # Key: channel name (e.g., "power", "uart_app")
        self._channel_data: Dict[str, List[Dict[str, Any]]] = {}
        self._channel_lock = threading.Lock()

        # Channel metadata (auto-discovered from samples)
        # Key: channel name → {type, unit, ...}
        self._channel_meta: Dict[str, Dict[str, Any]] = {}

        # Test step boundaries (for manifest)
        self._steps: List[Dict[str, Any]] = []
        self._step_start_t: Optional[float] = None

        # Also keep per-test accumulators for backward-compatible per-test JSONL
        self._test_data: Dict[str, List[Dict[str, Any]]] = {}
        self._test_lock = threading.Lock()

        # Cached env var — read once, not on every flush
        self._host_header: Optional[str] = os.environ.get("CONCORD_API_HOST")

        # Flush thread
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

        # Stats
        self._total_samples = 0
        self._total_flushes = 0

        self.enabled = bool(run_id)

    # ── Channel name resolution ────────────────────────────────

    @staticmethod
    def _channel_name(sample_type: str, target: Optional[str] = None) -> str:
        """Derive channel name from sample type + optional target.

        Examples:
            ("power", None) → "power"
            ("uart", "app") → "uart_app"
            ("power_chg", None) → "power_chg"
            ("accel", None) → "accel"
            ("adc", "ch0") → "adc_ch0"
            ("gpio", "3") → "gpio_3"
        """
        if target:
            return f"{sample_type}_{target}"
        return sample_type

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start background WebSocket flush thread."""
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
        """Stop flush thread, write channel JSONL files + manifest to storage."""
        if not self._started:
            return

        self._stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

        # Final WebSocket flush
        self._flush_ws_batch()

        # Close the last test step
        if self._current_test:
            self._close_step()
            # Flush per-test data (backward compat)
            self._flush_test_to_storage(self._current_test)
            self._current_test = None

        # Write per-channel JSONL files + manifest
        self._flush_channels_to_storage()

        self._started = False
        log.info("Telemetry streamer stopped (%d samples, %d flushes, %d channels)",
                 self._total_samples, self._total_flushes, len(self._channel_data))

    # ── Test step tracking ────────────────────────────────────

    def set_test(
        self,
        test_name: Optional[str],
        module: Optional[str] = None,
    ) -> None:
        """Set current test name for step boundaries. Pass None on session end."""
        # Close previous step
        if self._current_test:
            self._close_step()
            # Flush per-test data (backward compat)
            self._flush_test_to_storage(self._current_test)

        self._current_test = test_name
        self._current_module = module

        # Open new step
        if test_name:
            self._step_start_t = time.time()

    def _close_step(self) -> None:
        """Record the end of the current test step."""
        if self._current_test and self._step_start_t is not None:
            self._steps.append({
                "name": self._current_test,
                "module": self._current_module,
                "startedAt": self._step_start_t,
                "finishedAt": time.time(),
            })

    # ── Data ingestion ────────────────────────────────────────

    def push_uart(self, target_name: str, posix_us: int, line: str,
                  target_id: Optional[str] = None) -> None:
        """Push a UART line (called by UartDemuxer.on_line callback).

        Args:
            target_name: UART target ("app" or "comms")
            posix_us: Timestamp in microseconds
            line: UART line content
            target_id: RunTarget ID for per-slot routing in multi-slot runs
        """
        t = posix_us / 1_000_000
        channel = self._channel_name("uart", target_name)

        # Channel sample (for per-channel JSONL — lean, no redundant fields)
        channel_sample = {"t": t, "line": line}

        # WebSocket sample (includes type/target for frontend routing)
        ws_sample = {
            "t": t,
            "type": "uart",
            "target": target_name,
            "test": self._current_test,
            "line": line,
        }
        if target_id:
            ws_sample["targetId"] = target_id

        self._push_to_channel(channel, channel_sample, "text")
        self._push_to_ws(ws_sample)
        self._push_to_test(ws_sample)
        self._total_samples += 1

    def push_power(self, timestamp_s: float, current_ma: float, voltage_mv: float,
                   target_id: Optional[str] = None) -> None:
        """Push a power measurement sample.

        Args:
            target_id: RunTarget ID for per-slot routing in multi-slot runs
        """
        mA = round(current_ma, 2)
        mV = round(voltage_mv, 1)

        channel_sample = {"t": timestamp_s, "mA": mA, "mV": mV}
        ws_sample = {
            "t": timestamp_s,
            "type": "power",
            "test": self._current_test,
            "mA": mA,
            "mV": mV,
        }
        if target_id:
            ws_sample["targetId"] = target_id

        self._push_to_channel("power", channel_sample, "timeseries", unit="mA")
        self._push_to_ws(ws_sample)
        self._push_to_test(ws_sample)
        self._total_samples += 1

    def push(self, sample_type: str, data: Dict[str, Any],
             target: Optional[str] = None,
             target_id: Optional[str] = None) -> None:
        """Push a generic telemetry sample. Channel is auto-created on first push.

        Args:
            sample_type: e.g., "power_chg", "accel", "temp", "adc", "gpio"
            data: Payload dict (don't include "t" -- added automatically).
            target: Optional sub-target (e.g., "ch0" for ADC channels).
            target_id: RunTarget ID for per-slot routing in multi-slot runs.
        """
        t = time.time()
        channel = self._channel_name(sample_type, target)

        channel_sample = {"t": t, **data}
        ws_sample = {
            "t": t,
            "type": sample_type,
            "test": self._current_test,
            **data,
        }
        if target:
            ws_sample["target"] = target
        if target_id:
            ws_sample["targetId"] = target_id

        # Infer channel type from data shape
        ch_type = "timeseries"
        if "line" in data:
            ch_type = "text"
        elif "state" in data and len(data) == 1:
            ch_type = "event"

        self._push_to_channel(channel, channel_sample, ch_type)
        self._push_to_ws(ws_sample)
        self._push_to_test(ws_sample)
        self._total_samples += 1

    # ── Internal: routing to buffers ───────────────────────────

    def _push_to_channel(self, channel: str, sample: Dict[str, Any],
                         ch_type: str, unit: Optional[str] = None) -> None:
        """Accumulate a sample in the per-channel buffer."""
        with self._channel_lock:
            if channel not in self._channel_data:
                self._channel_data[channel] = []
                self._channel_meta[channel] = {"type": ch_type}
                if unit:
                    self._channel_meta[channel]["unit"] = unit
            self._channel_data[channel].append(sample)

    def _push_to_ws(self, sample: Dict[str, Any]) -> None:
        """Add a sample to the WebSocket batch buffer."""
        with self._ws_lock:
            self._ws_buffer.append(sample)

    def _push_to_test(self, sample: Dict[str, Any]) -> None:
        """Add a sample to the per-test accumulator (backward compat)."""
        test = sample.get("test")
        if test:
            with self._test_lock:
                if test not in self._test_data:
                    self._test_data[test] = []
                self._test_data[test].append(sample)

    # ── Internal: flushing ─────────────────────────────────────

    def _flush_loop(self) -> None:
        """Background thread: flush WebSocket batch at regular intervals."""
        while not self._stop_event.wait(self._flush_interval):
            self._flush_ws_batch()
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

            if self._host_header:
                headers["Host"] = self._host_header

            _requests.post(
                f"{self._api_url}/v2/runs/{self._run_id}/report/telemetry",
                json={"samples": batch},
                headers=headers,
                timeout=2,
                verify=_TLS_VERIFY,
            )
        except Exception as exc:
            log.warning("Telemetry flush to API failed: %s", exc)

    def _flush_test_to_storage(self, test_name: str) -> None:
        """Write a test's accumulated telemetry to per-test JSONL (backward compat)."""
        with self._test_lock:
            data = self._test_data.pop(test_name, [])

        if not data or not self._on_flush_storage:
            return

        lines = [json.dumps(s, separators=(",", ":")) for s in data]
        content = "\n".join(lines) + "\n"

        try:
            self._on_flush_storage(
                f"telemetry/{test_name}.jsonl",
                content.encode("utf-8"),
            )
        except Exception as e:
            log.warning("Failed to flush per-test telemetry for %s: %s", test_name, e)

    def _flush_channels_to_storage(self) -> None:
        """Write per-channel JSONL files and manifest to persistent storage."""
        if not self._on_flush_storage:
            return

        with self._channel_lock:
            channels = dict(self._channel_data)
            self._channel_data.clear()
            meta = dict(self._channel_meta)

        if not channels:
            return

        # Write each channel's JSONL file
        manifest_channels: Dict[str, Any] = {}

        for channel_name, samples in channels.items():
            if not samples:
                continue

            # Build JSONL content
            lines = [json.dumps(s, separators=(",", ":")) for s in samples]
            content = "\n".join(lines) + "\n"
            filename = f"{channel_name}.jsonl"

            try:
                self._on_flush_storage(
                    f"telemetry/{filename}",
                    content.encode("utf-8"),
                )
            except Exception as e:
                log.warning("Failed to flush channel %s: %s", channel_name, e)
                continue

            # Channel metadata for manifest
            timestamps = [s["t"] for s in samples if "t" in s]
            ch_meta = meta.get(channel_name, {})
            manifest_channels[channel_name] = {
                "type": ch_meta.get("type", "timeseries"),
                "file": filename,
                "sampleCount": len(samples),
                "minT": min(timestamps) if timestamps else None,
                "maxT": max(timestamps) if timestamps else None,
            }
            if "unit" in ch_meta:
                manifest_channels[channel_name]["unit"] = ch_meta["unit"]

        # Build manifest
        all_min_t = [c["minT"] for c in manifest_channels.values() if c.get("minT")]
        all_max_t = [c["maxT"] for c in manifest_channels.values() if c.get("maxT")]

        manifest = {
            "version": 1,
            "runId": self._run_id,
            "startedAt": min(all_min_t) if all_min_t else None,
            "finishedAt": max(all_max_t) if all_max_t else None,
            "totalSamples": self._total_samples,
            "channels": manifest_channels,
            "steps": self._steps,
        }

        try:
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            self._on_flush_storage("telemetry/manifest.json", manifest_bytes)
            log.info(
                "Telemetry manifest written: %d channels, %d steps, %d samples",
                len(manifest_channels), len(self._steps), self._total_samples,
            )
        except Exception as e:
            log.warning("Failed to write telemetry manifest: %s", e)
