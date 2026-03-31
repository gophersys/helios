"""Tests for CFW (CoreKinect Firmware) binary header parsing.

Tests parse_cfw_header() from corekinect.test.cfw with synthetic
CFW files containing known header values.
"""

import struct
import tempfile
from pathlib import Path

import pytest

from corekinect.test.cfw import parse_cfw_header, RELEASE_TRACKS

# Header format: big-endian >HQHBHHHi (23 bytes total)
# FileVersion(2) + TimeCreated(8) + AppId(2) + Flags(1) + Major(2) + Minor(2) + Build(2) + ImageLen(4)
HEADER_FORMAT = ">HQHBHHHi"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def _make_cfw(
    file_version: int = 2,
    time_created: int = 1700000000,
    app_id: int = 108,
    flags: int = 0x01,
    major: int = 0,
    minor: int = 5,
    build: int = 2,
    image_len: int = 65536,
    payload: bytes = b"",
) -> bytes:
    """Build a synthetic CFW binary with the given header fields."""
    header = struct.pack(
        HEADER_FORMAT,
        file_version,
        time_created,
        app_id,
        flags,
        major,
        minor,
        build,
        image_len,
    )
    return header + payload


def _write_cfw(tmp_path: Path, data: bytes, name: str = "test.cfw") -> Path:
    """Write CFW bytes to a file and return the path."""
    cfw_path = tmp_path / name
    cfw_path.write_bytes(data)
    return cfw_path


class TestReleaseTracksConstant:
    """Tests for the RELEASE_TRACKS mapping."""

    def test_has_bench(self):
        assert RELEASE_TRACKS[0] == "B"

    def test_has_engineering(self):
        assert RELEASE_TRACKS[1] == "E"

    def test_has_production(self):
        assert RELEASE_TRACKS[2] == "P"

    def test_has_exactly_three_entries(self):
        assert len(RELEASE_TRACKS) == 3


class TestHeaderSize:
    """Verify header struct is 23 bytes as documented."""

    def test_header_is_23_bytes(self):
        assert HEADER_SIZE == 23


class TestParseValidHeader:
    """Tests parsing a valid CFW header."""

    def test_basic_bench_mfg_header(self, tmp_path):
        """Parse a Bench+Mfg CFW (flags=0x01: bit0=Mfg, track=Bench)."""
        data = _make_cfw(app_id=108, flags=0x01, major=0, minor=5, build=2)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["app_id"] == 108
        assert result["major"] == 0
        assert result["minor"] == 5
        assert result["build"] == 2
        assert result["track"] == "B"
        assert result["is_mfg"] is True
        assert result["is_debug"] is False
        assert result["target_string"] == "108.0.5.2-BM"
        assert result["version_string"] == "0.5.2"

    def test_file_version_and_image_len(self, tmp_path):
        """file_version and image_len should be parsed correctly."""
        data = _make_cfw(file_version=3, image_len=131072)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["file_version"] == 3
        assert result["image_len"] == 131072

    def test_flags_field_is_raw(self, tmp_path):
        """The raw flags byte should be returned as-is."""
        data = _make_cfw(flags=0x09)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["flags"] == 0x09

    def test_accepts_string_path(self, tmp_path):
        """parse_cfw_header should accept a string path."""
        data = _make_cfw()
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(str(path))

        assert result["app_id"] == 108

    def test_header_with_payload_data(self, tmp_path):
        """Extra payload bytes after the header should not affect parsing."""
        payload = b"\xff" * 1024
        data = _make_cfw(payload=payload)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["app_id"] == 108
        assert result["version_string"] == "0.5.2"


class TestFlagCombinations:
    """Test all meaningful flag combinations."""

    def test_bench_mfg(self, tmp_path):
        """Flags=0x01: Bench (bits 2:1=0b00) + Mfg (bit 0=1) -> BM."""
        data = _make_cfw(flags=0x01)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "B"
        assert result["is_mfg"] is True
        assert result["is_debug"] is False
        assert result["target_string"].endswith("-BM")

    def test_production_no_mfg(self, tmp_path):
        """Flags=0x04: Production (bits 2:1=0b10) + no Mfg -> P."""
        data = _make_cfw(flags=0x04)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "P"
        assert result["is_mfg"] is False
        assert result["is_debug"] is False
        assert result["target_string"].endswith("-P")

    def test_bench_mfg_debug(self, tmp_path):
        """Flags=0x09: Bench + Mfg + Debug (bit 3=1) -> BMD."""
        data = _make_cfw(flags=0x09)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "B"
        assert result["is_mfg"] is True
        assert result["is_debug"] is True
        assert result["target_string"].endswith("-BMD")

    def test_engineering_no_mfg(self, tmp_path):
        """Flags=0x02: Engineering (bits 2:1=0b01) + no Mfg -> E."""
        data = _make_cfw(flags=0x02)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "E"
        assert result["is_mfg"] is False
        assert result["is_debug"] is False
        assert result["target_string"].endswith("-E")

    def test_engineering_mfg(self, tmp_path):
        """Flags=0x03: Engineering + Mfg -> EM."""
        data = _make_cfw(flags=0x03)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "E"
        assert result["is_mfg"] is True
        assert result["is_debug"] is False
        assert result["target_string"].endswith("-EM")

    def test_production_mfg_debug(self, tmp_path):
        """Flags=0x0D: Production + Mfg + Debug -> PMD."""
        data = _make_cfw(flags=0x0D)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "P"
        assert result["is_mfg"] is True
        assert result["is_debug"] is True
        assert result["target_string"].endswith("-PMD")

    def test_no_flags_at_all(self, tmp_path):
        """Flags=0x00: Bench + no Mfg + no Debug -> B."""
        data = _make_cfw(flags=0x00)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == "B"
        assert result["is_mfg"] is False
        assert result["is_debug"] is False
        assert result["target_string"].endswith("-B")


class TestTrackExtraction:
    """Verify track extraction from bits 2:1 of the flags byte."""

    @pytest.mark.parametrize(
        "flags,expected_track",
        [
            (0x00, "B"),  # bits 2:1 = 0b00
            (0x02, "E"),  # bits 2:1 = 0b01
            (0x04, "P"),  # bits 2:1 = 0b10
            (0x06, "?"),  # bits 2:1 = 0b11 (undefined, should get "?")
        ],
    )
    def test_track_from_flag_bits(self, tmp_path, flags, expected_track):
        data = _make_cfw(flags=flags)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["track"] == expected_track


class TestTargetStringFormat:
    """Verify the target_string and version_string output."""

    def test_target_string_format(self, tmp_path):
        """target_string should be {app_id}.{major}.{minor}.{build}-{suffix}."""
        data = _make_cfw(app_id=109, flags=0x01, major=0, minor=8, build=3)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["target_string"] == "109.0.8.3-BM"

    def test_version_string_format(self, tmp_path):
        """version_string should be {major}.{minor}.{build}."""
        data = _make_cfw(major=1, minor=2, build=3)
        path = _write_cfw(tmp_path, data)
        result = parse_cfw_header(path)

        assert result["version_string"] == "1.2.3"


class TestParseErrors:
    """Tests for error handling on invalid CFW data."""

    def test_short_header_raises(self, tmp_path):
        """A file shorter than 23 bytes should raise ValueError."""
        path = tmp_path / "short.cfw"
        path.write_bytes(b"\x00" * 10)

        with pytest.raises(ValueError, match="header too short"):
            parse_cfw_header(path)

    def test_empty_file_raises(self, tmp_path):
        """An empty file should raise ValueError."""
        path = tmp_path / "empty.cfw"
        path.write_bytes(b"")

        with pytest.raises(ValueError, match="header too short"):
            parse_cfw_header(path)

    def test_22_bytes_raises(self, tmp_path):
        """Exactly 22 bytes (one short) should raise ValueError."""
        path = tmp_path / "almost.cfw"
        path.write_bytes(b"\x00" * 22)

        with pytest.raises(ValueError, match="header too short"):
            parse_cfw_header(path)

    def test_exactly_23_bytes_succeeds(self, tmp_path):
        """Exactly 23 bytes (minimum valid) should parse without error."""
        data = _make_cfw()
        assert len(data) == 23  # No payload, header only
        path = _write_cfw(tmp_path, data)

        result = parse_cfw_header(path)
        assert "app_id" in result

    def test_nonexistent_file_raises(self, tmp_path):
        """A path to a file that doesn't exist should raise FileNotFoundError."""
        path = tmp_path / "nonexistent.cfw"

        with pytest.raises(FileNotFoundError):
            parse_cfw_header(path)
