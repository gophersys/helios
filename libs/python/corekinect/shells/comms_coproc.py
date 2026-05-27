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

import base64
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells.base import ShellCommander, hex_addr


# Backwards-compatible alias — kept so any in-repo importer (and any
# external pinned consumer) that referenced the previous module-private
# helper keeps resolving. Prefer ``hex_addr`` from ``shells.base``.
_hex_addr = hex_addr


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
    """Result from get_sim_info (imei_iccid command).

    Response format:
        IMEI,EID0,ICCID0[,EID1,ICCID1]: <15d>,<32d>,<19-20d>[,<32d>,<19-20d>]

    Fields classified by digit count:
        15 digits  → IMEI
        30-34 digits → EID (eUICC identifier)
        19-20 digits → ICCID
    """
    imei: Optional[str] = None
    eids: List[str] = field(default_factory=list)
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
        modem is warm, data arrives within 0.1s; when cold (e.g. after
        modem DFU), up to 30s while the modem re-registers.

        Strategy: send command, watch buffer for modem data. If no
        response, re-send the command and try again. Repeats until
        timeout_s expires. This keeps the retry logic inside the
        command so callers don't need their own retry loops.

        Returns:
            (SimInfo, error) — error is None on success.
        """
        _log = logging.getLogger("comms_coproc")

        deadline = time.time() + timeout_s
        attempt = 0
        # Each attempt: send command (5s), then watch buffer (up to 10s).
        # Re-send if the modem hasn't responded yet.
        cmd_timeout = min(timeout_s, 5.0)

        while time.time() < deadline:
            attempt += 1
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            # Match any response header starting with "IMEI,"
            lines, err = self._cmd.send(
                "imei_iccid",
                success_patterns=["IMEI,"],
                timeout_s=min(cmd_timeout, remaining),
            )

            if err is None:
                # Try parsing from send() response (warm modem path)
                result = self._parse_sim_response(lines)
                if result.imei:
                    return result, None

            # Cold modem: data arrives after the shell prompt.
            # Watch the stream buffer for a line of comma-separated numeric fields
            # starting with a 15-digit IMEI.
            watch_until = min(time.time() + 10.0, deadline)
            while time.time() < watch_until:
                text = self._cmd._stream.get_text()
                result = self._parse_sim_response(text.splitlines())
                if result.imei:
                    return result, None
                self._cmd._stream._data_event.clear()
                self._cmd._stream._data_event.wait(timeout=0.2)

            if time.time() < deadline:
                _log.info(
                    "IMEI/ICCID attempt %d — no response, re-sending (%.0fs left)",
                    attempt, deadline - time.time(),
                )

        return SimInfo(), f"Modem did not respond within {timeout_s:.0f}s ({attempt} attempts)"

    @staticmethod
    def _parse_sim_response(lines: list) -> SimInfo:
        """Parse IMEI/EID/ICCID from response lines.

        Parses comma-separated values after the header colon.
        Classification by digit count (treating an optional trailing
        Luhn check character ``F`` / ``A`` as part of the ID — many
        ICCIDs are issued as 19 digits + 1 hex check char, e.g.
        ``8949440009200185337F``):
          15 digits          → IMEI
          30–34 digits       → EID (eUICC identifier)
          19–20 digits (or 19–20 + trailing letter) → ICCID
        """
        # Keep only digits in the first len-1 positions; the last
        # position may be a hex Luhn check character (F most commonly).
        def _is_iccid_like(s: str) -> bool:
            if not (19 <= len(s) <= 20):
                return False
            return s[:-1].isdigit() and (s[-1].isdigit() or s[-1] in "ABCDEFabcdef")

        for line in lines:
            # Match header line with colon-separated data
            m = re.search(r"IMEI[^:]*:\s*(.+)", line)
            if not m:
                continue
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split(",")]

            imei = None
            eids = []
            iccids = []
            for part in parts:
                if not part:
                    continue
                n = len(part)
                if n == 15 and part.isdigit() and imei is None:
                    imei = part
                elif 30 <= n <= 34 and part.isdigit():
                    eids.append(part)
                elif _is_iccid_like(part):
                    iccids.append(part)

            if imei and iccids:
                return SimInfo(imei=imei, eids=eids, iccids=iccids)

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

    def set_cgdcont(
        self, at_string: str, timeout_s: float = 30.0
    ) -> Tuple[bool, Optional[str]]:
        """Persist the modem CGDCONT (APN) context for both SIM slots.

        ``at_string`` is the full semicolon-delimited list the firmware
        expects, in SIM order, e.g. for a Verizon-primary unit::

            'AT+CGDCONT=1,"IPV4V6","VZWINTERNET",0,0,0,1;'
            'AT+CGDCONT=1,"IP","internet",0,0,0,1'

        The firmware command (``comm_coproc_mfg/src/app/shell_handler.c``
        → ``cmd_set_cgdcont``) copies the string into the modem CGDCONT
        persistent buffer and triggers ``persistent_data_save()``. The
        modem applies it on the next attach.

        WARNING: this writes both SIM contexts in one shot — get the
        per-SIM order right.

        Returns:
            (success, error) — success is True when the firmware echoed
            "Setting <command>".
        """
        lines, err = self._cmd.send(
            f"set_cgdcont {at_string}",
            success_patterns=["Setting "],
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        ok = any(("Setting " in l) and (at_string[:32] in l) for l in lines) \
            or any("Setting " in l for l in lines)
        if not ok:
            return False, f"set_cgdcont did not echo 'Setting': {lines}"
        return True, None

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
        self,
        address: Union[int, str],
        data: Union[bytes, str],
        timeout_s: float = 15.0,
    ) -> Tuple[bool, Optional[str]]:
        """Write data to external flash.

        ``data`` accepts raw ``bytes`` (preferred — encoded internally)
        or an already-base64-encoded ``str``. Earlier callers were
        passing raw bytes through an ``f"...{data}"`` format string,
        which sent the Python ``b'\\xa5...'`` *repr* over UART; the
        firmware base64 decoder rejected it with "Base64 conversion to
        char array failed. Invalid argument".

        ``address`` accepts an ``int`` (formatted as ``0x{:08x}``) or
        an already-formatted hex/decimal string.

        Returns:
            (success, error)
        """
        if isinstance(data, bytes):
            data_b64 = base64.b64encode(data).decode("ascii")
        else:
            data_b64 = data
        lines, err = self._cmd.send(
            f"write_ext_flash {_hex_addr(address)} {data_b64}",
            success_patterns=["Writing", "bytes to address:"],
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        return any("Writing" in l for l in lines), None

    def read_ext_flash(
        self,
        address: Union[int, str],
        num_bytes: int,
        timeout_s: float = 15.0,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """Read data from external flash.

        Returns the actual bytes the firmware reported, parsed from the
        hex dump it prints (``00000000: aa bb cc … |ascii|``). Returning
        bytes — not the hex string — lets callers compare directly
        against the bytes they wrote.

        Returns:
            (data, error)
        """
        # success_patterns intentionally None: the firmware emits
        # ``Reading %d bytes from address: 0x%x`` BEFORE the underlying
        # SPI flash_read() runs, then the hex-dump, then the prompt.
        # If we put "Reading" / "bytes from address" / a prompt into
        # success_patterns, ShellCommander.send() arms its 3 s fallback
        # the moment the prologue line lands and returns BEFORE the
        # actual hex-dump arrives whenever the read is slow (on the
        # nRF9151 comms processor under LTE modem load this happens
        # every time — see run cmpnbxt5y on panel 0AW2 where every
        # slot failed with ``Failed to parse hex data from:
        # ['Reading 8 bytes from address: 0x0']``).
        #
        # With no success_patterns, ``send()`` waits for the prompt
        # line — which the firmware prints AFTER ``shell_hexdump``
        # completes. The full read response is then in ``lines`` and
        # the hex parser below has data to work on.
        lines, err = self._cmd.send(
            f"read_ext_flash {_hex_addr(address)} {num_bytes}",
            success_patterns=None,
            timeout_s=timeout_s,
        )
        # If send() timed out but there's data in the buffer, try parsing it
        if err and not lines:
            time.sleep(1)
            text = self._cmd._stream.get_text()
            if text:
                lines = [l for l in text.splitlines() if l.strip()]
        if err:
            return None, err

        # The firmware emits a hex dump like:
        #   00000000: a5 5a ff 01 02 03 fe ed                          |.Z......        |
        # Strip the leading "<offset>:" address column before scanning
        # for hex byte pairs — without this strip, the regex picks up
        # the four bytes that make up the offset and prepends them to
        # the data, returning 12 bytes when the caller asked for 8.
        offset_re = re.compile(r"^\s*[0-9A-Fa-f]{4,8}\s*:\s*")
        hex_data = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            payload = stripped.split("|", 1)[0]  # drop ASCII sidebar
            payload = offset_re.sub("", payload).strip()  # drop "00000000: " prefix
            if not payload:
                continue
            if re.fullmatch(r"(?:[0-9A-Fa-f]{2}\s*)+", payload):
                hex_data += re.sub(r"\s+", "", payload)

        if hex_data:
            try:
                # Firmware always dumps in 16-byte rows (zero-padded), so slice down to what the caller asked for.
                return bytes.fromhex(hex_data)[:num_bytes], None
            except ValueError as exc:
                return None, f"Failed to decode hex output ({exc}): {hex_data[:64]}…"
        return None, f"Failed to parse hex data from: {lines}"

    def erase_ext_flash(self, timeout_s: float = 150.0) -> Tuple[bool, Optional[str]]:
        """Erase entire external flash.

        The MX25L6406E whole-chip erase blocks the SPI bus while the
        chip's WIP bit is high — datasheet quotes 80 s typ / 100 s max.
        The firmware shell sits inside ``flash_erase()`` for that entire
        window, then prints the prompt. Default ``timeout_s`` is 150 s
        — comfortably above the datasheet max plus shell-print latency
        and a small jitter margin.

        ``success_patterns`` is intentionally ``None``: ``ShellCommander.
        send()`` then waits for the prompt, which is the *only* signal
        that ``flash_erase()`` has actually returned. Earlier versions
        used ``["Erasing flash", "pages"]``, but those tokens match the
        firmware's *prologue* line (``shell_print("Erasing flash. %d
        pages, ...")``) emitted BEFORE the syscall runs — so ``send()``'s
        3 s premature-success fallback fired ~3 s into the erase and
        reported success while the chip was still busy. The next shell
        command then raced the still-erasing chip and lost (run
        cmpnd4ifm on panel 0AW2, test_08 failures on all 5 slots).
        See ``shells/tests/test_read_ext_flash_cadence.py``.

        Returns:
            (success, error)
        """
        lines, err = self._cmd.send(
            "erase_ext_flash",
            success_patterns=None,
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        joined = "\n".join(lines)
        if "Flash erase failed" in joined:
            return False, f"Flash erase failed: {joined[:300]}"
        return any("Erasing flash" in l for l in lines), None
