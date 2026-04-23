"""Unit tests for ArtifactWriter."""

import json
import struct
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from corekinect.test import artifact_writer as aw
from corekinect.test.artifact_writer import (
    ArtifactWriter,
    PowerSample,
    ArtifactInfo,
    POWER_FLAG_HAS_CH0,
    POWER_FLAG_HAS_CH1,
    POWER_FLAG_HAS_JOULESCOPE,
    POWER_HEADER_SIZE,
    POWER_MAGIC,
    _build_minio_http_client,
)


class TestPowerFormat:
    """Test binary power trace format."""

    def test_header_size_constant(self):
        """Test header size constant."""
        assert POWER_HEADER_SIZE == 32

    def test_magic_value(self):
        """Test magic value."""
        assert POWER_MAGIC == b"CKPWR001"
        assert len(POWER_MAGIC) == 8

    def test_header_packing(self):
        """Verify header packs to exactly 32 bytes."""
        flags = POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1
        sample_rate_hz = 1000
        start_timestamp_us = 1709971200000000

        header = struct.pack(
            "<8sIIQ8x",
            POWER_MAGIC,
            flags,
            sample_rate_hz,
            start_timestamp_us,
        )

        assert len(header) == POWER_HEADER_SIZE

    def test_header_unpacking(self):
        """Verify header can be parsed back."""
        flags = 0x03
        sample_rate_hz = 2000
        start_timestamp_us = 1709971200123456

        header = struct.pack(
            "<8sIIQ8x",
            POWER_MAGIC,
            flags,
            sample_rate_hz,
            start_timestamp_us,
        )

        magic, f, rate, ts = struct.unpack("<8sIIQ", header[:24])
        assert magic == POWER_MAGIC
        assert f == flags
        assert rate == sample_rate_hz
        assert ts == start_timestamp_us

    def test_sample_ch0_only(self):
        """Sample with only ch0 data."""
        sample = PowerSample(
            timestamp_offset_us=1000,
            ch0_voltage_mv=4500,
            ch0_current_ua=15000,
        )

        flags = POWER_FLAG_HAS_CH0
        parts = [struct.pack("<I", sample.timestamp_offset_us)]
        parts.append(struct.pack("<Hh", sample.ch0_voltage_mv, sample.ch0_current_ua))
        data = b"".join(parts)

        assert len(data) == 8  # 4 (timestamp) + 4 (ch0)

        ts_off, v, i = struct.unpack("<IHh", data)
        assert ts_off == 1000
        assert v == 4500
        assert i == 15000

    def test_sample_ch0_ch1(self):
        """Sample with ch0 and ch1 data."""
        sample = PowerSample(
            timestamp_offset_us=2000,
            ch0_voltage_mv=4500,
            ch0_current_ua=15000,
            ch1_voltage_mv=5000,
            ch1_current_ua=-500,  # Negative current (charging battery)
        )

        flags = POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1
        parts = [struct.pack("<I", sample.timestamp_offset_us)]
        parts.append(struct.pack("<Hh", sample.ch0_voltage_mv, sample.ch0_current_ua))
        parts.append(struct.pack("<Hh", sample.ch1_voltage_mv, sample.ch1_current_ua))
        data = b"".join(parts)

        assert len(data) == 12  # 4 + 4 + 4

    def test_sample_joulescope_only(self):
        """Sample with only Joulescope data."""
        sample = PowerSample(
            timestamp_offset_us=5000,
            js_current_na=-123456789,
            js_voltage_mv=3300,
        )

        flags = POWER_FLAG_HAS_JOULESCOPE
        parts = [struct.pack("<I", sample.timestamp_offset_us)]
        parts.append(struct.pack("<iH", sample.js_current_na, sample.js_voltage_mv))
        data = b"".join(parts)

        assert len(data) == 10  # 4 + 6

        ts_off, i, v = struct.unpack("<IiH", data)
        assert ts_off == 5000
        assert i == -123456789
        assert v == 3300

    def test_sample_all_channels(self):
        """Sample with all channels."""
        sample = PowerSample(
            timestamp_offset_us=10000,
            ch0_voltage_mv=4500,
            ch0_current_ua=15000,
            ch1_voltage_mv=5000,
            ch1_current_ua=2000,
            js_current_na=50000000,
            js_voltage_mv=3300,
        )

        flags = POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1 | POWER_FLAG_HAS_JOULESCOPE
        parts = [struct.pack("<I", sample.timestamp_offset_us)]
        parts.append(struct.pack("<Hh", sample.ch0_voltage_mv, sample.ch0_current_ua))
        parts.append(struct.pack("<Hh", sample.ch1_voltage_mv, sample.ch1_current_ua))
        parts.append(struct.pack("<iH", sample.js_current_na, sample.js_voltage_mv))
        data = b"".join(parts)

        assert len(data) == 18  # 4 + 4 + 4 + 6


class TestUartFormat:
    """Test UART log format."""

    def test_uart_line_format(self):
        """UART lines should have POSIX timestamp prefix."""
        posix_ts = 1709971200123456
        line = "[00:00:00.123,456] <inf> main: Hello world"
        formatted = f"[{posix_ts}] {line}\n"

        assert formatted.startswith("[1709971200123456]")
        assert formatted.endswith("\n")
        assert line in formatted

    def test_uart_line_with_newline(self):
        """Lines with newlines should not get double newlines."""
        posix_ts = 1709971200000000
        line = "[00:00:00.000,000] <inf> test\n"
        formatted = f"[{posix_ts}] {line}"
        if not formatted.endswith("\n"):
            formatted += "\n"

        # Should still only have one trailing newline
        assert formatted.count("\n") == 1  # Line already had newline, no extra added


class TestManifestFormat:
    """Test manifest JSON structure."""

    def test_manifest_structure(self):
        """Manifest should have required fields."""
        manifest = {
            "runId": "abc123",
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "tests": [],
        }

        assert "runId" in manifest
        assert "startedAt" in manifest
        assert "tests" in manifest
        assert isinstance(manifest["tests"], list)

    def test_test_artifact_info(self):
        """ArtifactInfo dataclass should serialize correctly."""
        info = ArtifactInfo(
            name="test_boot",
            status="passed",
            started_at="2026-03-09T10:00:00Z",
            finished_at="2026-03-09T10:00:05Z",
            artifacts=["output.log", "uart_app.log"],
        )

        assert info.name == "test_boot"
        assert info.status == "passed"
        assert len(info.artifacts) == 2

    def test_manifest_with_tests(self):
        """Manifest with test entries."""
        manifest = {
            "runId": "abc123",
            "startedAt": "2026-03-09T10:00:00Z",
            "tests": [
                {
                    "name": "test_boot",
                    "status": "passed",
                    "startedAt": "2026-03-09T10:00:00Z",
                    "finishedAt": "2026-03-09T10:00:05Z",
                    "artifacts": ["output.log", "uart_app.log"],
                }
            ],
        }

        assert len(manifest["tests"]) == 1
        assert manifest["tests"][0]["name"] == "test_boot"
        assert "output.log" in manifest["tests"][0]["artifacts"]


class TestArtifactWriterInit:
    """Test ArtifactWriter initialization."""

    def test_disabled_when_no_storage_url(self):
        """Writer should be disabled when STORAGE_URL is not set."""
        with patch.dict("os.environ", {}, clear=True):
            writer = ArtifactWriter()
            assert not writer.enabled

    def test_disabled_when_no_run_id(self):
        """Writer should be disabled when CONCORD_RUN_ID is not set."""
        with patch.dict("os.environ", {"STORAGE_URL": "http://minio:9000"}, clear=True):
            writer = ArtifactWriter()
            assert not writer.enabled

    def test_disabled_when_minio_not_installed(self):
        """Writer should be disabled when minio is not installed."""
        with patch.dict(
            "os.environ",
            {"STORAGE_URL": "http://minio:9000", "CONCORD_RUN_ID": "test123"},
            clear=True,
        ):
            with patch("corekinect.test.artifact_writer._HAS_MINIO", False):
                writer = ArtifactWriter()
                assert not writer.enabled

    def test_object_path_with_test(self):
        """Object path should include test name when in test context."""
        writer = ArtifactWriter()
        writer.run_id = "run123"
        writer._current_test = "test_boot"

        path = writer._object_path("output.log")
        assert path == "sessions/run123/test_boot/output.log"

    def test_object_path_without_test(self):
        """Object path should be session-level when no test context."""
        writer = ArtifactWriter()
        writer.run_id = "run123"
        writer._current_test = None

        path = writer._object_path("manifest.json")
        assert path == "sessions/run123/manifest.json"

    def test_object_path_override_test(self):
        """Object path should use override test name."""
        writer = ArtifactWriter()
        writer.run_id = "run123"
        writer._current_test = "test_boot"

        path = writer._object_path("output.log", test_name="test_power")
        assert path == "sessions/run123/test_power/output.log"


class TestArtifactWriterTestLifecycle:
    """Test test lifecycle methods."""

    def test_start_test_sets_current(self):
        """start_test should set current test context."""
        writer = ArtifactWriter()
        writer.start_test("test_boot")

        assert writer._current_test == "test_boot"
        assert "test_boot" in writer._test_index

    def test_finish_test_clears_current(self):
        """finish_test should clear current test context."""
        writer = ArtifactWriter()
        writer.start_test("test_boot")
        writer.finish_test("test_boot", status="passed")

        assert writer._current_test is None

    def test_manifest_tracks_tests(self):
        """Manifest should track test lifecycle."""
        writer = ArtifactWriter()
        writer.start_test("test_boot")

        assert len(writer._manifest["tests"]) == 1
        assert writer._manifest["tests"][0]["name"] == "test_boot"
        assert writer._manifest["tests"][0]["status"] == "running"

        writer.finish_test("test_boot", status="passed")

        assert writer._manifest["tests"][0]["status"] == "passed"
        assert writer._manifest["tests"][0]["finishedAt"] is not None


class TestPowerSampleDataclass:
    """Test PowerSample dataclass."""

    def test_minimal_sample(self):
        """PowerSample with only timestamp."""
        sample = PowerSample(timestamp_offset_us=1000)
        assert sample.timestamp_offset_us == 1000
        assert sample.ch0_voltage_mv is None

    def test_ch0_sample(self):
        """PowerSample with ch0 data."""
        sample = PowerSample(
            timestamp_offset_us=1000,
            ch0_voltage_mv=4500,
            ch0_current_ua=15000,
        )
        assert sample.ch0_voltage_mv == 4500
        assert sample.ch0_current_ua == 15000

    def test_negative_current(self):
        """PowerSample can have negative current."""
        sample = PowerSample(
            timestamp_offset_us=1000,
            ch1_current_ua=-500,  # Battery charging
        )
        assert sample.ch1_current_ua == -500

    def test_joulescope_sample(self):
        """PowerSample with Joulescope data."""
        sample = PowerSample(
            timestamp_offset_us=1000,
            js_current_na=50000000,  # 50mA in nA
            js_voltage_mv=3300,
        )
        assert sample.js_current_na == 50000000
        assert sample.js_voltage_mv == 3300


class TestMinioClientTimeouts:
    """Regression tests for the MinIO client timeout contract.

    When the MinIO Python SDK is constructed without ``http_client=``,
    connect() blocks indefinitely on a dropped packet. That deadlocks
    every parallel slot's teardown under an outage / misconfigured
    NetworkPolicy and masks the root cause behind a generic pytest
    timeout. ``ArtifactWriter`` must always build a bounded PoolManager.
    """

    def test_pool_manager_is_bounded(self):
        """The shared builder returns a PoolManager with a finite timeout."""
        pool = _build_minio_http_client()
        assert pool is not None, "urllib3 must be available at runtime"

        # Underlying connection_pool_kw carries the Timeout the PoolManager
        # will pass to each new pool. Assert both connect + read are bounded.
        timeout = pool.connection_pool_kw.get("timeout")
        assert timeout is not None, "PoolManager must carry a Timeout"
        assert timeout.connect_timeout is not None and timeout.connect_timeout <= 10, (
            f"connect timeout must be ≤10s (was {timeout.connect_timeout})"
        )
        assert timeout.read_timeout is not None and timeout.read_timeout <= 30, (
            f"read timeout must be ≤30s (was {timeout.read_timeout})"
        )

    def test_writer_wires_bounded_client_into_minio(self):
        """ArtifactWriter._get_client() passes the bounded PoolManager to Minio()."""
        captured = {}

        class _FakeMinio:
            def __init__(self, *args, **kwargs):
                captured["kwargs"] = kwargs

        with patch.object(aw, "Minio", _FakeMinio), \
             patch.object(aw, "_HAS_MINIO", True), \
             patch.dict("os.environ", {
                 "STORAGE_URL": "http://concord-minio.production.svc.cluster.local:9000",
                 "STORAGE_ACCESS_KEY": "test",
                 "STORAGE_SECRET_ACCESS_KEY": "test",
                 "CONCORD_RUN_ID": "run-timeout-test",
             }):
            writer = aw.ArtifactWriter()
            # Force client construction.
            writer._get_client()

        http_client = captured["kwargs"].get("http_client")
        assert http_client is not None, (
            "Minio() must be called with http_client= so connect() is bounded"
        )
        timeout = http_client.connection_pool_kw.get("timeout")
        assert timeout.connect_timeout is not None and timeout.connect_timeout <= 10
        assert timeout.read_timeout is not None and timeout.read_timeout <= 30
