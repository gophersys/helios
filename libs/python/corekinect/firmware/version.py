"""Firmware version detection from UART boot logs.

Product-specific patterns for parsing firmware version strings from
device boot output. Each product (Alpha, Theta, Sigma5) has different
log formats for MFG and production firmware.

Usage:
    from corekinect.firmware.version import detect_version, AlphaVersionDetector

    detector = AlphaVersionDetector()
    version = detector.detect(uart_lines, target="app")  # "0.8.6" or None
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FirmwareVersion:
    """Detected firmware version from boot logs."""
    version: Optional[str] = None      # e.g., "0.8.6"
    app_id: Optional[int] = None       # e.g., 109 (nRF52840) or 108 (nRF9151)
    fw_type: Optional[str] = None      # "mfg" or "prod"
    full_version: Optional[str] = None  # e.g., "109.0.8.6"


class AlphaVersionDetector:
    """Alpha product firmware version detection.

    MFG firmware patterns (nRF52840 APP):
        "Theta Manufacturing Application 109 launched. Version 0.5.4"
        "Running FW version 109.0.5.4"

    MFG firmware patterns (nRF9151 COMMS):
        "Communication Coprocessor application 108 launched. Version 0.5.4"
        "Running FW version 108.0.5.4, Flags 0x9"

    Production firmware patterns (nRF52840 APP):
        "Alpha FW v0.8.6 (id=109, release, a037994)"
        "Running FW version 109.0.8.6"
        "Theta Application 109 launched. Version 0.8.6"

    Production firmware patterns (nRF9151 COMMS):
        "Communication Coprocessor application 108 launched. Version 0.8.6"
        "Running FW version 108.0.8.6, Flags 0x9"
    """

    # Patterns ordered by specificity (most specific first)
    _PATTERNS = [
        # "application NNN launched. Version X.Y.Z"
        re.compile(
            r"application\s+(\d+)\s+launched.*Version\s+(\d+\.\d+\.\d+)"
        ),
        # "Alpha FW vX.Y.Z (id=NNN, ...)"
        re.compile(
            r"Alpha FW v(\d+\.\d+\.\d+)\s*\(id=(\d+)"
        ),
        # "Running FW version NNN.X.Y.Z"
        re.compile(
            r"Running FW version\s+(\d+)\.(\d+\.\d+\.\d+)"
        ),
        # "FW version NNN.X.Y.Z" (general)
        re.compile(
            r"FW version[:\s]+(\d+)\.(\d+\.\d+\.\d+)"
        ),
    ]

    # App ID to target mapping
    APP_IDS = {109: "app", 108: "comms"}

    def detect(self, lines: List[str], target: str = "app") -> Optional[str]:
        """Detect firmware version from boot log lines.

        Args:
            lines: UART boot log lines (raw text, may contain ANSI codes).
            target: "app" (nRF52840, app_id=109) or "comms" (nRF9151, app_id=108).

        Returns:
            Version string (e.g., "0.8.6") or None if not detected.
        """
        target_app_id = 109 if target == "app" else 108

        for line in lines:
            # Strip ANSI escape codes for matching
            clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
            clean = re.sub(r'\u241b\[[0-9;]*m', '', clean)

            for pattern in self._PATTERNS:
                m = pattern.search(clean)
                if not m:
                    continue

                groups = m.groups()

                if len(groups) == 2:
                    # Could be (app_id, version) or (version, app_id)
                    g1, g2 = groups

                    # "application NNN launched. Version X.Y.Z" → (app_id, version)
                    if g1.isdigit() and len(g1) <= 3 and '.' in g2:
                        app_id = int(g1)
                        version = g2
                    # "Alpha FW vX.Y.Z (id=NNN)" → (version, app_id)
                    elif '.' in g1 and g2.isdigit():
                        version = g1
                        app_id = int(g2)
                    # "Running FW version NNN.X.Y.Z" → (app_id_str, version)
                    elif g1.isdigit() and '.' in g2:
                        app_id = int(g1)
                        version = g2
                    else:
                        continue

                    if app_id == target_app_id:
                        return version

        return None

    def detect_all(self, lines: List[str]) -> dict:
        """Detect versions for both processors.

        Returns:
            {"app": "0.8.6" or None, "comms": "0.5.4" or None}
        """
        return {
            "app": self.detect(lines, target="app"),
            "comms": self.detect(lines, target="comms"),
        }


# Default detector for Alpha product
_alpha_detector = AlphaVersionDetector()


def detect_alpha_version(lines: List[str], target: str = "app") -> Optional[str]:
    """Convenience function for Alpha version detection."""
    return _alpha_detector.detect(lines, target)


def detect_alpha_versions(lines: List[str]) -> dict:
    """Convenience function for Alpha — detect both processors."""
    return _alpha_detector.detect_all(lines)
