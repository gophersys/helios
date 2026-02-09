"""Target and probe discovery handler with ProbeManager.

The ProbeManager auto-discovers J-Link probes, identifies which target
each probe is connected to via non-destructive DPID detection, and
provides per-probe locking for parallel flash operations.

Two modes:
- **Dual-probe:** Each probe is mapped directly to its target.  Both
  nrf52840 and nrf9151 can be flashed in parallel (different USB
  devices, no contention).
- **Single-probe (JLINK1 slot):** One probe can reach both targets by
  toggling the J-Link MUX (TCA9534A P0).  Flash requests are
  serialized through the probe lock.
"""

import glob
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from corekinect.utils import Logger
from src.shared.types import (
    DebugProbe,
    DebugProbeType,
    Empty,
    ListProbesResponse,
    ListTargetsResponse,
    TargetDevice,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


# -------------------------------------------------------------------------
# DPID → target family mapping
# -------------------------------------------------------------------------
# ARM Debug Port ID values seen on the SWD bus.  nrfjprog reports these
# in "unexpected debug port ID" errors when the wrong --family flag is
# specified.
DPID_FAMILY_MAP: Dict[int, Tuple[str, str]] = {
    2: ("nrf52840", "NRF52"),   # ARM Cortex-M4 → NRF52 family
    6: ("nrf9151", "NRF91"),    # ARM Cortex-M33 → NRF91 family
}

# Targets considered to be in the NRF91 family (used for JLINK slot heuristic)
NRF91_TARGETS = {"nrf9151", "nrf91", "nrf9160"}


# -------------------------------------------------------------------------
# ProbeMapping — describes one discovered probe
# -------------------------------------------------------------------------
@dataclass
class ProbeMapping:
    """Describes what target a J-Link probe can reach."""
    serial: str
    target_id: str   # e.g., "nrf52840", "nrf9151"
    family: str      # nrfjprog family flag: "NRF52", "NRF91"
    slot: str        # "jlink1" (through MUX) or "jlink2" (direct)


# -------------------------------------------------------------------------
# ProbeManager
# -------------------------------------------------------------------------
class ProbeManager:
    """Auto-discovers J-Link probes and maps them to targets.

    On ``discover()``, runs ``nrfjprog --ids`` to enumerate probes, then
    uses a non-destructive memory read to detect the target DPID for each
    probe.  Results are cached until the next ``discover()`` call.

    Provides ``get_probe_lock(serial)`` for per-probe locking so that
    two nrfjprog processes targeting different USB probes can run in
    parallel, while same-probe access is serialized.
    """

    CLOCKSPEED_KHZ = 4000

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._mappings: Dict[str, ProbeMapping] = {}       # serial → ProbeMapping
        self._target_to_serial: Dict[str, str] = {}        # target_id → serial
        self._probe_locks: Dict[str, threading.Lock] = {}  # serial → Lock
        self._global_lock = threading.Lock()
        self._discovered = False
        self._mode = "none"  # "dual", "single", "none"

    # -- Properties ----------------------------------------------------------

    @property
    def mode(self) -> str:
        """Current probe mode: 'dual', 'single', or 'none'."""
        return self._mode

    @property
    def probe_count(self) -> int:
        return len(self._mappings)

    def get_serials(self) -> List[str]:
        return list(self._mappings.keys())

    def get_mapping(self, serial: str) -> Optional[ProbeMapping]:
        return self._mappings.get(serial)

    def get_all_mappings(self) -> Dict[str, ProbeMapping]:
        return dict(self._mappings)

    # -- Per-probe locking ---------------------------------------------------

    def get_probe_lock(self, serial: str) -> threading.Lock:
        """Get (or create) the per-probe lock for *serial*."""
        with self._global_lock:
            if serial not in self._probe_locks:
                self._probe_locks[serial] = threading.Lock()
            return self._probe_locks[serial]

    # -- Discovery -----------------------------------------------------------

    def discover(self) -> Optional[str]:
        """Discover probes and build target mappings.

        Safe to call multiple times (re-scans each time).
        Returns an error string, or None on success.
        """
        with self._global_lock:
            self._mappings.clear()
            self._target_to_serial.clear()

        serials = self._list_probe_serials()
        if not serials:
            self._mode = "none"
            self._discovered = True
            self.logger.warning("ProbeManager: no J-Link probes detected")
            return None

        self.logger.info(f"ProbeManager: found {len(serials)} probe(s): {', '.join(serials)}")

        # Ensure MUX is NORMAL for identification
        if self.hardware.has_jlink_mux:
            try:
                self.hardware.set_jlink_mux(swap=False)
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"ProbeManager: MUX set failed during discovery: {e}")

        # Identify each probe
        for serial in serials:
            with self._global_lock:
                if serial not in self._probe_locks:
                    self._probe_locks[serial] = threading.Lock()

            target_id, family = self._identify_probe_target(serial)
            if target_id:
                slot = "jlink2" if target_id in NRF91_TARGETS else "jlink1"
                mapping = ProbeMapping(
                    serial=serial, target_id=target_id, family=family, slot=slot,
                )
                with self._global_lock:
                    self._mappings[serial] = mapping
                    self._target_to_serial[target_id] = serial
                self.logger.info(
                    f"ProbeManager: probe {serial} → {target_id} ({family}, {slot})"
                )
            else:
                self.logger.warning(f"ProbeManager: probe {serial} — could not identify target")

        # Determine mode
        mapped = len(self._mappings)
        if mapped >= 2:
            self._mode = "dual"
            self.logger.info("ProbeManager: DUAL mode — parallel flash supported")
        elif mapped == 1:
            self._mode = "single"
            self.logger.info("ProbeManager: SINGLE mode — MUX switching required")
        else:
            self._mode = "none"
            self.logger.warning("ProbeManager: no probes mapped to targets")

        self._discovered = True
        return None

    # -- Probe resolution ----------------------------------------------------

    def resolve_probe_for_target(self, target_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve probe serial for *target_id*.

        Returns:
            (serial, None) on success, or (None, error_message) on failure.
        """
        if not self._discovered:
            err = self.discover()
            if err:
                return None, err

        target = target_id.lower()
        serial = self._target_to_serial.get(target)
        if serial:
            return serial, None

        # In single-probe JLINK1 mode, the probe can reach the other target
        # via MUX switching.
        if self._mode == "single" and len(self._mappings) == 1:
            mapping = next(iter(self._mappings.values()))
            if mapping.slot == "jlink1":
                return mapping.serial, None

        return None, f"No probe available for target '{target_id}'"

    def prepare_mux_for_target(self, target_id: str, serial: str) -> Optional[str]:
        """Set J-Link MUX to the correct position for *target_id*.

        In dual-probe mode, MUX stays NORMAL (JLINK1→Target1, JLINK2 direct).
        In single-probe JLINK1 mode, MUX is toggled to reach the target.

        Returns:
            Error string, or None on success.
        """
        if not self.hardware.has_jlink_mux:
            return None

        mapping = self._mappings.get(serial)
        target = target_id.lower()

        if self._mode == "dual":
            # Dual-probe: MUX always NORMAL
            try:
                self.hardware.set_jlink_mux(swap=False)
                time.sleep(0.3)
            except Exception as e:
                return f"MUX error: {e}"
            return None

        # Single-probe in JLINK1 slot: switch based on target
        if mapping and mapping.slot == "jlink1":
            swap = target in NRF91_TARGETS
            try:
                self.hardware.set_jlink_mux(swap)
                time.sleep(0.5)
                self.logger.info(
                    f"ProbeManager: MUX → {'SWAPPED' if swap else 'NORMAL'} for {target_id}"
                )
            except Exception as e:
                return f"MUX error: {e}"

        return None

    # -- Internal helpers ----------------------------------------------------

    def _list_probe_serials(self) -> List[str]:
        """Get connected J-Link serial numbers via nrfjprog."""
        try:
            result = subprocess.run(
                ["nrfjprog", "--ids"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return [s.strip() for s in result.stdout.strip().split() if s.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.logger.debug("nrfjprog not available for probe detection")
        except Exception as e:
            self.logger.error(f"nrfjprog --ids failed: {e}")
        return []

    def _identify_probe_target(self, serial: str) -> Tuple[Optional[str], Optional[str]]:
        """Identify which target a probe is connected to.

        Uses non-destructive ``nrfjprog --memrd`` to trigger DPID detection.
        If the wrong family is specified, nrfjprog reports a DPID mismatch
        which tells us the actual target family.

        Returns:
            (target_id, family) or (None, None).
        """
        for family, default_target in [("NRF52", "nrf52840"), ("NRF91", "nrf9151")]:
            try:
                result = subprocess.run(
                    [
                        "nrfjprog", "--memrd", "0", "--n", "4",
                        "--snr", serial, "-f", family,
                        "--speed", str(self.CLOCKSPEED_KHZ),
                    ],
                    capture_output=True, text=True, timeout=10,
                )

                if result.returncode == 0:
                    # Probe sees this family
                    return default_target, family

                stderr = result.stderr

                # DPID mismatch → probe sees a different family
                dpid_match = re.search(r"unexpected debug port ID (\d+)", stderr)
                if dpid_match:
                    dpid = int(dpid_match.group(1))
                    if dpid in DPID_FAMILY_MAP:
                        return DPID_FAMILY_MAP[dpid]
                    # Unknown DPID — keep trying other families
                    continue

                # No SWD response — connection issue (GPIO not set? pogo pin?)
                if "-102" in stderr:
                    self.logger.warning(
                        f"Probe {serial}: no SWD response with {family} (-102)"
                    )
                    continue

                # APPROTECT / readback protection — probe IS connected to this family
                if "readback" in stderr.lower() or "approtect" in stderr.lower():
                    return default_target, family

            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                self.logger.error(f"Probe {serial} identification error ({family}): {e}")
                continue

        return None, None


# -------------------------------------------------------------------------
# TargetHandler — gRPC RPCs
# -------------------------------------------------------------------------
class TargetHandler:
    """Handles ListTargets and ListProbes RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._probe_manager: Optional[ProbeManager] = None

    def set_probe_manager(self, pm: ProbeManager) -> None:
        self._probe_manager = pm

    def list_targets(self, request: Empty, context) -> ListTargetsResponse:
        """Return configured target devices from hardware context."""
        targets = []
        targets.append(TargetDevice(
            id="nrf52840",
            name="nRF52840",
            arch=4,  # ARCH_ARM_CORTEX_M4
            chip="nRF52840",
            board="nrf52840dk_nrf52840",
            has_debug=True,
            has_uart=True,
            has_rtt=True,
            has_swo=False,
            flash_size_kb=1024,
            ram_size_kb=256,
        ))
        targets.append(TargetDevice(
            id="nrf9160",
            name="nRF9160",
            arch=6,  # ARCH_ARM_CORTEX_M33
            chip="nRF9160",
            board="nrf9160dk_nrf9160",
            has_debug=True,
            has_uart=True,
            has_rtt=True,
            has_swo=False,
            flash_size_kb=1024,
            ram_size_kb=256,
        ))
        targets.append(TargetDevice(
            id="nrf5340",
            name="nRF5340",
            arch=6,  # ARCH_ARM_CORTEX_M33
            chip="nRF5340",
            board="nrf5340dk_nrf5340_cpuapp",
            has_debug=True,
            has_uart=True,
            has_rtt=True,
            has_swo=False,
            flash_size_kb=1024,
            ram_size_kb=512,
        ))
        targets.append(TargetDevice(
            id="nrf9151",
            name="nRF9151",
            arch=6,  # ARCH_ARM_CORTEX_M33
            chip="nRF9151",
            board="nrf9151dk_nrf9151",
            has_debug=True,
            has_uart=True,
            has_rtt=True,
            has_swo=False,
            flash_size_kb=1024,
            ram_size_kb=256,
        ))

        return ListTargetsResponse(success=True, message="", targets=targets)

    def list_probes(self, request: Empty, context) -> ListProbesResponse:
        """Detect connected debug probes.

        Uses ProbeManager's cached data when available, enriching each
        probe entry with its mapped target.
        """
        probes = []

        # Use ProbeManager if available (preferred — cached + enriched)
        if self._probe_manager:
            for serial, mapping in self._probe_manager.get_all_mappings().items():
                probes.append(DebugProbe(
                    id=serial,
                    type=DebugProbeType.PROBE_JLINK,
                    serial=serial,
                    firmware_version="",
                    supported_targets=[mapping.target_id],
                ))
            if probes:
                return ListProbesResponse(success=True, message="", probes=probes)

        # Fallback: direct nrfjprog scan
        try:
            result = subprocess.run(
                ["nrfjprog", "--ids"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for serial in result.stdout.strip().split():
                    if serial:
                        probes.append(DebugProbe(
                            id=serial,
                            type=DebugProbeType.PROBE_JLINK,
                            serial=serial,
                            firmware_version="",
                            supported_targets=["nrf52840", "nrf9160", "nrf5340", "nrf9151"],
                        ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.logger.debug("nrfjprog not available for probe detection")
        except Exception as e:
            self.logger.warning(f"Error scanning for J-Link probes: {e}")

        # Scan for CMSIS-DAP probes in /dev
        for usb_dev in glob.glob("/dev/ttyACM*"):
            try:
                dev_name = os.path.basename(usb_dev)
                sysfs_path = f"/sys/class/tty/{dev_name}/device"
                if os.path.exists(sysfs_path):
                    product_path = os.path.join(sysfs_path, "../product")
                    if os.path.exists(product_path):
                        with open(product_path, "r") as f:
                            product = f.read().strip()
                        if "CMSIS-DAP" in product or "DAPLink" in product:
                            probes.append(DebugProbe(
                                id=dev_name,
                                type=DebugProbeType.PROBE_CMSIS_DAP,
                                serial="",
                                firmware_version="",
                                supported_targets=[],
                            ))
            except Exception:
                continue

        return ListProbesResponse(success=True, message="", probes=probes)
