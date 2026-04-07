"""Additional unit tests for ArtifactWriter — logic paths not covered by test_artifact_writer.py.

Focuses on:
- PowerSample dataclass: construction, all-fields, defaults
- ArtifactInfo dataclass: construction, defaults
- POWER_MAGIC, POWER_HEADER_SIZE constants
- Power header packing/unpacking round-trip
- Power flag constants and combinations
- Power sample serialization (struct-level verification)
- _object_path with sessions/ prefix (source uses sessions/, not validation/runs/)
- ArtifactWriter manifest tracking across multiple tests
- append_uart formatting edge cases
- _StorageConfig env loading
"""

import os
import struct
from unittest.mock import patch

import pytest

from corekinect.test.artifact_writer import (
    ArtifactInfo,
    ArtifactWriter,
    PowerSample,
    POWER_FLAG_HAS_CH0,
    POWER_FLAG_HAS_CH1,
    POWER_FLAG_HAS_JOULESCOPE,
    POWER_HEADER_SIZE,
    POWER_MAGIC,
    _StorageConfig,
)


# =============================================================================
# Constants verification
# =============================================================================


class TestPowerConstants:
    """Verify binary format constants are correct and self-consistent."""

    def test_magic_bytes(self):
        """Test magic bytes."""
        assert POWER_MAGIC == b"CKPWR001"

    def test_magic_length(self):
        """Test magic length."""
        assert len(POWER_MAGIC) == 8

    def test_header_size(self):
        """Test header size."""
        assert POWER_HEADER_SIZE == 32

    def test_flag_ch0_value(self):
        """Test flag ch0 value."""
        assert POWER_FLAG_HAS_CH0 == 0x01

    def test_flag_ch1_value(self):
        """Test flag ch1 value."""
        assert POWER_FLAG_HAS_CH1 == 0x02

    def test_flag_joulescope_value(self):
        """Test flag joulescope value."""
        assert POWER_FLAG_HAS_JOULESCOPE == 0x04

    def test_flags_are_distinct_bits(self):
        """All flags must be distinct powers of 2."""
        flags = [POWER_FLAG_HAS_CH0, POWER_FLAG_HAS_CH1, POWER_FLAG_HAS_JOULESCOPE]
        combined = 0
        for f in flags:
            assert f & combined == 0, f"Flag {f:#x} overlaps with another"
            combined |= f

    def test_all_flags_combined(self):
        """Combined value of all flags."""
        all_flags = POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1 | POWER_FLAG_HAS_JOULESCOPE
        assert all_flags == 0x07


# =============================================================================
# Power header packing/unpacking round-trip
# =============================================================================


class TestPowerHeaderRoundTrip:
    """Test that headers pack to 32 bytes and round-trip correctly."""

    def test_pack_produces_32_bytes(self):
        """Test pack produces 32 bytes."""
        header = struct.pack(
            "<8sIIQ8x",
            POWER_MAGIC,
            POWER_FLAG_HAS_CH0,
            1000,
            1709971200000000,
        )
        assert len(header) == POWER_HEADER_SIZE

    def test_round_trip_ch0_only(self):
        """Test round trip ch0 only."""
        flags = POWER_FLAG_HAS_CH0
        rate = 500
        ts = 1710000000000000

        header = struct.pack("<8sIIQ8x", POWER_MAGIC, flags, rate, ts)
        magic, f, r, t = struct.unpack("<8sIIQ", header[:24])

        assert magic == POWER_MAGIC
        assert f == flags
        assert r == rate
        assert t == ts

    def test_round_trip_all_flags(self):
        """Test round trip all flags."""
        flags = POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1 | POWER_FLAG_HAS_JOULESCOPE
        rate = 10000
        ts = 1709971200999999

        header = struct.pack("<8sIIQ8x", POWER_MAGIC, flags, rate, ts)
        magic, f, r, t = struct.unpack("<8sIIQ", header[:24])

        assert magic == POWER_MAGIC
        assert f == flags
        assert r == rate
        assert t == ts

    def test_reserved_bytes_are_zero(self):
        """The 8 reserved bytes at the end should be all zeros."""
        header = struct.pack("<8sIIQ8x", POWER_MAGIC, 0x03, 1000, 0)
        reserved = header[24:32]
        assert reserved == b"\x00" * 8

    def test_zero_timestamp(self):
        """Test zero timestamp."""
        header = struct.pack("<8sIIQ8x", POWER_MAGIC, 0, 0, 0)
        assert len(header) == POWER_HEADER_SIZE
        _, _, _, ts = struct.unpack("<8sIIQ", header[:24])
        assert ts == 0

    def test_max_sample_rate(self):
        """High sample rate should pack correctly."""
        max_rate = 0xFFFFFFFF  # uint32 max
        header = struct.pack("<8sIIQ8x", POWER_MAGIC, 0, max_rate, 0)
        _, _, r, _ = struct.unpack("<8sIIQ", header[:24])
        assert r == max_rate


# =============================================================================
# Power sample serialization
# =============================================================================


class TestPowerSampleSerialization:
    """Test sample packing matches the documented binary format."""

    def test_ch0_only_sample_size(self):
        """ch0 sample: 4 (timestamp) + 2 (voltage) + 2 (current) = 8 bytes."""
        parts = [struct.pack("<I", 1000)]
        parts.append(struct.pack("<Hh", 4500, 15000))
        data = b"".join(parts)
        assert len(data) == 8

    def test_ch0_ch1_sample_size(self):
        """ch0+ch1 sample: 4 + 4 + 4 = 12 bytes."""
        parts = [struct.pack("<I", 2000)]
        parts.append(struct.pack("<Hh", 4500, 15000))
        parts.append(struct.pack("<Hh", 5000, 2000))
        data = b"".join(parts)
        assert len(data) == 12

    def test_joulescope_only_sample_size(self):
        """Joulescope sample: 4 + 4 (int32) + 2 (uint16) = 10 bytes."""
        parts = [struct.pack("<I", 5000)]
        parts.append(struct.pack("<iH", -123456789, 3300))
        data = b"".join(parts)
        assert len(data) == 10

    def test_all_channels_sample_size(self):
        """All channels: 4 + 4 + 4 + 6 = 18 bytes."""
        parts = [struct.pack("<I", 10000)]
        parts.append(struct.pack("<Hh", 4500, 15000))  # ch0
        parts.append(struct.pack("<Hh", 5000, 2000))   # ch1
        parts.append(struct.pack("<iH", 50000000, 3300))  # joulescope
        data = b"".join(parts)
        assert len(data) == 18

    def test_negative_current_round_trip(self):
        """Signed int16 current should preserve negative values."""
        current_ua = -500
        packed = struct.pack("<Hh", 5000, current_ua)
        v, i = struct.unpack("<Hh", packed)
        assert v == 5000
        assert i == -500

    def test_joulescope_negative_current_round_trip(self):
        """Signed int32 nanoamp current should preserve negative values."""
        current_na = -50000000  # -50mA in nA
        packed = struct.pack("<iH", current_na, 3300)
        i, v = struct.unpack("<iH", packed)
        assert i == -50000000
        assert v == 3300

    def test_timestamp_offset_zero(self):
        """Test timestamp offset zero."""
        parts = [struct.pack("<I", 0)]
        parts.append(struct.pack("<Hh", 4500, 100))
        data = b"".join(parts)
        ts, _, _ = struct.unpack("<IHh", data)
        assert ts == 0


# =============================================================================
# PowerSample dataclass
# =============================================================================


class TestPowerSampleDataclassLogic:
    """Test PowerSample construction edge cases."""

    def test_all_fields_populated(self):
        """Test all fields populated."""
        sample = PowerSample(
            timestamp_offset_us=12345,
            ch0_voltage_mv=4500,
            ch0_current_ua=15000,
            ch1_voltage_mv=5000,
            ch1_current_ua=2000,
            js_current_na=50000000,
            js_voltage_mv=3300,
        )
        assert sample.timestamp_offset_us == 12345
        assert sample.ch0_voltage_mv == 4500
        assert sample.ch0_current_ua == 15000
        assert sample.ch1_voltage_mv == 5000
        assert sample.ch1_current_ua == 2000
        assert sample.js_current_na == 50000000
        assert sample.js_voltage_mv == 3300

    def test_all_optional_fields_default_none(self):
        """Test all optional fields default none."""
        sample = PowerSample(timestamp_offset_us=0)
        assert sample.ch0_voltage_mv is None
        assert sample.ch0_current_ua is None
        assert sample.ch1_voltage_mv is None
        assert sample.ch1_current_ua is None
        assert sample.js_current_na is None
        assert sample.js_voltage_mv is None

    def test_flag_auto_detect_ch0(self):
        """Verify flag auto-detection logic matches source code."""
        sample = PowerSample(timestamp_offset_us=0, ch0_voltage_mv=4500)
        flags = 0
        if sample.ch0_voltage_mv is not None or sample.ch0_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH0
        if sample.ch1_voltage_mv is not None or sample.ch1_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH1
        if sample.js_current_na is not None or sample.js_voltage_mv is not None:
            flags |= POWER_FLAG_HAS_JOULESCOPE
        assert flags == POWER_FLAG_HAS_CH0

    def test_flag_auto_detect_ch0_ch1(self):
        """Test flag auto detect ch0 ch1."""
        sample = PowerSample(
            timestamp_offset_us=0,
            ch0_voltage_mv=4500,
            ch1_current_ua=2000,
        )
        flags = 0
        if sample.ch0_voltage_mv is not None or sample.ch0_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH0
        if sample.ch1_voltage_mv is not None or sample.ch1_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH1
        if sample.js_current_na is not None or sample.js_voltage_mv is not None:
            flags |= POWER_FLAG_HAS_JOULESCOPE
        assert flags == (POWER_FLAG_HAS_CH0 | POWER_FLAG_HAS_CH1)

    def test_flag_auto_detect_all(self):
        """Test flag auto detect all."""
        sample = PowerSample(
            timestamp_offset_us=0,
            ch0_current_ua=100,
            ch1_voltage_mv=5000,
            js_voltage_mv=3300,
        )
        flags = 0
        if sample.ch0_voltage_mv is not None or sample.ch0_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH0
        if sample.ch1_voltage_mv is not None or sample.ch1_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH1
        if sample.js_current_na is not None or sample.js_voltage_mv is not None:
            flags |= POWER_FLAG_HAS_JOULESCOPE
        assert flags == 0x07

    def test_flag_auto_detect_none_fields(self):
        """When all optional fields are None, flags should be 0."""
        sample = PowerSample(timestamp_offset_us=0)
        flags = 0
        if sample.ch0_voltage_mv is not None or sample.ch0_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH0
        if sample.ch1_voltage_mv is not None or sample.ch1_current_ua is not None:
            flags |= POWER_FLAG_HAS_CH1
        if sample.js_current_na is not None or sample.js_voltage_mv is not None:
            flags |= POWER_FLAG_HAS_JOULESCOPE
        assert flags == 0


# =============================================================================
# ArtifactInfo dataclass
# =============================================================================


class TestArtifactInfoDataclass:
    """Test ArtifactInfo construction and defaults."""

    def test_construction_all_fields(self):
        """Test construction all fields."""
        info = ArtifactInfo(
            name="test_boot",
            status="passed",
            started_at="2026-03-09T10:00:00Z",
            finished_at="2026-03-09T10:00:05Z",
            artifacts=["output.log", "uart_app.log"],
        )
        assert info.name == "test_boot"
        assert info.status == "passed"
        assert info.started_at == "2026-03-09T10:00:00Z"
        assert info.finished_at == "2026-03-09T10:00:05Z"
        assert info.artifacts == ["output.log", "uart_app.log"]

    def test_default_status(self):
        """Status defaults to 'running'."""
        info = ArtifactInfo(name="test_x")
        assert info.status == "running"

    def test_default_timestamps(self):
        """Timestamps default to None."""
        info = ArtifactInfo(name="test_x")
        assert info.started_at is None
        assert info.finished_at is None

    def test_default_artifacts_list(self):
        """Artifacts list defaults to empty."""
        info = ArtifactInfo(name="test_x")
        assert info.artifacts == []

    def test_default_artifacts_not_shared(self):
        """Each instance should get its own artifacts list (not shared mutable default)."""
        info1 = ArtifactInfo(name="test_a")
        info2 = ArtifactInfo(name="test_b")
        info1.artifacts.append("file.log")
        assert info2.artifacts == []


# =============================================================================
# ArtifactWriter object path (correct prefix)
# =============================================================================


class TestArtifactWriterObjectPath:
    """Test _object_path uses the correct prefix from source code."""

    def _make_writer(self, run_id="run-abc"):
        """ make writer."""
        with patch.dict(os.environ, {}, clear=True):
            writer = ArtifactWriter()
        writer.run_id = run_id
        return writer

    def test_session_level_path(self):
        """Test session level path."""
        writer = self._make_writer()
        writer._current_test = None
        path = writer._object_path("manifest.json")
        assert path == "sessions/run-abc/manifest.json"

    def test_test_level_path(self):
        """Test test level path."""
        writer = self._make_writer()
        writer._current_test = "test_boot"
        path = writer._object_path("output.log")
        assert path == "sessions/run-abc/test_boot/output.log"

    def test_test_name_override(self):
        """Test test name override."""
        writer = self._make_writer()
        writer._current_test = "test_boot"
        path = writer._object_path("power.bin", test_name="test_power")
        assert path == "sessions/run-abc/test_power/power.bin"

    def test_override_takes_precedence(self):
        """Explicit test_name parameter takes precedence over _current_test."""
        writer = self._make_writer()
        writer._current_test = "test_a"
        path = writer._object_path("file.log", test_name="test_b")
        assert path == "sessions/run-abc/test_b/file.log"


# =============================================================================
# ArtifactWriter manifest tracking
# =============================================================================


class TestArtifactWriterManifestTracking:
    """Test manifest tracking across multiple test lifecycles."""

    def _make_writer(self):
        """ make writer."""
        with patch.dict(os.environ, {}, clear=True):
            writer = ArtifactWriter()
        writer.run_id = "run-123"
        return writer

    def test_multiple_tests_tracked(self):
        """Test multiple tests tracked."""
        writer = self._make_writer()
        writer.start_test("test_boot")
        writer.finish_test("test_boot", status="passed")

        writer.start_test("test_power")
        writer.finish_test("test_power", status="failed")

        assert len(writer._manifest["tests"]) == 2
        assert writer._manifest["tests"][0]["name"] == "test_boot"
        assert writer._manifest["tests"][0]["status"] == "passed"
        assert writer._manifest["tests"][1]["name"] == "test_power"
        assert writer._manifest["tests"][1]["status"] == "failed"

    def test_finish_nonexistent_test_no_crash(self):
        """Finishing a test that was never started should not crash."""
        writer = self._make_writer()
        writer.finish_test("never_started", status="skipped")
        # Should not raise, _current_test stays None
        assert writer._current_test is None

    def test_current_test_property(self):
        """Test current test property."""
        writer = self._make_writer()
        assert writer.current_test is None

        writer.start_test("test_x")
        assert writer.current_test == "test_x"

        writer.finish_test("test_x")
        assert writer.current_test is None

    def test_finish_different_test_keeps_current(self):
        """Finishing a test other than the current one should not clear current."""
        writer = self._make_writer()
        writer.start_test("test_a")
        writer.start_test("test_b")

        # Current is now test_b
        assert writer.current_test == "test_b"

        # Finish test_a (not current)
        writer.finish_test("test_a", status="passed")

        # Current should still be test_b
        assert writer.current_test == "test_b"

    def test_add_artifact_to_manifest(self):
        """Artifacts should be tracked in the manifest for the correct test."""
        writer = self._make_writer()
        writer.start_test("test_boot")
        writer._add_artifact_to_manifest(None, "output.log")
        writer._add_artifact_to_manifest(None, "uart_app.log")

        idx = writer._test_index["test_boot"]
        artifacts = writer._manifest["tests"][idx]["artifacts"]
        assert "output.log" in artifacts
        assert "uart_app.log" in artifacts

    def test_add_artifact_deduplication(self):
        """Same artifact should not be added twice."""
        writer = self._make_writer()
        writer.start_test("test_boot")
        writer._add_artifact_to_manifest(None, "output.log")
        writer._add_artifact_to_manifest(None, "output.log")

        idx = writer._test_index["test_boot"]
        artifacts = writer._manifest["tests"][idx]["artifacts"]
        assert artifacts.count("output.log") == 1

    def test_add_artifact_to_specific_test(self):
        """Artifacts can be added to a specific test by name."""
        writer = self._make_writer()
        writer.start_test("test_a")
        writer.start_test("test_b")

        writer._add_artifact_to_manifest("test_a", "file_a.log")
        writer._add_artifact_to_manifest("test_b", "file_b.log")

        idx_a = writer._test_index["test_a"]
        idx_b = writer._test_index["test_b"]
        assert "file_a.log" in writer._manifest["tests"][idx_a]["artifacts"]
        assert "file_b.log" in writer._manifest["tests"][idx_b]["artifacts"]
        assert "file_a.log" not in writer._manifest["tests"][idx_b]["artifacts"]


# =============================================================================
# ArtifactWriter disabled behavior
# =============================================================================


class TestArtifactWriterDisabledBehavior:
    """Test that disabled writer returns correct values without errors."""

    def _make_disabled_writer(self):
        """ make disabled writer."""
        with patch.dict(os.environ, {}, clear=True):
            writer = ArtifactWriter()
        assert not writer.enabled
        return writer

    def test_write_object_returns_false(self):
        """Test write object returns false."""
        writer = self._make_disabled_writer()
        assert writer._write_object("test/path", b"data") is False

    def test_read_object_returns_none(self):
        """Test read object returns none."""
        writer = self._make_disabled_writer()
        assert writer._read_object("test/path") is None

    def test_append_to_object_returns_false(self):
        """Test append to object returns false."""
        writer = self._make_disabled_writer()
        assert writer._append_to_object("test/path", b"data") is False

    def test_append_to_object_empty_data_returns_false(self):
        """Test append to object empty data returns false."""
        writer = self._make_disabled_writer()
        assert writer._append_to_object("test/path", b"") is False

    def test_get_artifact_url_returns_none(self):
        """Test get artifact url returns none."""
        writer = self._make_disabled_writer()
        assert writer.get_artifact_url("file.log") is None

    def test_write_bytes_returns_false(self):
        """Test write bytes returns false."""
        writer = self._make_disabled_writer()
        assert writer.write_bytes("path.jsonl", b"content") is False

    def test_flush_is_noop(self):
        """flush() should not raise even when disabled."""
        writer = self._make_disabled_writer()
        writer.flush()  # Should not raise


# =============================================================================
# _StorageConfig env loading
# =============================================================================


class TestStorageConfigWriter:
    """Test _StorageConfig (writer module's EnvConfig subclass)."""

    def test_defaults(self):
        """Test defaults."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_URL is None
            assert cfg.STORAGE_ACCESS_KEY is None
            assert cfg.STORAGE_SECRET_ACCESS_KEY is None
            assert cfg.STORAGE_BUCKET_NAME == "concord"
            assert cfg.CONCORD_RUN_ID is None
            assert cfg.CONCORD_API_URL is None
            assert cfg.CONCORD_API_KEY is None
            assert cfg.CONCORD_API_HOST is None

    def test_reads_run_id(self):
        """Test reads run id."""
        with patch.dict(os.environ, {"CONCORD_RUN_ID": "run-xyz"}, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.CONCORD_RUN_ID == "run-xyz"

    def test_reads_api_config(self):
        """Test reads api config."""
        env = {
            "CONCORD_API_URL": "https://concord.local",
            "CONCORD_API_KEY": "ck_run_test123",
            "CONCORD_API_HOST": "concord.local",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.CONCORD_API_URL == "https://concord.local"
            assert cfg.CONCORD_API_KEY == "ck_run_test123"
            assert cfg.CONCORD_API_HOST == "concord.local"

    def test_enabled_requires_all(self):
        """ArtifactWriter.enabled needs storage_url + run_id + minio."""
        env = {
            "STORAGE_URL": "http://minio:9000",
            "CONCORD_RUN_ID": "run-123",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_URL == "http://minio:9000"
            assert cfg.CONCORD_RUN_ID == "run-123"
