# Standard library
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

# Third party
import grpc

# Corekinect
from corekinect.utils import Logger

# Proto types
from src.shared.types import (
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    Empty,
    EnableAppProtectRequest,
    EnableAppProtectResponse,
    EraseFlashRequest,
    EraseFlashResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    FwFileInfo,
    HostType,
    ListFwFilesResponse,
    ListProgrammersResponse,
    Programmer,
    ProgrammerType,
    UploadFwFileRequest,
    UploadFwFileResponse,
)


class FirmwareHandler:
    JLINK_CLOCKSPEED_KHZ = 2000  # Reduced from 4MHz to 2MHz — 4MHz caused verify failures on some boards through the MTIB mux

    def __init__(self, logger: Logger):
        self.logger = logger

        # Flash lock to serialize mux-select + scan + flash/erase operations
        self._flash_lock = threading.Lock()

        # Initialize RAM storage directory in /dev/shm
        self.ram_storage = Path("/dev/shm/mtib_fw_files")
        self.ram_storage.mkdir(exist_ok=True)

        # Initialize programmer info storage
        self.programmers: dict[str, tuple[HostType | None, bool]] = {}

        # Track active firmware files
        self.active_files: Dict[str, Tuple[Path, HostType]] = {}  # Maps filename to (temp file path, target)

        # J-Link mux support via TCA9534A (set via set_hw_context)
        self._gpio_expander = None
        self._num_jlinks = 0  # Detected J-Link probe count

    def set_gpio_expander(self, gpio_expander) -> None:
        """Set the TCA9534A GPIO expander for REV 1.2 J-Link mux control.

        On REV 1.2, the J-Link multiplexer (SN74CBT3257C) is controlled by
        TCA9534A P0 (JLINK_MUL). P0=LOW selects nRF52840, P0=HIGH selects nRF9151.
        """
        self._gpio_expander = gpio_expander
        self.logger.info("J-Link mux support enabled via TCA9534A")

    def _select_jlink_target(self, target: HostType) -> Optional[str]:
        """Select the J-Link mux target on REV 1.2 before flash/erase operations.

        When a single J-Link is muxed between both chips (SN74CBT3257C),
        P0 on the TCA9534A selects the target. When 2+ separate J-Links
        are present (each hardwired to one chip), the mux is not needed.

        Returns error string on failure, None on success.
        """
        if self._gpio_expander is None:
            return None  # No GPIO expander configured

        try:
            # REV 1.2: P0 controls SN74CBT3257C mux — ALWAYS switch,
            # even with 2 probes. The mux routes SWD lines to the chip,
            # probes connect through the mux output.
            # P0=LOW -> nRF9151, P0=HIGH -> nRF52840
            is_nrf52840 = target in (HostType.HOST_TYPE_NRF52840, HostType.HOST_TYPE_NRF5340)
            swap = is_nrf52840
            self._gpio_expander.set_jlink_mux(swap)
            target_name = "nRF52840" if is_nrf52840 else "nRF9151"
            self.logger.info(f"J-Link mux → {target_name} (P0={'HIGH' if swap else 'LOW'})")
            time.sleep(0.3)
            return None
        except Exception as e:
            self.logger.error(f"Failed to set J-Link mux: {e}")
            return f"Failed to set J-Link mux: {e}"

    def _assign_jlinks(self, force_recovery: bool = False):
        """Detect and assign J-Link programmers to their respective chips.

        On REV 1.2 with TCA9534A GPIO expander (J-Link mux), a single J-Link
        can reach BOTH nRF52840 and nRF9151 depending on mux position. We
        register the J-Link for both targets - the mux selection happens
        before each flash operation via _select_jlink_target().
        """
        try:
            serials = subprocess.check_output(["nrfjprog", "--ids"]).decode().split()
        except Exception as e:
            self.logger.error(f"Error getting J-Link serials: {e}")
            serials = []

        self._num_jlinks = len(serials)

        if not serials:
            self.logger.warning("No J-Link probes detected")
            return

        self.logger.info(f"Found {len(serials)} J-Link probe(s): {', '.join(serials)}")

        # Don't re-scan if all probes already have confirmed assignments
        all_assigned = all(
            any(k.startswith(s) and v[1] and v[0] is not None
                for k, v in self.programmers.items())
            for s in serials
        )
        if all_assigned:
            self.logger.info("All probes already assigned — skipping re-scan")
            return

        # REV 1.2 with J-Link mux AND single probe: scan at each mux position.
        # With 2+ probes, each is directly connected — skip mux, use fallback path.
        if self._gpio_expander and len(serials) == 1:
            mux_positions = [
                (HostType.HOST_TYPE_NRF52840, True, "nRF52840"),   # swap=True -> P0=HIGH
                (HostType.HOST_TYPE_NRF9151, False, "nRF9151"),    # swap=False -> P0=LOW
            ]
            for target_type, swap, target_name in mux_positions:
                self._gpio_expander.set_jlink_mux(swap)
                self.logger.info(f"Scanning J-Links with mux set to {target_name} (P0={'HIGH' if swap else 'LOW'})")
                time.sleep(0.3)  # Allow mux to settle

                for serial in serials:
                    # Skip if already assigned to this target
                    key = f"{serial}:{target_name.lower()}"
                    if key in self.programmers:
                        continue

                    # Try to detect device at this mux position.
                    # If APPROTECT is enabled, the probe IS connected but device
                    # info can't be read. We still register it — the flash flow
                    # runs --recover first which clears APPROTECT.
                    try:
                        result = subprocess.check_output(
                            ["nrfjprog", "--snr", serial, "--deviceversion",
                             "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)],
                            stderr=subprocess.STDOUT,
                        ).decode()
                        result_upper = result.strip().upper()

                        if target_type == HostType.HOST_TYPE_NRF52840 and "NRF52840" in result_upper:
                            self.programmers[key] = (HostType.HOST_TYPE_NRF52840, True)
                            self.logger.info(f"J-Link {serial} → nRF52840 (P0={'HIGH' if swap else 'LOW'})")
                        elif target_type == HostType.HOST_TYPE_NRF9151 and ("NRF9151" in result_upper or "NRF9120" in result_upper):
                            self.programmers[key] = (HostType.HOST_TYPE_NRF9151, True)
                            self.logger.info(f"J-Link {serial} → nRF9151 (P0={'HIGH' if swap else 'LOW'})")
                        elif "ACCESS" in result_upper and "PROTECT" in result_upper:
                            # APPROTECT is on — probe IS connected, just can't read device info.
                            # Register it; --recover during flash will clear protection.
                            self.programmers[key] = (target_type, True)
                            self.logger.info(f"J-Link {serial} → {target_name} (APPROTECT — will recover on flash)")
                    except subprocess.CalledProcessError as e:
                        err_msg = (e.output or b"").decode().upper() if e.output else str(e).upper()
                        if "ACCESS" in err_msg and "PROTECT" in err_msg:
                            self.programmers[key] = (target_type, True)
                            self.logger.info(f"J-Link {serial} → {target_name} (APPROTECT — will recover on flash)")
                        elif "ERROR" in err_msg and serial in subprocess.check_output(["nrfjprog", "--ids"]).decode():
                            # Probe exists but can't talk to target — likely APPROTECT or unpowered
                            self.programmers[key] = (target_type, False)
                            self.logger.info(f"J-Link {serial} → {target_name} (probe present, target unreachable)")
                    except Exception as e:
                        self.logger.debug(f"Error scanning J-Link {serial}: {e}")
            return

        # With a mux: the SN74CBT3257C routes ALL SWD lines to one chip at a time.
        # At each mux position, every probe sees the SAME chip. To find which
        # probe is physically wired to which chip, we scan at each position and
        # look for the probe that ONLY works at that position (not both).
        #
        # Strategy: scan all probes at nRF52840 position, then at nRF9151 position.
        # A probe that responds at nRF52840-position but NOT at nRF9151-position
        # is the nRF52840 probe (and vice versa). If both respond at both positions
        # (true mux with 1 probe), register the single probe for both targets.
        if self._gpio_expander:
            nrf52_responders = set()
            nrf91_responders = set()

            # Scan at nRF52840 mux position
            self._gpio_expander.set_jlink_mux(True)  # P0=HIGH → nRF52840
            self.logger.info("Mux → nRF52840 (P0=HIGH), scanning probes...")
            time.sleep(0.3)
            for serial in serials:
                try:
                    result = subprocess.check_output(
                        ["nrfjprog", "--snr", serial, "--deviceversion",
                         "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ), "-f", "NRF52"],
                        stderr=subprocess.STDOUT, timeout=10,
                    ).decode().upper()
                    if "NRF52840" in result:
                        nrf52_responders.add(serial)
                        self.logger.info(f"  {serial}: sees nRF52840")
                except subprocess.CalledProcessError as e:
                    err = (e.output or b"").decode().upper()
                    if "ACCESS" in err and "PROTECT" in err:
                        nrf52_responders.add(serial)
                        self.logger.info(f"  {serial}: APPROTECT (likely nRF52840)")
                    else:
                        self.logger.info(f"  {serial}: no response at nRF52840 position")
                except Exception:
                    pass

            # Scan at nRF9151 mux position
            self._gpio_expander.set_jlink_mux(False)  # P0=LOW → nRF9151
            self.logger.info("Mux → nRF9151 (P0=LOW), scanning probes...")
            time.sleep(0.3)
            for serial in serials:
                try:
                    result = subprocess.check_output(
                        ["nrfjprog", "--snr", serial, "--deviceversion",
                         "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ), "-f", "NRF91"],
                        stderr=subprocess.STDOUT, timeout=10,
                    ).decode().upper()
                    if any(m in result for m in ["NRF9151", "NRF9120", "NRF9160"]):
                        nrf91_responders.add(serial)
                        self.logger.info(f"  {serial}: sees nRF9151")
                except subprocess.CalledProcessError as e:
                    err = (e.output or b"").decode().upper()
                    if "ACCESS" in err and "PROTECT" in err:
                        nrf91_responders.add(serial)
                        self.logger.info(f"  {serial}: APPROTECT (likely nRF9151)")
                    else:
                        self.logger.info(f"  {serial}: no response at nRF9151 position")
                except Exception:
                    pass

            # Assign probes based on which positions they responded at
            self.logger.info(f"nRF52840 responders: {nrf52_responders}, nRF9151 responders: {nrf91_responders}")

            # Probes that ONLY respond at one position are definitively assigned
            only_52 = nrf52_responders - nrf91_responders
            only_91 = nrf91_responders - nrf52_responders
            both = nrf52_responders & nrf91_responders

            for serial in only_52:
                self.programmers[serial] = (HostType.HOST_TYPE_NRF52840, True)
                self.logger.info(f"J-Link {serial} → nRF52840 (exclusive)")

            for serial in only_91:
                self.programmers[serial] = (HostType.HOST_TYPE_NRF9151, True)
                self.logger.info(f"J-Link {serial} → nRF9151 (exclusive)")

            if both:
                if len(both) == 1 and not only_52 and not only_91:
                    # Truly single probe on a mux — register for both targets
                    serial = list(both)[0]
                    self.programmers[serial] = (HostType.HOST_TYPE_NRF52840, True)
                    self.programmers[f"{serial}:nrf91"] = (HostType.HOST_TYPE_NRF9151, True)
                    self.logger.info(f"J-Link {serial} → BOTH via mux (single-probe mux)")
                else:
                    # Multi-probe: "both" probes see both targets through the mux.
                    # Exclusive probes already assigned above. Assign remaining
                    # "both" probes to whichever target still needs one.
                    need_52 = not only_52  # No exclusive nRF52840 probe found
                    need_91 = not only_91  # No exclusive nRF9151 probe found
                    for serial in sorted(both):
                        if need_52:
                            self.programmers[serial] = (HostType.HOST_TYPE_NRF52840, True)
                            self.logger.info(f"J-Link {serial} → nRF52840 (remaining assignment)")
                            need_52 = False
                        elif need_91:
                            self.programmers[serial] = (HostType.HOST_TYPE_NRF9151, True)
                            self.logger.info(f"J-Link {serial} → nRF9151 (remaining assignment)")
                            need_91 = False

            # Unassigned probes: APPROTECT blocks --deviceversion.
            # Assign by elimination when possible. When both are unassigned,
            # try --recover at each mux position to clear APPROTECT and detect.
            # This is safe because the flash step runs --recover anyway.
            unassigned = set(serials) - nrf52_responders - nrf91_responders
            if unassigned:
                self.logger.info(f"Unassigned probes (APPROTECT blocking detection): {unassigned}")

                for serial in list(unassigned):
                    if nrf91_responders and serial not in nrf91_responders:
                        self.programmers[serial] = (HostType.HOST_TYPE_NRF52840, True)
                        self.logger.info(f"J-Link {serial} → nRF52840 (by elimination)")
                        unassigned.discard(serial)
                    elif nrf52_responders and serial not in nrf52_responders:
                        self.programmers[serial] = (HostType.HOST_TYPE_NRF9151, True)
                        self.logger.info(f"J-Link {serial} → nRF9151 (by elimination)")
                        unassigned.discard(serial)

                # Both still unassigned — recover at each mux position to detect
                if len(unassigned) >= 2:
                    self.logger.info("Both probes undetected — recovering to identify targets")
                    probe_list = sorted(unassigned)

                    for serial in probe_list:
                        # Try nRF52840 first
                        self._gpio_expander.set_jlink_mux(True)  # P0=HIGH → nRF52840
                        time.sleep(0.3)
                        try:
                            subprocess.run(
                                ["nrfjprog", "--recover", "--snr", serial,
                                 "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ), "-f", "NRF52"],
                                capture_output=True, text=True, check=True, timeout=30,
                            )
                            # Recover succeeded — this probe reaches nRF52840
                            self.programmers[serial] = (HostType.HOST_TYPE_NRF52840, True)
                            self.logger.info(f"J-Link {serial} → nRF52840 (recovered)")
                            unassigned.discard(serial)
                            break  # Found the nRF52840 probe, remaining one is nRF9151
                        except Exception:
                            pass

                    # Remaining probe must be nRF9151
                    for serial in unassigned:
                        self.programmers[serial] = (HostType.HOST_TYPE_NRF9151, True)
                        self.logger.info(f"J-Link {serial} → nRF9151 (remaining after recovery)")
        else:
            # No mux: try each family flag per probe
            family_attempts = [
                ("NRF52", ["-f", "NRF52"], HostType.HOST_TYPE_NRF52840, ["NRF52840", "NRF52833"]),
                ("NRF91", ["-f", "NRF91"], HostType.HOST_TYPE_NRF9151, ["NRF9151", "NRF9120", "NRF9160"]),
                ("NRF53", ["-f", "NRF53"], HostType.HOST_TYPE_NRF5340, ["NRF5340"]),
            ]
            # nrfjprog's wording for AP-protect varies across versions/devices:
            # nRF52 typically prints "ACCESS PROTECTION IS ENABLED", nRF91 prints
            # "READBACK PROTECTION", and some firmwares print "USE --RECOVER".
            # Match any of those signals.
            def _is_locked(err_text: str) -> bool:
                e = err_text.upper()
                return (
                    ("ACCESS" in e and "PROTECT" in e)
                    or ("READBACK" in e and "PROTECT" in e)
                    or "USE --RECOVER" in e
                    or "MUST BE RECOVERED" in e
                )

            for serial in serials:
                if serial in self.programmers:
                    existing_type, _ = self.programmers[serial]
                    if existing_type is not None:
                        continue
                identified = False
                for family_name, family_flag, host_type, markers in family_attempts:
                    try:
                        result = subprocess.check_output(
                            ["nrfjprog", "--snr", serial, "--deviceversion",
                             "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)] + family_flag,
                            stderr=subprocess.STDOUT, timeout=10,
                        ).decode().upper()
                        if any(m in result for m in markers):
                            self.programmers[serial] = (host_type, True)
                            self.logger.info(f"J-Link {serial} → {family_name} (direct)")
                            identified = True
                            break
                    except subprocess.CalledProcessError as e:
                        err = (e.output or b"").decode()
                        if _is_locked(err):
                            self.programmers[serial] = (host_type, True)
                            self.logger.info(f"J-Link {serial} → {family_name} (APPROTECT)")
                            identified = True
                            break
                    except Exception:
                        continue

                # Probe didn't talk via --deviceversion under any family — most
                # likely an AP-protected chip whose error wording wasn't caught
                # above. Try --recover with each family in order; whichever
                # family's recover sequence succeeds is the chip's family, and
                # the chip is now unlocked. Same operation the flash step would
                # run anyway, so safe to do here.
                if not identified:
                    self.logger.info(
                        f"J-Link {serial}: no family matched via --deviceversion — "
                        f"attempting --recover to identify family"
                    )
                    for family_name, family_flag, host_type, _markers in family_attempts:
                        try:
                            subprocess.run(
                                ["nrfjprog", "--snr", serial, "--recover",
                                 "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)] + family_flag,
                                capture_output=True, check=True, timeout=60,
                            )
                            self.programmers[serial] = (host_type, True)
                            self.logger.info(
                                f"J-Link {serial} → {family_name} (identified via --recover)"
                            )
                            identified = True
                            break
                        except subprocess.CalledProcessError:
                            continue
                        except subprocess.TimeoutExpired:
                            self.logger.warning(
                                f"J-Link {serial}: --recover -f {family_name} timed out"
                            )
                            continue
                    if not identified:
                        self.logger.warning(
                            f"J-Link {serial}: could not identify family via --recover either"
                        )

    def _try_detect_device(self, serial: str) -> bool:
        """Try to detect device type for a J-Link serial number. Returns True if successful."""
        try:
            result = subprocess.check_output(
                ["nrfjprog", "--snr", serial, "--deviceversion", "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)],
                stderr=subprocess.STDOUT,
            ).decode()

            # Log the raw output for debugging
            result_upper = result.strip().upper()

            # APPROTECT is on — probe IS connected, just can't read device info
            if "ACCESS PROTECTION IS ENABLED" in result_upper:
                self.logger.info(f"J-Link {serial} has APPROTECT — registering as connected (will recover on flash)")
                self.programmers[serial] = (None, True)
                return True

            # Check for other error conditions
            if "LOW VOLTAGE" in result_upper or "ERROR" in result_upper:
                self.logger.warning(f"J-Link {serial} detected but no device connected or low voltage condition")
                self.programmers[serial] = (None, False)
                return False

            # Successfully detected device
            self.logger.info(f"J-Link serial {serial} detected with device version {result}")
            self._assign_device_type(serial, result_upper)
            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            self.logger.error(f"Error reading device info for J-Link {serial}: {error_msg}")

            # Check if this might be access protection
            if "access protection" in error_msg.lower() or "error -90" in error_msg.lower():
                self.logger.info(f"J-Link {serial} might have access protection (detected in exception)")
                return False

            self.programmers[serial] = (None, False)
            return False

    def _try_recover_device(self, serial: str) -> bool:
        """Try to recover a J-Link device. Returns True if recovery was successful."""
        try:
            self.logger.info(f"Attempting recovery for J-Link {serial}...")
            recover_result = subprocess.run(
                ["nrfjprog", "--snr", serial, "--recover", "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)],
                capture_output=True,
                text=True,
                timeout=60,  # 30s + buffer
            )

            if recover_result.returncode == 0:
                self.logger.info(f"Successfully recovered J-Link {serial}")
                return True
            else:
                self.logger.error(f"Failed to recover J-Link {serial}: {recover_result.stderr}")
                self.programmers[serial] = (None, False)
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Recovery timeout for J-Link {serial}")
            self.programmers[serial] = (None, False)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during recovery for J-Link {serial}: {e}")
            self.programmers[serial] = (None, False)
            return False

    def _assign_device_type(self, serial: str, result_upper: str):
        """Assign the J-Link serial to the appropriate device type."""
        host_type = None
        if "NRF9160" in result_upper:
            host_type = HostType.HOST_TYPE_NRF9160
        elif "NRF52840" in result_upper:
            host_type = HostType.HOST_TYPE_NRF52840
        elif "NRF5340" in result_upper:
            host_type = HostType.HOST_TYPE_NRF5340
        elif "NRF9151" in result_upper or "NRF9120" in result_upper:
            host_type = HostType.HOST_TYPE_NRF9151

        if host_type:
            self.programmers[serial] = (host_type, True)
            self.logger.info(f"Assigned J-Link {serial} to host type {host_type}")
        else:
            self.logger.warning(f"Unknown device version for serial {serial}")
            self.programmers[serial] = (None, False)

    @staticmethod
    def _get_family_flag(target: HostType) -> list:
        """Return the nrfjprog -f family flag for the given target."""
        if target in (HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9151, HostType.HOST_TYPE_NRF9160_MODEM, HostType.HOST_TYPE_NRF9151_MODEM):
            return ["-f", "NRF91"]
        elif target == HostType.HOST_TYPE_NRF5340:
            return ["-f", "NRF53"]
        else:
            return ["-f", "NRF52"]

    # Modem-compatible targets: nRF9160/nRF9151 programmer can flash modem targets
    _MODEM_TARGETS = {HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9151, HostType.HOST_TYPE_NRF9160_MODEM, HostType.HOST_TYPE_NRF9151_MODEM}
    _MODEM_PROGRAMMERS = {HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF9151}

    def _find_programmer(self, target: HostType) -> Optional[str]:
        """Find a connected programmer serial number suitable for the given target.

        Returns the serial string, or None if no suitable programmer found.
        """
        for key, (host_type, is_connected) in self.programmers.items():
            if not is_connected:
                continue
            serial = key.split(":")[0]
            if target in self._MODEM_TARGETS:
                if host_type in self._MODEM_PROGRAMMERS:
                    return serial
            else:
                if host_type == target:
                    return serial
        return None

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _cleanup_file(self, filename: str) -> None:
        """Clean up a temporary file."""
        if filename in self.active_files:
            try:
                file_path, _ = self.active_files[filename]
                file_path.unlink(missing_ok=True)
                del self.active_files[filename]
            except Exception as e:
                self.logger.error(f"Error cleaning up file {filename}: {e}")

    def list_programmers(self, request: Empty, context: grpc.ServicerContext) -> ListProgrammersResponse:
        """List available programmers."""
        self.logger.info("ListProgrammers request received")
        try:
            # Scan for J-Link probes on every call -- probes may be
            # connected/disconnected at any time and the server has no
            # persistent state about them from startup.
            self._assign_jlinks(force_recovery=False)

            programmers = []

            # Create a programmer for each detected J-Link
            for key, (host_type, is_connected) in self.programmers.items():
                # Extract serial from key (handles both "serial" and "serial:target" formats)
                serial = key.split(":")[0]
                programmer = Programmer(
                    type=ProgrammerType.PROGRAMMER_TYPE_JLINK,
                    host=host_type if is_connected else HostType.HOST_TYPE_UNDEFINED,
                    serial=serial,
                    connected=is_connected,
                )
                programmers.append(programmer)

            return ListProgrammersResponse(success=True, message="", programmers=programmers)
        except Exception as e:
            self.logger.error(f"Error listing programmers: {str(e)}")
            return ListProgrammersResponse(
                success=False, message=f"Failed to list programmers: {str(e)}", programmers=[]
            )

    def list_fw_files(self, request: Empty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        """List available firmware files."""
        self.logger.info("ListFwFiles request received")
        try:
            files = []
            for filename, (file_path, target) in self.active_files.items():
                if file_path.exists():
                    size = file_path.stat().st_size
                    sha256 = self._calculate_sha256(file_path)
                    files.append(FwFileInfo(name=filename, target=target, size_b=size, sha256_digest=sha256))
            return ListFwFilesResponse(success=True, message="", files=files)
        except Exception as e:
            self.logger.error(f"Error listing firmware files: {e}")
            return ListFwFilesResponse(success=False, message=f"Failed to list firmware files: {str(e)}", files=[])

    def upload_fw_file(
        self, request_iterator: Iterator[UploadFwFileRequest], context: grpc.ServicerContext
    ) -> UploadFwFileResponse:
        """Upload a firmware file to RAM.

        Args:
            request_iterator: Iterator of UploadFwFileRequest messages containing file chunks
            context: gRPC servicer context

        Returns:
            UploadFwFileResponse with success status and SHA256 digest
        """
        try:
            # Get the first request to get the filename
            try:
                first_request = next(request_iterator)
            except StopIteration:
                self.logger.error("UploadFwFile request stream ended before first chunk")
                return UploadFwFileResponse(
                    success=False, message="Upload stream ended before first chunk", sha256_digest=""
                )
            except grpc.RpcError as e:
                self.logger.error(f"gRPC error getting first request: {e}")
                return UploadFwFileResponse(
                    success=False, message=f"gRPC error getting first request: {str(e)}", sha256_digest=""
                )

            filename = first_request.name
            target = first_request.target
            self.logger.info(f"UploadFwFile request received for {filename} with target {target}")

            # Clean up any existing file with the same name
            self._cleanup_file(filename)

            # Create a new temporary file in RAM
            temp_file = self.ram_storage / filename
            with open(temp_file, "wb") as f:
                # Write the first chunk
                f.write(first_request.content)

                # Write remaining chunks
                try:
                    for chunk in request_iterator:
                        if not chunk.content:  # Skip empty chunks
                            continue
                        f.write(chunk.content)
                except grpc.RpcError as e:
                    self.logger.error(f"gRPC error during chunk processing: {e}")
                    # Clean up the partial file
                    self._cleanup_file(filename)
                    return UploadFwFileResponse(
                        success=False, message=f"gRPC error during chunk processing: {str(e)}", sha256_digest=""
                    )

            # Calculate SHA256 and store the file path and target
            sha256 = self._calculate_sha256(temp_file)
            self.active_files[filename] = (temp_file, target)

            return UploadFwFileResponse(success=True, message="", sha256_digest=sha256)
        except Exception as e:
            self.logger.error(f"Error uploading firmware file: {e}")
            return UploadFwFileResponse(
                success=False, message=f"Failed to upload firmware file: {str(e)}", sha256_digest=""
            )

    def delete_fw_file(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        """Delete a firmware file from RAM."""
        self.logger.info(f"DeleteFwFile request received for {request.file_info.name}")
        try:
            self._cleanup_file(request.file_info.name)
            return DeleteFwFileResponse(success=True, message="")
        except Exception as e:
            self.logger.error(f"Error deleting firmware file: {e}")
            return DeleteFwFileResponse(success=False, message=f"Failed to delete firmware file: {str(e)}")

    def flash_fw_file(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        """Flash a firmware file from RAM."""
        self.logger.info(f"FlashFwFile request received for {request.file_info.name}")
        with self._flash_lock:
            try:
                # Select J-Link mux target on REV 1.2
                if err := self._select_jlink_target(request.file_info.target):
                    return FlashFwFileResponse(success=False, message=err, time_ms=0)

                # Re-scan and update programmer assignments before flashing
                self._assign_jlinks(force_recovery=True)

                if request.file_info.name not in self.active_files:
                    return FlashFwFileResponse(
                        success=False, message=f"Firmware file {request.file_info.name} not found", time_ms=0
                    )

                file_path, stored_target = self.active_files[request.file_info.name]
                if not file_path.exists():
                    return FlashFwFileResponse(
                        success=False, message=f"Firmware file {request.file_info.name} no longer exists", time_ms=0
                    )

                # Verify SHA256 if provided
                if request.file_info.sha256_digest:
                    current_sha256 = self._calculate_sha256(file_path)
                    if current_sha256 != request.file_info.sha256_digest:
                        return FlashFwFileResponse(success=False, message="SHA256 digest mismatch", time_ms=0)

                # Find a suitable programmer — if not found, clear cache and re-scan
                programmer = self._find_programmer(request.file_info.target)
                if not programmer:
                    self.logger.warning(f"No programmer for target {request.file_info.target} — clearing cache and re-scanning")
                    self.programmers.clear()
                    self._assign_jlinks(force_recovery=True)
                    programmer = self._find_programmer(request.file_info.target)
                if not programmer:
                    return FlashFwFileResponse(
                        success=False,
                        message=f"No suitable programmer found for target {request.file_info.target}",
                        time_ms=0,
                    )

                # Determine nrfjprog family flag based on target
                family_flag = self._get_family_flag(request.file_info.target)

                # Flash the firmware
                start_time = time.time()
                # Step 1: Recover if requested
                if request.recover:
                    try:
                        recover_cmd = [
                            "nrfjprog",
                            "--recover",
                            "--snr",
                            programmer,
                            "--clockspeed",
                            str(self.JLINK_CLOCKSPEED_KHZ),
                        ] + family_flag
                        self.logger.info(f"Running recover: {' '.join(recover_cmd)}")
                        subprocess.run(
                            recover_cmd,
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=60,  # 1 minute timeout
                        )
                    except subprocess.TimeoutExpired:
                        error_msg = f"Recover operation timed out after 1 minute for programmer {programmer}"
                        self.logger.error(error_msg)
                        return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                    except subprocess.CalledProcessError as e:
                        error_msg = f"Failed to recover programmer {programmer}: {e.stderr if e.stderr else str(e)}"
                        if e.stdout:
                            error_msg += f"\nstdout: {e.stdout}"
                        self.logger.error(error_msg)
                        # Clear probe cache — assignment may be wrong
                        self.programmers.clear()
                        return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                    except FileNotFoundError:
                        error_msg = "nrfjprog command not found. Please ensure nRF Command Line Tools are installed."
                        self.logger.error(error_msg)
                        return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
                    except Exception as e:
                        error_msg = f"Unexpected error during recover operation: {str(e)}"
                        self.logger.error(error_msg)
                        return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)

                # Step 1.5: Explicit erase after recover to ensure clean flash.
                # --recover clears APPROTECT but may leave flash in a partial state.
                # An explicit --eraseall guarantees all flash is 0xFF before programming.
                if request.recover:
                    try:
                        erase_cmd = [
                            "nrfjprog",
                            "--eraseall",
                            "--snr",
                            programmer,
                            "--clockspeed",
                            str(self.JLINK_CLOCKSPEED_KHZ),
                        ] + family_flag
                        self.logger.info(f"Running eraseall: {' '.join(erase_cmd)}")
                        subprocess.run(
                            erase_cmd,
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=30,
                        )
                    except Exception as e:
                        self.logger.warning(f"Eraseall failed (non-fatal, chiperase will retry): {e}")

                # Step 2: Build the nrfjprog programming command
                is_nrf91 = request.file_info.target in (
                    HostType.HOST_TYPE_NRF9160,
                    HostType.HOST_TYPE_NRF9151,
                    HostType.HOST_TYPE_NRF9160_MODEM,
                    HostType.HOST_TYPE_NRF9151_MODEM,
                )
                cmd = [
                    "nrfjprog",
                    "--program",
                    str(file_path),
                    "--snr",
                    programmer,
                    "--clockspeed",
                    str(self.JLINK_CLOCKSPEED_KHZ),
                ] + family_flag

                # nRF91 secure firmware enables APPROTECT after programming,
                # which prevents read-back verification. Skip --verify for nRF91.
                if not is_nrf91:
                    cmd.append("--verify")

                if request.sector_erase:
                    cmd.append("--sectorerase")
                else:
                    cmd.append("--chiperase")

                cmd.append("--reset")

                # Step 3: Run the programming command
                self.logger.info(f"Running program: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
                time_ms = int((time.time() - start_time) * 1000)
                self.logger.info(f"Successfully flashed firmware in {time_ms}ms")
                return FlashFwFileResponse(success=True, message="", time_ms=time_ms)

            except subprocess.TimeoutExpired:
                error_msg = f"Flash operation timed out after 1 minute for programmer {programmer}"
                self.logger.error(error_msg)
                return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to flash firmware: {e.stderr if e.stderr else str(e)}"
                if e.stdout:
                    error_msg += f"\nstdout: {e.stdout}"
                self.logger.error(error_msg)
                return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
            except FileNotFoundError:
                error_msg = "nrfjprog command not found. Please ensure nRF Command Line Tools are installed."
                self.logger.error(error_msg)
                return FlashFwFileResponse(success=False, message=error_msg, time_ms=0)
            except Exception as e:
                self.logger.error(f"Error flashing firmware: {e}")
                return FlashFwFileResponse(success=False, message=f"Failed to flash firmware: {str(e)}", time_ms=0)

    def erase_flash(self, request: EraseFlashRequest, context: grpc.ServicerContext) -> EraseFlashResponse:
        """Erase the flash memory on a target device.

        Based on nrfjprog documentation:
        - --chiperase: Erases all available non-volatile memory and UICR
        - --recover: Erases all user flash memory, UICR, and readback protection mechanism
        """
        self.logger.info(f"EraseFlash request received for {request.target}, recover={request.recover}")
        with self._flash_lock:
            try:
                # Select J-Link mux target on REV 1.2
                if err := self._select_jlink_target(request.target):
                    return EraseFlashResponse(success=False, message=err)

                # Re-scan and update programmer assignments before erasing flash
                # Use force_recovery=True when recover flag is set, otherwise False
                self._assign_jlinks(force_recovery=request.recover)

                # Find a suitable programmer
                programmer = self._find_programmer(request.target)
                if not programmer:
                    return EraseFlashResponse(
                        success=False, message=f"No suitable programmer found for target {request.target}"
                    )

                # Choose the appropriate erase command based on recover flag
                # --chiperase: Erases all non-volatile memory and UICR (when recover=False)
                # --recover: Erases everything including readback protection (when recover=True)
                family_flag = self._get_family_flag(request.target)
                if request.recover:
                    cmd = ["nrfjprog", "--recover", "--snr", programmer, "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)] + family_flag
                    self.logger.info(f"Running recover erase: {' '.join(cmd)}")
                else:
                    cmd = ["nrfjprog", "--chiperase", "--snr", programmer, "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ)] + family_flag
                    self.logger.info(f"Running chip erase: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,  # 1 minute timeout
                )
                self.logger.info(f"Successfully erased flash (recover={request.recover})")
                return EraseFlashResponse(success=True, message="")
            except Exception as e:
                self.logger.error(f"Error erasing flash: {e}")
                return EraseFlashResponse(success=False, message=f"Failed to erase flash: {str(e)}")

    def enable_app_protect(
        self, request: EnableAppProtectRequest, context: grpc.ServicerContext
    ) -> EnableAppProtectResponse:
        """Enable App Protect."""
        self.logger.info(f"EnableAppProtect request received for {request.target}")

        with self._flash_lock:
            try:
                # Select J-Link mux target (REV 1.2)
                if err := self._select_jlink_target(request.target):
                    return EnableAppProtectResponse(success=False, message=err)

                # Re-scan and update programmer assignments before enabling protection
                self._assign_jlinks(False)

                # Find a suitable programmer for the target
                programmer = self._find_programmer(request.target)
                if not programmer:
                    return EnableAppProtectResponse(
                        success=False, message=f"No suitable programmer found for target {request.target}"
                    )

                # Determine chip family for nrfjprog --rbp ALL
                # --rbp ALL works for all Nordic chips:
                #   nRF52840: writes UICR.APPROTECT (0x10001208) = 0x00
                #   nRF9160:  writes UICR.APPROTECT + SECUREAPPROTECT
                #   nRF9151:  writes UICR.APPROTECT + SECUREAPPROTECT (91x1 series)
                #   nRF5340:  writes UICR.APPROTECT per core (needs --coprocessor)
                family_flag = self._get_family_flag(request.target)

                if not family_flag:
                    return EnableAppProtectResponse(
                        success=False, message=f"Unsupported target {request.target} for App Protect"
                    )

                family_name = family_flag[1] if len(family_flag) > 1 else "unknown"
                self.logger.info(f"Enabling App Protect ({family_name}) on programmer {programmer}")

                # Step 1: Enable readback protection via --rbp ALL
                try:
                    protect_cmd = [
                        "nrfjprog",
                        "--rbp", "ALL",
                        "--snr", programmer,
                        "--clockspeed", str(self.JLINK_CLOCKSPEED_KHZ),
                    ] + family_flag

                    self.logger.info(f"Running: {' '.join(protect_cmd)}")
                    result = subprocess.run(
                        protect_cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30,
                    )
                    self.logger.info(f"Successfully enabled readback protection for {family_name}")
                    if result.stdout:
                        self.logger.debug(f"rbp stdout: {result.stdout.strip()}")
                except subprocess.TimeoutExpired:
                    error_msg = f"App Protect timed out after 30s for programmer {programmer}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)
                except subprocess.CalledProcessError as e:
                    error_msg = f"Failed to enable App Protect: {e.stderr if e.stderr else str(e)}"
                    if e.stdout:
                        error_msg += f"\nstdout: {e.stdout}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)
                except FileNotFoundError:
                    error_msg = "nrfjprog command not found."
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error during App Protect: {str(e)}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)

                # Step 2: Reset MCU to apply protection
                try:
                    reset_cmd = [
                        "nrfjprog",
                        "--reset",
                        "--snr",
                        programmer,
                        "--clockspeed",
                        str(self.JLINK_CLOCKSPEED_KHZ),
                    ] + family_flag
                    self.logger.info(f"Running reset: {' '.join(reset_cmd)}")
                    result = subprocess.run(
                        reset_cmd,
                        capture_output=True,
                        text=True,
                        check=False,  # Don't fail on non-zero exit code, check output instead
                        timeout=30,  # 30 second timeout
                    )

                    # Check if reset failed due to access protection
                    output = result.stdout + result.stderr
                    if "Access protection is enabled" in output or "readback protection" in output.lower():
                        self.logger.info("Device already has access protection enabled - skipping reset")
                        # Protection is already active, proceed to verification
                    elif result.returncode == 0:
                        self.logger.info("Successfully reset MCU to apply protection")
                    else:
                        error_msg = f"Failed to reset MCU: {result.stderr if result.stderr else str(result)}"
                        if result.stdout:
                            error_msg += f"\nstdout: {result.stdout}"
                        self.logger.error(error_msg)
                        return EnableAppProtectResponse(success=False, message=error_msg)

                except subprocess.TimeoutExpired:
                    error_msg = f"Reset operation timed out after 30 seconds for programmer {programmer}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error during reset: {str(e)}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)

                # Step 3: Wait for MCU to boot (brief delay)
                self.logger.info("Waiting for MCU to boot...")
                time.sleep(2)  # Wait 2 seconds for MCU to boot

                # Step 4: Verify protection is active
                try:
                    verify_cmd = [
                        "nrfjprog",
                        "--memrd",
                        "0x00000000",
                        "--n",
                        "4",
                        "--snr",
                        programmer,
                        "--clockspeed",
                        str(self.JLINK_CLOCKSPEED_KHZ),
                    ] + family_flag
                    self.logger.info(f"Running protection verification: {' '.join(verify_cmd)}")
                    result = subprocess.run(
                        verify_cmd,
                        capture_output=True,
                        text=True,
                        check=False,  # Don't fail on non-zero exit code, we expect this to fail
                        timeout=30,  # 30 second timeout
                    )

                    # Check if the expected protection message is in the output
                    output = result.stdout + result.stderr
                    protection_indicators = [
                        "Can't read memory descriptors, ap-protection is enabled.",
                        "Access protection is enabled",
                        "readback protection",
                        "unavailable due to readback protection",
                    ]

                    protection_active = any(indicator.lower() in output.lower() for indicator in protection_indicators)

                    if protection_active:
                        self.logger.info("App Protect verification successful - protection is active")
                        return EnableAppProtectResponse(success=True, message="App Protect enabled successfully")
                    else:
                        # If we can read memory, protection might not be active
                        self.logger.warning("App Protect verification inconclusive - protection status unclear")
                        self.logger.debug(f"Verification output: {output}")
                        return EnableAppProtectResponse(
                            success=False, message="App Protect verification failed - protection may not be active"
                        )

                except subprocess.TimeoutExpired:
                    error_msg = f"Protection verification timed out after 30 seconds for programmer {programmer}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error during protection verification: {str(e)}"
                    self.logger.error(error_msg)
                    return EnableAppProtectResponse(success=False, message=error_msg)

            except Exception as e:
                self.logger.error(f"Error enabling App Protect: {e}")
                return EnableAppProtectResponse(success=False, message=f"Failed to enable App Protect: {str(e)}")

    def __del__(self):
        """Cleanup all temporary files when the handler is destroyed."""
        try:
            for filename in list(self.active_files.keys()):
                self._cleanup_file(filename)
            if self.ram_storage.exists():
                self.ram_storage.rmdir()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
