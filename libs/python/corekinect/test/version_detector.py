"""Boot version detection via UART capture.

Captures firmware versions from UART boot logs after a power cycle.
The version regex patterns are injectable so products can define their
own patterns for different firmware output formats.

Usage:
    from corekinect.test.version_detector import BootVersionDetector

    detector = BootVersionDetector(fixture_controller)
    versions = detector.capture_boot_versions()
    # {"comms": "0.5.1", "app": "0.8.3"}

    detector.verify_firmware_version("0.5.2", max_boot_cycles=3)
"""

import re
import threading
import time
from typing import Dict, List, Optional, Pattern

from corekinect.errors import FirmwareError
from corekinect.utils import Logger

log = Logger(log_name="version_detector")

# Default patterns for nRF boot logs
DEFAULT_VERSION_PATTERNS: List[Pattern] = [
    re.compile(r"application\s+(\d+)\s+launched.*Version\s+(\d+\.\d+\.\d+)"),
    re.compile(r"Running FW version\s+(\d+)\.(\d+\.\d+\.\d+)"),
]


class BootVersionDetector:
    """Capture and verify firmware versions from UART boot logs.

    Products provide version_patterns as regex list. Default patterns
    match the common nRF "application N launched...Version X.Y.Z" format.

    Each pattern must have group(2) = version string (e.g., "0.5.1").
    """

    def __init__(
        self,
        mtib_client,
        version_patterns: Optional[List[Pattern]] = None,
    ):
        """
        Args:
            mtib_client: Connected MTIB V1 client.
            version_patterns: Regex patterns with group(2) = version string.
                Defaults to DEFAULT_VERSION_PATTERNS.
        """
        self._client = mtib_client
        self._patterns = version_patterns or DEFAULT_VERSION_PATTERNS

    def capture_boot_versions(
        self,
        timeout_s: float = 90.0,
    ) -> Dict[str, Optional[str]]:
        """Power cycle DUT and capture firmware versions from UART boot logs.

        Opens UART streams BEFORE power-on (mandatory — MCUs boot in ms).
        Parses version strings from both APP and COMMS boot output.

        Returns:
            {"comms": "0.5.1" or None, "app": "0.8.3" or None}
        """
        from corekinect.mtib_client.v1.client.types import PowerChannel
        from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

        # Power off first
        self._client.PowerDisable(channel=PowerChannel.DUT)
        self._client.PowerDisable(channel=PowerChannel.CHARGER)
        time.sleep(2)

        versions = {"comms": None, "app": None}
        stop = threading.Event()
        found = {"comms": threading.Event(), "app": threading.Event()}

        def _capture(target: int, key: str) -> None:
            """Capture UART output on a single target in a background thread."""
            partial = ""

            def req_gen():
                """Generate UART stream requests at 20Hz."""
                yield UartStreamRequest(target=target, data=b"")
                while not stop.is_set():
                    time.sleep(0.05)
                    yield UartStreamRequest(target=target, data=b"")

            try:
                for resp in self._client.UartStream(target, req_gen()):
                    if stop.is_set():
                        break
                    if resp.data:
                        partial += resp.data.decode("utf-8", errors="replace")
                        while "\n" in partial:
                            line, partial = partial.split("\n", 1)
                            if versions[key] is None:
                                for pat in self._patterns:
                                    m = pat.search(line)
                                    if m:
                                        versions[key] = m.group(2)
                                        found[key].set()
                                        break
            except Exception as exc:
                log.warning("UART capture error on %s: %s", key, exc)

        # Start UART capture threads BEFORE power-on
        threads = []
        for target, key in [
            (HostType.HOST_TYPE_NRF9151, "comms"),
            (HostType.HOST_TYPE_NRF52840, "app"),
        ]:
            t = threading.Thread(target=_capture, args=(target, key), daemon=True)
            t.start()
            threads.append(t)

        time.sleep(1)  # Let UART threads initialize

        # Power on
        from corekinect.mtib_client.v1.client.types import (
            GpioDirection, GpioResistorConfig,
        )

        for gpio in (0, 1):
            self._client.GpioConfig(
                gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE,
            )
            self._client.GpioWrite(gpio, False)

        self._client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
        self._client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)

        # Wait for BOTH versions
        PROGRESS_LOG_INTERVAL = 10  # Log progress every N seconds
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if found["comms"].is_set() and found["app"].is_set():
                time.sleep(2)  # Let a few more lines flow
                break
            if found["comms"].is_set() and not found["app"].is_set():
                elapsed = int(time.time() - (deadline - timeout_s))
                if elapsed % PROGRESS_LOG_INTERVAL == 0 and elapsed > 0:
                    log.info(
                        "COMMS version detected, waiting for APP "
                        "(MCUboot swap may be in progress)... %ds", elapsed,
                    )
            time.sleep(0.5)

        stop.set()
        for t in threads:
            t.join(timeout=5)

        return versions

    def verify_firmware_version(
        self,
        expected_version: str,
        timeout_s: float = 180.0,
        require_both: bool = True,
        max_boot_cycles: int = 3,
    ) -> Dict[str, Optional[str]]:
        """Power cycle and verify firmware version via UART boot logs.

        After FUOTA delivery, the update process is:
          1. First boot: FUOTA copies pages → MCUboot secondary slot
          2. FUOTA handler sets the pending swap flag
          3. Second boot: MCUboot swaps primary <-> secondary
          4. Third boot (if needed): MCUboot confirms swap

        Retries up to max_boot_cycles to give both processors time to swap.

        Args:
            expected_version: Expected version string (e.g., "0.5.14").
            timeout_s: Max seconds per boot cycle for version detection.
            require_both: If True, fail if either processor version is missing.
            max_boot_cycles: Max power cycles before failing.

        Returns:
            Detected versions dict.

        Raises:
            FirmwareError: If versions don't match after all retries.
        """
        log.info("Verifying firmware version (expecting v%s)...", expected_version)
        log.info(
            "  Max boot cycles: %d, timeout per cycle: %ds",
            max_boot_cycles, int(timeout_s),
        )

        best_versions: Dict[str, Optional[str]] = {"comms": None, "app": None}

        for cycle in range(1, max_boot_cycles + 1):
            log.info("  Boot cycle %d/%d...", cycle, max_boot_cycles)

            cycle_timeout = timeout_s if cycle == 1 else 60.0
            versions = self.capture_boot_versions(timeout_s=cycle_timeout)

            log.info("    COMMS: %s", versions["comms"] or "NOT DETECTED")
            log.info("    APP:   %s", versions["app"] or "NOT DETECTED")

            if versions["comms"]:
                best_versions["comms"] = versions["comms"]
            if versions["app"]:
                best_versions["app"] = versions["app"]

            comms_ok = best_versions["comms"] == expected_version
            app_ok = (
                best_versions["app"] == expected_version
                if require_both else True
            )

            if comms_ok and app_ok:
                log.info(
                    "  Both processors verified at v%s (cycle %d)",
                    expected_version, cycle,
                )
                return best_versions

            if cycle < max_boot_cycles:
                if not comms_ok:
                    log.info(
                        "    COMMS not yet at v%s, power cycling again...",
                        expected_version,
                    )
                if require_both and not app_ok:
                    log.info(
                        "    APP not yet at v%s, power cycling again...",
                        expected_version,
                    )
                time.sleep(5)

        # Final assertions
        log.info("  Final versions after %d cycles:", max_boot_cycles)
        log.info("    COMMS: %s", best_versions["comms"] or "NOT DETECTED")
        log.info("    APP:   %s", best_versions["app"] or "NOT DETECTED")

        if best_versions["comms"] is None:
            raise FirmwareError(
                f"COMMS version not detected after {max_boot_cycles} boot cycles"
            )
        if best_versions["comms"] != expected_version:
            raise FirmwareError(
                f"COMMS version mismatch: expected {expected_version}, "
                f"got {best_versions['comms']} after {max_boot_cycles} boot cycles. "
                f"The COMMS MCUboot may not have swapped the secondary image.",
                expected=expected_version,
                actual=best_versions["comms"] or "",
            )

        if require_both:
            if best_versions["app"] is None:
                raise FirmwareError(
                    f"APP version not detected after {max_boot_cycles} boot cycles. "
                    f"The APP processor may be in a boot loop."
                )
            if best_versions["app"] != expected_version:
                raise FirmwareError(
                    f"APP version mismatch: expected {expected_version}, "
                    f"got {best_versions['app']} after {max_boot_cycles} boot cycles.",
                    expected=expected_version,
                    actual=best_versions["app"] or "",
                )

        return best_versions

    def verify_build_asset(
        self,
        expected,
        timeout_s: float = 180.0,
        max_boot_cycles: int = 3,
    ) -> Dict[str, Optional[str]]:
        """Verify firmware version matches a BuildAsset.

        Convenience method that extracts the version from a BuildAsset
        and delegates to verify_firmware_version().

        Args:
            expected: BuildAsset whose version to verify against.
            timeout_s: Max seconds per boot cycle.
            max_boot_cycles: Max power cycles before failing.

        Returns:
            Detected versions dict.
        """
        return self.verify_firmware_version(
            expected_version=expected.version(),
            timeout_s=timeout_s,
            max_boot_cycles=max_boot_cycles,
        )
