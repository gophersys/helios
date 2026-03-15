"""Alpha nRF9151 comms coprocessor shell commands.

Usage:
    from corekinect.shells.comms_coproc import CommsCoprocShell

    comms = CommsCoprocShell(mtib_client)
    comms.lock()
    comms.debug_off()

    ids = comms.get_chip_ids()
    print(f"Flash: {ids.ext_flash_id}")

    sim = comms.get_sim_info()
    print(f"IMEI: {sim.imei}, ICCIDs: {sim.iccids}")

    keys = comms.personalize("70B3D584C01E1FCC")
    print(f"Public key: {keys.base64}")
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells.base import ShellCommander


# ── Result types ─────────────────────────────────────────

@dataclass
class CommsChipIds:
    """Result from get_chip_ids on nRF9151."""
    ext_flash_id: Optional[str] = None
    lora_available: Optional[str] = None


@dataclass
class ModemFirmware:
    """Result from get_modem_fw."""
    version: Optional[str] = None


@dataclass
class SimInfo:
    """Result from get_sim_info (imei_iccid command)."""
    imei: Optional[str] = None
    iccids: List[str] = field(default_factory=list)


@dataclass
class PersonalizeResult:
    """Result from personalize command."""
    hex_key: Optional[str] = None
    base64_key: Optional[str] = None


@dataclass
class ExtFlashResult:
    """Result from ext flash operations."""
    write_ok: bool = False
    read_ok: bool = False
    data_match: bool = False


# ── Shell interface ──────────────────────────────────────

class CommsCoprocShell:
    """nRF9151 comms coprocessor manufacturing shell.

    Args:
        mtib: Connected MtibV1Client instance.
    """

    TARGET = HostType.HOST_TYPE_NRF9151

    def __init__(self, mtib):
        self._cmd = ShellCommander(mtib, self.TARGET, label="COMMS")

    # ── Lifecycle ────────────────────────────────────

    def start(self) -> None:
        """Start persistent UART stream."""
        self._cmd.start()

    def stop(self) -> None:
        """Stop persistent UART stream."""
        self._cmd.stop()

    def lock(self, timeout_s: float = 120.0) -> bool:
        """Lock the manufacturing shell."""
        return self._cmd.lock(timeout_s=timeout_s)

    def debug_off(self, timeout_s: float = 30.0) -> bool:
        """Disable debug UART output."""
        return self._cmd.debug_off(timeout_s=timeout_s)

    def reset_stream(self) -> None:
        """Reset stream to clear pipeline. Call after lock+debug_off."""
        self._cmd.reset_stream()

    # ── Hardware queries ─────────────────────────────

    def get_chip_ids(self, timeout_s: float = 30.0) -> Tuple[CommsChipIds, Optional[str]]:
        """Get external flash ID and LoRa hardware status.

        Returns:
            (CommsChipIds, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "get_chip_ids",
            success_patterns=["Ext flash chip ID:"],
            timeout_s=timeout_s,
        )
        if err:
            return CommsChipIds(), err

        result = CommsChipIds()
        for line in lines:
            m = re.search(r"Ext flash chip ID:\s*(.+)", line)
            if m:
                result.ext_flash_id = m.group(1).strip()
            m = re.search(r"LoRa hardware available:\s*(\w+)", line)
            if m:
                result.lora_available = m.group(1).strip()

        if result.ext_flash_id:
            return result, None
        return result, f"Failed to parse chip IDs from: {lines}"

    def get_modem_fw(self, timeout_s: float = 30.0) -> Tuple[ModemFirmware, Optional[str]]:
        """Get modem firmware version.

        Returns:
            (ModemFirmware, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "get_modem_fw",
            success_patterns=["Modem FW:"],
            timeout_s=timeout_s,
        )
        if err:
            return ModemFirmware(), err

        result = ModemFirmware()
        for line in lines:
            m = re.search(r"Modem FW:\s*(.+)", line)
            if m:
                result.version = m.group(1).strip()
                return result, None

        return result, f"Failed to parse modem FW from: {lines}"

    def get_sim_info(self, timeout_s: float = 30.0) -> Tuple[SimInfo, Optional[str]]:
        """Get IMEI and ICCIDs from the modem.

        The firmware's imei_iccid command is async: it prints the
        header immediately, returns control to the shell (prompt
        printed), and the modem data arrives 1-5s later. When the
        modem is warm, data arrives within 0.1s; when cold, up to 5s.

        Strategy: send command normally. If data isn't in the initial
        response, keep watching the stream buffer for the modem data
        to arrive asynchronously.

        Returns:
            (SimInfo, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "imei_iccid",
            success_patterns=["IMEI,ICCID"],
            timeout_s=timeout_s,
        )
        if err:
            return SimInfo(), err

        # Try parsing from send() response (warm modem path)
        result = self._parse_sim_lines(lines)
        if result.imei:
            return result, None

        # Cold modem: data arrives after the shell prompt.
        # Watch the stream buffer for IMEI (15 digits) + ICCID (19-20 digits).
        deadline = time.time() + min(timeout_s, 10.0)
        while time.time() < deadline:
            text = self._cmd._stream.get_text()
            m = re.search(r"(\d{15}),(\d{19,20}(?:,\d{19,20})*)", text)
            if m:
                imei = m.group(1)
                iccids = m.group(2).split(",")
                return SimInfo(imei=imei, iccids=iccids), None
            self._cmd._stream._data_event.clear()
            self._cmd._stream._data_event.wait(timeout=0.2)

        return SimInfo(), f"Modem did not respond within timeout"

    @staticmethod
    def _parse_sim_lines(lines: list) -> SimInfo:
        """Parse IMEI/ICCID from response lines."""
        for line in lines:
            m = re.search(r"IMEI,ICCID[^:]*:\s*(.+)", line)
            if m:
                parts = [p.strip() for p in m.group(1).split(",")]
                if len(parts) >= 2:
                    return SimInfo(imei=parts[0], iccids=parts[1:])
        return SimInfo()

    # ── Security / personalization ───────────────────

    def personalize(
        self, device_id: str, timeout_s: float = 60.0
    ) -> Tuple[PersonalizeResult, Optional[str]]:
        """Personalize device — generates EC keypair and returns public key.

        Args:
            device_id: Device ID to personalize with.

        Returns:
            (PersonalizeResult, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            f"personalize {device_id}",
            success_patterns=["Public key (base64)"],
            timeout_s=timeout_s,
        )
        if err:
            return PersonalizeResult(), err

        result = PersonalizeResult()
        joined = "\n".join(lines)

        # Hex key regex: also match truncated prefix from IPC interleaving
        # (APP IPC messages can corrupt "Public key" → "ey" or similar)
        m = re.search(r"(?:Public key \(hex\)|ey \(hex\))\s*:\s*([0-9a-fA-F]{100,})", joined)
        if not m:
            # Fallback: any 128+ char hex string is likely the key
            m = re.search(r":\s*([0-9a-fA-F]{128,})", joined)
        if m:
            result.hex_key = m.group(1)

        m = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]{40,})", joined)
        if m:
            result.base64_key = m.group(1)

        # Base64 key alone is sufficient for CoreCloud key upload
        if result.base64_key:
            return result, None
        return result, f"Failed to parse public keys from: {joined[:300]}"

    def get_pub_key(self, timeout_s: float = 15.0) -> Tuple[PersonalizeResult, Optional[str]]:
        """Get existing device public key (without re-personalizing).

        Returns:
            (PersonalizeResult, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "get_pub_key",
            success_patterns=["Public key (base64):"],
            timeout_s=timeout_s,
        )
        if err:
            return PersonalizeResult(), err

        result = PersonalizeResult()
        joined = "\n".join(lines)

        m = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]+)", joined)
        if m:
            result.hex_key = m.group(1)

        m = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]+)", joined)
        if m:
            result.base64_key = m.group(1)

        if result.hex_key and result.base64_key:
            return result, None
        return result, f"Failed to parse public keys from: {joined[:200]}"

    def rekey_ipc(self, timeout_s: float = 15.0) -> Tuple[bool, Optional[str]]:
        """Rekey IPC — generates new IPC encryption key and syncs with app processor.

        Returns:
            (success, error) — success is True if rekey completed.
        """
        lines, err = self._cmd.send(
            "rekey_ipc",
            success_patterns=["IPC rekey completed successfully", "IPC rekey failed"],
            timeout_s=timeout_s,
        )
        if err:
            return False, err

        joined = "\n".join(lines)
        if "IPC rekey completed successfully" in joined:
            return True, None
        if "IPC rekey failed" in joined:
            return False, "IPC rekey failed (reported by device)"
        return False, f"Unexpected response: {joined[:200]}"

    # ── External flash ───────────────────────────────

    def write_ext_flash(
        self, address: str, data_b64: str, timeout_s: float = 15.0
    ) -> Tuple[bool, Optional[str]]:
        """Write base64-encoded data to external flash.

        Returns:
            (success, error)
        """
        lines, err = self._cmd.send(
            f"write_ext_flash {address} {data_b64}",
            success_patterns=["Writing", "bytes to address:"],
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        return any("Writing" in l for l in lines), None

    def read_ext_flash(
        self, address: str, num_bytes: int, timeout_s: float = 15.0
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash.

        Returns:
            (hex_data, error) — hex_data is the concatenated hex bytes.
        """
        lines, err = self._cmd.send(
            f"read_ext_flash {address} {num_bytes}",
            success_patterns=["Reading", "Mfg shell:", "Comms Mfg:"],
            timeout_s=timeout_s,
        )
        if err:
            return None, err

        hex_data = ""
        for line in lines:
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")

        if hex_data:
            return hex_data, None
        return None, f"Failed to parse hex data from: {lines}"

    def erase_ext_flash(self, timeout_s: float = 30.0) -> Tuple[bool, Optional[str]]:
        """Erase entire external flash.

        Returns:
            (success, error)
        """
        lines, err = self._cmd.send(
            "erase_ext_flash",
            success_patterns=["Erasing flash", "pages"],
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        return any("Erasing flash" in l for l in lines), None
