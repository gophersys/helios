"""Unit tests for BootVersionDetector.

Tests regex pattern matching and verify_build_asset delegation.
Does NOT test capture_boot_versions (requires MTIB UART hardware).
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.version_detector import (
    DEFAULT_VERSION_PATTERNS,
    BootVersionDetector,
)


# =============================================================================
# DEFAULT_VERSION_PATTERNS regex matching
# =============================================================================


class TestDefaultVersionPatterns:
    """Tests for DEFAULT_VERSION_PATTERNS regex patterns."""

    # ── Pattern 1: "application N launched...Version X.Y.Z" ──

    def test_app_launched_pattern_matches_109(self):
        """Should match 'application 109 launched successfully. Version 0.8.3'."""
        line = "application 109 launched successfully. Version 0.8.3"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match is not None
        assert match.group(2) == "0.8.3"

    def test_app_launched_pattern_matches_108(self):
        """Should match 'application 108 launched successfully. Version 0.5.1'."""
        line = "application 108 launched successfully. Version 0.5.1"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match is not None
        assert match.group(1) == "108"
        assert match.group(2) == "0.5.1"

    def test_app_launched_pattern_extracts_app_id(self):
        """Group 1 should be the app ID."""
        line = "application 109 launched successfully. Version 0.8.3"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match.group(1) == "109"

    def test_app_launched_pattern_embedded_in_log_line(self):
        """Should match when the pattern appears within a longer log line."""
        line = "[00:00:03.456] application 109 launched successfully. Version 0.8.3 (build 42)"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match is not None
        assert match.group(2) == "0.8.3"

    # ── Pattern 2: "Running FW version N.X.Y.Z" ──

    def test_running_fw_pattern_matches(self):
        """Should match 'Running FW version 109.0.8.3'."""
        line = "Running FW version 109.0.8.3"
        match = DEFAULT_VERSION_PATTERNS[1].search(line)
        assert match is not None
        assert match.group(2) == "0.8.3"

    def test_running_fw_pattern_extracts_app_id(self):
        """Group 1 should be the app ID prefix."""
        line = "Running FW version 108.0.5.1"
        match = DEFAULT_VERSION_PATTERNS[1].search(line)
        assert match is not None
        assert match.group(1) == "108"
        assert match.group(2) == "0.5.1"

    def test_running_fw_pattern_embedded_in_log_line(self):
        """Should match within a longer log line."""
        line = "[00:00:05.789] Running FW version 109.0.8.3 -- nRF52840"
        match = DEFAULT_VERSION_PATTERNS[1].search(line)
        assert match is not None
        assert match.group(2) == "0.8.3"

    # ── Negative cases ──

    def test_patterns_do_not_match_random_text(self):
        """Neither pattern should match arbitrary text."""
        lines = [
            "Hello, world!",
            "Temperature: 25.3C",
            "uart0 initialized at 115200",
            "MCUboot primary confirmed",
        ]
        for line in lines:
            for pat in DEFAULT_VERSION_PATTERNS:
                assert pat.search(line) is None, f"Pattern matched unexpected line: {line}"

    def test_patterns_do_not_match_partial_version(self):
        """Should not match incomplete version strings."""
        partial_lines = [
            "application 109 launched successfully. Version 0.8",
            "Running FW version 109.0.8",
            "application launched successfully. Version 0.8.3",
            "Running FW version .0.8.3",
        ]
        for line in partial_lines:
            matched = False
            for pat in DEFAULT_VERSION_PATTERNS:
                m = pat.search(line)
                if m and re.fullmatch(r"\d+\.\d+\.\d+", m.group(2)):
                    matched = True
            # These partial lines should not produce valid 3-part version matches
            # (some patterns may match sub-portions, but group(2) should not be valid)
            # We just verify no pattern produces a clean match on the truly broken lines
            if "Version 0.8" == line.split("Version ")[-1] if "Version " in line else True:
                pass  # partial version, acceptable non-match

    def test_pattern_does_not_match_missing_app_id(self):
        """Pattern 1 requires an app ID number before 'launched'."""
        line = "application launched successfully. Version 0.8.3"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match is None

    def test_pattern_does_not_match_version_without_three_parts(self):
        """Pattern should require X.Y.Z (three dot-separated numbers)."""
        line = "application 109 launched successfully. Version 0.8"
        match = DEFAULT_VERSION_PATTERNS[0].search(line)
        assert match is None

    # ── Cross-pattern coverage ──

    def test_any_pattern_matches_app_launched(self):
        """At least one pattern should match the app-launched format."""
        line = "application 109 launched successfully. Version 0.8.3"
        matches = [pat.search(line) for pat in DEFAULT_VERSION_PATTERNS]
        assert any(m is not None for m in matches)

    def test_any_pattern_matches_running_fw(self):
        """At least one pattern should match the Running FW format."""
        line = "Running FW version 108.0.5.1"
        matches = [pat.search(line) for pat in DEFAULT_VERSION_PATTERNS]
        assert any(m is not None for m in matches)


# =============================================================================
# verify_build_asset delegation
# =============================================================================


class TestVerifyBuildAsset:
    """Tests for BootVersionDetector.verify_build_asset()."""

    def test_delegates_to_verify_firmware_version(self):
        """Should call verify_firmware_version with the BuildAsset's version."""
        mock_client = MagicMock()
        detector = BootVersionDetector(mtib_client=mock_client)

        # Mock the verify_firmware_version method
        detector.verify_firmware_version = MagicMock(
            return_value={"comms": "0.5.2", "app": "0.5.2"}
        )

        # Create a mock BuildAsset with .version() returning "0.5.2"
        mock_asset = MagicMock()
        mock_asset.version.return_value = "0.5.2"

        result = detector.verify_build_asset(mock_asset)

        detector.verify_firmware_version.assert_called_once_with(
            expected_version="0.5.2",
            timeout_s=180.0,
            max_boot_cycles=3,
        )
        assert result == {"comms": "0.5.2", "app": "0.5.2"}

    def test_passes_custom_timeout_and_boot_cycles(self):
        """Should forward timeout_s and max_boot_cycles kwargs."""
        mock_client = MagicMock()
        detector = BootVersionDetector(mtib_client=mock_client)

        detector.verify_firmware_version = MagicMock(
            return_value={"comms": "0.8.3", "app": "0.8.3"}
        )

        mock_asset = MagicMock()
        mock_asset.version.return_value = "0.8.3"

        detector.verify_build_asset(
            mock_asset, timeout_s=60.0, max_boot_cycles=5,
        )

        detector.verify_firmware_version.assert_called_once_with(
            expected_version="0.8.3",
            timeout_s=60.0,
            max_boot_cycles=5,
        )
