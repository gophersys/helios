"""Unified test artifact storage with MinIO backend and HTTP notifications.

This module provides thread-safe artifact writing for validation tests:
- Log files (console output, test logs)
- UART captures with POSIX timestamps
- Binary power traces with header metadata
- Manifest tracking for test artifacts

Opt-in activation via environment variables:
    STORAGE_URL:               MinIO endpoint URL (e.g., http://minio:9000).
    STORAGE_ACCESS_KEY:        MinIO access key.
    STORAGE_SECRET_ACCESS_KEY: MinIO secret key.
    STORAGE_BUCKET:            Bucket name (default: concord).
    CONCORD_RUN_ID:            Validation run ID.
    CONCORD_API_URL:           (Optional) Backend URL for chunk notifications.
    CONCORD_API_KEY:           (Optional) API key for notifications.

When storage is not configured, all writes are no-ops.
"""

import io
import json
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="artifact_writer")

# Optional imports
try:
    from minio import Minio
    _HAS_MINIO = True
except ImportError:
    _HAS_MINIO = False

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# TLS verification — enabled by default, can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


# Binary power trace format constants
POWER_MAGIC = b"CKPWR001"
POWER_HEADER_SIZE = 32
POWER_FLAG_HAS_CH0 = 0x01
POWER_FLAG_HAS_CH1 = 0x02
POWER_FLAG_HAS_JOULESCOPE = 0x04


class _StorageConfig(EnvConfig):
    """MinIO storage config loaded from environment variables."""
    ENV_PREFIX = ""

    STORAGE_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    STORAGE_BUCKET: str = "concord"
    CONCORD_RUN_ID: Optional[str] = None
    CONCORD_API_URL: Optional[str] = None
    CONCORD_API_KEY: Optional[str] = None
    CONCORD_API_HOST: Optional[str] = None


@dataclass
class ArtifactInfo:
    """Metadata for a single test's artifacts in the manifest."""
    name: str
    status: str = "running"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)


@dataclass
class PowerSample:
    """A single power measurement sample."""
    timestamp_offset_us: int  # Microseconds from trace start
    ch0_voltage_mv: Optional[int] = None
    ch0_current_ua: Optional[int] = None
    ch1_voltage_mv: Optional[int] = None
    ch1_current_ua: Optional[int] = None
    js_current_na: Optional[int] = None
    js_voltage_mv: Optional[int] = None


class ArtifactWriter:
    """Thread-safe artifact writer with MinIO backend.

    Writes artifacts to MinIO under the path:
        validation/runs/{run_id}/{test_name}/{artifact_name}

    For session-level artifacts (no test context):
        validation/runs/{run_id}/{artifact_name}

    Usage:
        writer = ArtifactWriter()

        # Start a test
        writer.start_test("test_boot")
        writer.append_log("Boot sequence started\\n")
        writer.append_uart("app", 1709971200000000, "[00:00:00.000,000] <inf> main: Hello\\n")
        writer.finish_test("test_boot", status="passed")

        # Power trace
        writer.write_power_header("power.bin", flags=0x03, sample_rate_hz=1000)
        writer.append_power_sample("power.bin", PowerSample(
            timestamp_offset_us=1000,
            ch0_voltage_mv=4500, ch0_current_ua=15000,
            ch1_voltage_mv=5000, ch1_current_ua=2000
        ))
    """

    def __init__(self):
        cfg = _StorageConfig()
        self.storage_url = cfg.STORAGE_URL or ""
        self.access_key = cfg.STORAGE_ACCESS_KEY or ""
        self.secret_key = cfg.STORAGE_SECRET_ACCESS_KEY or ""
        self.bucket = cfg.STORAGE_BUCKET
        self.run_id = cfg.CONCORD_RUN_ID or ""
        self.api_url = (cfg.CONCORD_API_URL or "").rstrip("/")
        self.api_key = cfg.CONCORD_API_KEY or ""
        self.api_host = cfg.CONCORD_API_HOST or ""

        self.enabled = bool(self.storage_url and self.run_id and _HAS_MINIO)

        self._client: Optional["Minio"] = None
        self._lock = threading.Lock()

        # In-memory offset tracking for append operations
        # Key: object_name, Value: current byte offset
        self._offsets: Dict[str, int] = {}

        # In-memory content buffers for efficient batching
        # Key: object_name, Value: accumulated bytes
        self._buffers: Dict[str, bytes] = {}

        # Current test context
        self._current_test: Optional[str] = None

        # Manifest tracking
        self._manifest: Dict[str, Any] = {
            "runId": self.run_id,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "tests": [],
        }
        self._test_index: Dict[str, int] = {}  # test_name -> index in tests list

        if self.enabled:
            log.info(
                "ArtifactWriter: enabled (run_id=%s, bucket=%s)",
                self.run_id, self.bucket,
            )
        else:
            log.debug("ArtifactWriter: disabled (storage not configured)")

    def _get_client(self) -> "Minio":
        """Get or create MinIO client."""
        if self._client is None:
            endpoint = self.storage_url.replace("http://", "").replace("https://", "")
            secure = self.storage_url.startswith("https://")
            self._client = Minio(
                endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=secure,
            )
        return self._client

    def _object_path(self, filename: str, test_name: Optional[str] = None) -> str:
        """Build full object path in MinIO."""
        test = test_name or self._current_test
        if test:
            return f"validation/runs/{self.run_id}/{test}/{filename}"
        return f"validation/runs/{self.run_id}/{filename}"

    def _notify_chunk(self, object_name: str, offset: int, size: int) -> None:
        """Fire-and-forget HTTP notification about new artifact chunk.

        This notifies the backend that new data is available for streaming
        to connected WebSocket clients.
        """
        if not self.api_url or not _HAS_REQUESTS:
            return

        try:
            url = f"{self.api_url}/v2/sessions/{self.run_id}/report/artifact-chunk"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"ApiKey {self.api_key}"
            if self.api_host:
                headers["Host"] = self.api_host

            data = {
                "objectName": object_name,
                "offset": offset,
                "size": size,
            }

            # Fire-and-forget with short timeout
            requests.post(url, json=data, headers=headers, timeout=2, verify=_TLS_VERIFY)
        except Exception as e:
            # Never fail on notification errors
            log.debug("Artifact chunk notification failed: %s", e)

    def _write_object(self, object_name: str, data: bytes) -> bool:
        """Write bytes to MinIO object (overwrites existing)."""
        if not self.enabled:
            return False

        try:
            client = self._get_client()
            client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(data),
                length=len(data),
            )
            return True
        except Exception as e:
            log.warning("Failed to write %s: %s", object_name, e)
            return False

    def _read_object(self, object_name: str) -> Optional[bytes]:
        """Read existing object from MinIO."""
        if not self.enabled:
            return None

        try:
            client = self._get_client()
            response = client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception:
            # Object may not exist yet
            return None

    def _append_to_object(self, object_name: str, data: bytes) -> bool:
        """Append data to an object (read-modify-write pattern).

        MinIO does not support true append, so we read existing content,
        append new data, and write back. This is fine for log files.
        """
        if not self.enabled or not data:
            return False

        with self._lock:
            # Use in-memory buffer for efficiency
            existing = self._buffers.get(object_name)
            if existing is None:
                # First access - try to read from MinIO
                existing = self._read_object(object_name) or b""
                self._buffers[object_name] = existing

            old_size = len(existing)
            new_content = existing + data
            self._buffers[object_name] = new_content

            # Write to MinIO
            if self._write_object(object_name, new_content):
                self._offsets[object_name] = len(new_content)
                # Notify backend of new chunk
                self._notify_chunk(object_name, old_size, len(data))
                return True
            return False

    # ── Test lifecycle ───────────────────────────────────────

    def start_test(self, test_name: str) -> None:
        """Mark the start of a new test, update manifest."""
        with self._lock:
            self._current_test = test_name

            # Add to manifest
            info = ArtifactInfo(
                name=test_name,
                status="running",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            self._manifest["tests"].append({
                "name": info.name,
                "status": info.status,
                "startedAt": info.started_at,
                "finishedAt": info.finished_at,
                "artifacts": info.artifacts,
            })
            self._test_index[test_name] = len(self._manifest["tests"]) - 1

        log.debug("Started test: %s", test_name)
        self._update_manifest()

    def finish_test(self, test_name: str, status: str = "passed") -> None:
        """Mark test as finished, update manifest with status."""
        with self._lock:
            if test_name in self._test_index:
                idx = self._test_index[test_name]
                self._manifest["tests"][idx]["status"] = status
                self._manifest["tests"][idx]["finishedAt"] = datetime.now(timezone.utc).isoformat()

            if self._current_test == test_name:
                self._current_test = None

        log.debug("Finished test: %s (status=%s)", test_name, status)
        self._update_manifest()

    def _add_artifact_to_manifest(self, test_name: Optional[str], filename: str) -> None:
        """Record artifact in the manifest for the given test."""
        with self._lock:
            name = test_name or self._current_test
            if name and name in self._test_index:
                idx = self._test_index[name]
                artifacts = self._manifest["tests"][idx]["artifacts"]
                if filename not in artifacts:
                    artifacts.append(filename)

    def _update_manifest(self) -> None:
        """Write current manifest to MinIO."""
        if not self.enabled:
            return

        try:
            with self._lock:
                manifest_data = json.dumps(self._manifest, indent=2).encode("utf-8")

            object_name = f"validation/runs/{self.run_id}/manifest.json"
            self._write_object(object_name, manifest_data)
        except Exception as e:
            log.warning("Failed to update manifest: %s", e)

    # ── Log appending ────────────────────────────────────────

    def append_log(self, text: str, filename: str = "output.log", test_name: Optional[str] = None) -> bool:
        """Append text to a log file.

        Args:
            text: Text to append (should include newlines as needed).
            filename: Log filename (default: output.log).
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        object_name = self._object_path(filename, test_name)
        data = text.encode("utf-8")
        success = self._append_to_object(object_name, data)
        if success:
            self._add_artifact_to_manifest(test_name, filename)
        return success

    def append_console(self, text: str, test_name: Optional[str] = None) -> bool:
        """Append console/stdout output to console.log."""
        return self.append_log(text, filename="console.log", test_name=test_name)

    # ── UART capture ─────────────────────────────────────────

    def append_uart(
        self,
        target: str,
        posix_timestamp_us: int,
        line: str,
        test_name: Optional[str] = None
    ) -> bool:
        """Append a UART line with POSIX timestamp.

        Format: [{posix_timestamp_us}] {raw_zephyr_line}

        Args:
            target: UART target name (e.g., "app", "comms").
            posix_timestamp_us: POSIX timestamp in microseconds.
            line: Raw UART line (without timestamp prefix).
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        filename = f"uart_{target}.log"
        formatted = f"[{posix_timestamp_us}] {line}"
        if not formatted.endswith("\n"):
            formatted += "\n"

        object_name = self._object_path(filename, test_name)
        data = formatted.encode("utf-8")
        success = self._append_to_object(object_name, data)
        if success:
            self._add_artifact_to_manifest(test_name, filename)
        return success

    def append_uart_bytes(
        self,
        target: str,
        posix_timestamp_us: int,
        data: bytes,
        test_name: Optional[str] = None
    ) -> bool:
        """Append raw UART bytes with timestamp (for binary protocols).

        Encodes non-printable bytes as hex escape sequences.
        """
        # Convert to printable representation
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.hex()

        return self.append_uart(target, posix_timestamp_us, text, test_name)

    # ── Binary power traces ──────────────────────────────────

    def write_power_header(
        self,
        filename: str,
        flags: int,
        sample_rate_hz: int,
        start_timestamp_us: Optional[int] = None,
        test_name: Optional[str] = None,
    ) -> bool:
        """Write power trace header (32 bytes).

        Header format:
            Magic: "CKPWR001" (8 bytes)
            Flags: uint32 (bit 0: has_ch0, bit 1: has_ch1, bit 2: has_joulescope)
            Sample rate Hz: uint32
            Start timestamp: uint64 (POSIX microseconds)
            Reserved: 8 bytes

        Args:
            filename: Power trace filename (e.g., "power.bin").
            flags: Channel flags (POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1 | ...).
            sample_rate_hz: Sample rate in Hz.
            start_timestamp_us: Start timestamp in POSIX microseconds (default: now).
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        if start_timestamp_us is None:
            start_timestamp_us = int(time.time() * 1_000_000)

        # Pack header: 8s (magic) + I (flags) + I (rate) + Q (timestamp) + 8x (reserved)
        header = struct.pack(
            "<8sIIQ8x",
            POWER_MAGIC,
            flags,
            sample_rate_hz,
            start_timestamp_us,
        )
        assert len(header) == POWER_HEADER_SIZE

        object_name = self._object_path(filename, test_name)

        with self._lock:
            # Initialize buffer with header
            self._buffers[object_name] = header
            self._offsets[object_name] = POWER_HEADER_SIZE

        success = self._write_object(object_name, header)
        if success:
            self._add_artifact_to_manifest(test_name, filename)
            self._notify_chunk(object_name, 0, POWER_HEADER_SIZE)
        return success

    def append_power_sample(
        self,
        filename: str,
        sample: PowerSample,
        flags: Optional[int] = None,
        test_name: Optional[str] = None,
    ) -> bool:
        """Append a power sample to the trace.

        Sample format (variable based on flags in header):
            Timestamp offset: uint32 (microseconds from start)
            [if has_ch0] Ch0 voltage: uint16 (mV), current: int16 (uA)
            [if has_ch1] Ch1 voltage: uint16 (mV), current: int16 (uA)
            [if has_js] JS current: int32 (nA), voltage: uint16 (mV)

        Args:
            filename: Power trace filename (must match write_power_header call).
            sample: PowerSample with measurement data.
            flags: Channel flags (if None, auto-detect from sample fields).
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        # Auto-detect flags from sample if not provided
        if flags is None:
            flags = 0
            if sample.ch0_voltage_mv is not None or sample.ch0_current_ua is not None:
                flags |= POWER_FLAG_HAS_CH0
            if sample.ch1_voltage_mv is not None or sample.ch1_current_ua is not None:
                flags |= POWER_FLAG_HAS_CH1
            if sample.js_current_na is not None or sample.js_voltage_mv is not None:
                flags |= POWER_FLAG_HAS_JOULESCOPE

        # Build sample record
        parts = [struct.pack("<I", sample.timestamp_offset_us)]

        if flags & POWER_FLAG_HAS_CH0:
            v = sample.ch0_voltage_mv or 0
            i = sample.ch0_current_ua or 0
            parts.append(struct.pack("<Hh", v, i))

        if flags & POWER_FLAG_HAS_CH1:
            v = sample.ch1_voltage_mv or 0
            i = sample.ch1_current_ua or 0
            parts.append(struct.pack("<Hh", v, i))

        if flags & POWER_FLAG_HAS_JOULESCOPE:
            i = sample.js_current_na or 0
            v = sample.js_voltage_mv or 0
            parts.append(struct.pack("<iH", i, v))

        data = b"".join(parts)
        object_name = self._object_path(filename, test_name)
        return self._append_to_object(object_name, data)

    def append_power_samples(
        self,
        filename: str,
        samples: List[PowerSample],
        flags: int,
        test_name: Optional[str] = None,
    ) -> bool:
        """Append multiple power samples in a batch (more efficient).

        Args:
            filename: Power trace filename.
            samples: List of PowerSample objects.
            flags: Channel flags (must match header).
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        if not samples:
            return True

        # Build all samples into a single buffer
        parts = []
        for sample in samples:
            parts.append(struct.pack("<I", sample.timestamp_offset_us))

            if flags & POWER_FLAG_HAS_CH0:
                v = sample.ch0_voltage_mv or 0
                i = sample.ch0_current_ua or 0
                parts.append(struct.pack("<Hh", v, i))

            if flags & POWER_FLAG_HAS_CH1:
                v = sample.ch1_voltage_mv or 0
                i = sample.ch1_current_ua or 0
                parts.append(struct.pack("<Hh", v, i))

            if flags & POWER_FLAG_HAS_JOULESCOPE:
                i = sample.js_current_na or 0
                v = sample.js_voltage_mv or 0
                parts.append(struct.pack("<iH", i, v))

        data = b"".join(parts)
        object_name = self._object_path(filename, test_name)
        return self._append_to_object(object_name, data)

    # ── Raw file operations ──────────────────────────────────

    def write_file(
        self,
        filename: str,
        content: bytes,
        test_name: Optional[str] = None,
    ) -> bool:
        """Write a complete file (overwrites existing).

        Use for small files like JSON reports, screenshots, etc.

        Args:
            filename: Artifact filename.
            content: File content as bytes.
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        object_name = self._object_path(filename, test_name)
        success = self._write_object(object_name, content)
        if success:
            self._add_artifact_to_manifest(test_name, filename)
            self._notify_chunk(object_name, 0, len(content))

            # Update in-memory buffer
            with self._lock:
                self._buffers[object_name] = content
                self._offsets[object_name] = len(content)

        return success

    def write_json(
        self,
        filename: str,
        data: Any,
        test_name: Optional[str] = None,
    ) -> bool:
        """Write JSON data to a file.

        Args:
            filename: Artifact filename (should end with .json).
            data: JSON-serializable data.
            test_name: Override current test context.

        Returns:
            True if write succeeded.
        """
        content = json.dumps(data, indent=2, default=str).encode("utf-8")
        return self.write_file(filename, content, test_name)

    # ── Utilities ────────────────────────────────────────────

    def flush(self) -> None:
        """Flush all pending buffers to MinIO.

        In the current implementation, writes are immediate, so this is a no-op.
        Reserved for future batching optimizations.
        """
        pass

    def get_artifact_url(self, filename: str, test_name: Optional[str] = None) -> Optional[str]:
        """Get a presigned URL for downloading an artifact.

        Args:
            filename: Artifact filename.
            test_name: Override current test context.

        Returns:
            Presigned URL valid for 1 hour, or None if not available.
        """
        if not self.enabled:
            return None

        try:
            from datetime import timedelta
            client = self._get_client()
            object_name = self._object_path(filename, test_name)
            return client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(hours=1),
            )
        except Exception as e:
            log.warning("Failed to get presigned URL for %s: %s", filename, e)
            return None

    @property
    def current_test(self) -> Optional[str]:
        """Get the current test name context."""
        return self._current_test
