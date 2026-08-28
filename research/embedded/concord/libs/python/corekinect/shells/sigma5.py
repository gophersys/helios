"""Sigma5 nRF52840 application processor shell commands.

Modeled on AlphaAppShell — uses :class:`ShellCommander` so the
caller opens a persistent UART stream once (``start()``), races
the manufacturing-shell window with spam-based locking
(``lock(timeout_s)``), then issues commands against the live
buffer without per-command stream churn.

Usage:
    from corekinect.shells.sigma5 import Sigma5AppShell

    app = Sigma5AppShell(mtib_client)
    app.start()                              # open UART before power
    # … power-cycle the DUT here …
    if not app.lock(timeout_s=20.0):
        raise RuntimeError("missed mfg shell window")
    app.debug_off()
    app.reset_stream()

    ids, err = app.get_chip_ids()
    print(f"BLE MAC: {ids.ble_mac}")
"""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells.base import ShellCommander, hex_addr


# ── Result types ─────────────────────────────────────────


@dataclass
class Sigma5ChipIds:
    """Result from get_chip_ids on the Sigma5 nRF52840."""

    accel_id: Optional[str] = None
    altimeter_id: Optional[str] = None
    ext_flash_id: Optional[str] = None
    gps_hw_version: Optional[str] = None
    ble_mac: Optional[str] = None


@dataclass
class Sigma5UbloxInfo:
    """Result from get_ublox on the Sigma5 nRF52840."""

    hw_version: Optional[str] = None
    fw_version: Optional[str] = None
    sw_version: Optional[str] = None
    proto_version: Optional[str] = None
    constellations: Optional[str] = None


@dataclass
class Sigma5AccelReading:
    """Result from read_accel on the Sigma5 nRF52840."""

    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    temp_c: Optional[float] = None


@dataclass
class Sigma5AltimeterReading:
    """Result from read_alt on the Sigma5 nRF52840."""

    pressure_hg: Optional[float] = None
    temp_c: Optional[float] = None


# ── Shell interface ──────────────────────────────────────


class Sigma5AppShell:
    """nRF52840 application processor manufacturing shell — Sigma5 C0.

    Args:
        mtib: Connected MtibV1Client instance.
    """

    TARGET = HostType.HOST_TYPE_NRF52840

    def __init__(self, mtib):
        self._cmd = ShellCommander(mtib, self.TARGET, label="APP")

    # ── Lifecycle ────────────────────────────────────

    def start(self) -> None:
        """Start persistent UART stream. Call BEFORE power-on so the
        boot output is captured from the first byte."""
        self._cmd.start()

    def stop(self) -> None:
        """Stop persistent UART stream."""
        self._cmd.stop()

    def lock(self, timeout_s: float = 120.0) -> bool:
        """Race the manufacturing-shell boot window.

        Spams ``lock_shell`` for the first few seconds after boot,
        then watches the buffer for the ``mode ON`` confirmation.
        """
        return self._cmd.lock(timeout_s=timeout_s)

    def debug_off(self, timeout_s: float = 30.0) -> bool:
        """Disable debug UART output. Call once shells are locked."""
        return self._cmd.debug_off(timeout_s=timeout_s)

    def reset_stream(self) -> None:
        """Clear the buffer pipeline. Call after lock + debug_off,
        before running real test commands."""
        self._cmd.reset_stream()

    # ── Back-compat aliases ──────────────────────────

    def lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Deprecated single-shot lock helper.

        Kept so older callers (test_03_verify_boot etc.) keep
        working through the migration; new code should call
        ``start()`` then ``lock(timeout_s=…)`` directly.
        """
        ok = self._cmd.lock(timeout_s=20.0)
        return (ok, None) if ok else (False, "lock_shell timeout")

    def debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Deprecated alias for ``debug_off``."""
        ok = self._cmd.debug_off(timeout_s=15.0)
        return (ok, None) if ok else (False, "debug_off timeout")

    # ── Hardware tests ───────────────────────────────

    def get_chip_ids(
        self, timeout_s: float = 30.0
    ) -> Tuple[Sigma5ChipIds, Optional[str]]:
        """Read accelerometer / altimeter / ext-flash / GPS / BLE MAC."""
        lines, err = self._cmd.send(
            "get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=timeout_s,
        )
        if err:
            return Sigma5ChipIds(), err

        joined = "\n".join(lines)
        result = Sigma5ChipIds()
        m = re.search(r"Accel chip ID:\s*(.+)", joined)
        if m:
            result.accel_id = m.group(1).strip()
        m = re.search(r"Altimeter chip ID:\s*(.+)", joined)
        if m:
            result.altimeter_id = m.group(1).strip()
        m = re.search(r"Ext flash chip ID:\s*(.+)", joined)
        if m:
            result.ext_flash_id = m.group(1).strip()
        m = re.search(r"GPS HW version:\s*(.+)", joined)
        if m:
            result.gps_hw_version = m.group(1).strip()
        m = re.search(r"BLE MAC:\s*(\S+)", joined)
        if m:
            result.ble_mac = m.group(1).strip()
        if not (result.accel_id or result.altimeter_id or result.ble_mac):
            return result, f"Failed to parse chip IDs from: {joined[:300]}"
        return result, None

    def get_ublox_version_info(
        self, timeout_s: float = 30.0
    ) -> Tuple[Sigma5UbloxInfo, Optional[str]]:
        """Query the u-blox HW/FW/SW/protocol versions + constellations."""
        lines, err = self._cmd.send(
            "get_ublox",
            success_patterns=["GPS constellations:"],
            timeout_s=timeout_s,
        )
        if err:
            return Sigma5UbloxInfo(), err

        joined = "\n".join(lines)
        result = Sigma5UbloxInfo()
        m = re.search(r"GPS HW version:\s*(.+)", joined)
        if m:
            result.hw_version = m.group(1).strip()
        m = re.search(r"GPS FW version:\s*(.+)", joined)
        if m:
            result.fw_version = m.group(1).strip()
        m = re.search(r"GPS SW version:\s*(.+)", joined)
        if m:
            result.sw_version = m.group(1).strip()
        m = re.search(r"GPS protocol version:\s*(.+)", joined)
        if m:
            result.proto_version = m.group(1).strip()
        m = re.search(r"GPS constellations:\s*(.+)", joined)
        if m:
            result.constellations = m.group(1).strip()
        if not (result.hw_version or result.fw_version):
            return result, f"Failed to parse u-blox info from: {joined[:300]}"
        return result, None

    def read_accel(
        self, timeout_s: float = 30.0
    ) -> Tuple[Sigma5AccelReading, Optional[str]]:
        """Read raw accelerometer values + temperature."""
        lines, err = self._cmd.send(
            "read_accel",
            success_patterns=["Accelerometer values"],
            timeout_s=timeout_s,
        )
        if err:
            return Sigma5AccelReading(), err

        joined = "\n".join(lines)
        m = re.search(
            r"Accelerometer values.*?:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)",
            joined,
        )
        if not m:
            return (
                Sigma5AccelReading(),
                f"Failed to parse accel from: {joined[:300]}",
            )
        try:
            return (
                Sigma5AccelReading(
                    x=float(m.group(1)),
                    y=float(m.group(2)),
                    z=float(m.group(3)),
                    temp_c=float(m.group(4)),
                ),
                None,
            )
        except ValueError as exc:
            return Sigma5AccelReading(), f"accel parse error: {exc}"

    def read_altimeter(
        self, timeout_s: float = 30.0
    ) -> Tuple[Sigma5AltimeterReading, Optional[str]]:
        """Read pressure + temperature from the altimeter."""
        lines, err = self._cmd.send(
            "read_alt",
            success_patterns=["Altimeter values"],
            timeout_s=timeout_s,
        )
        if err:
            return Sigma5AltimeterReading(), err

        joined = "\n".join(lines)
        m = re.search(
            r"Altimeter values.*?:\s*([-\d.]+),\s*([-\d.]+)",
            joined,
        )
        if not m:
            return (
                Sigma5AltimeterReading(),
                f"Failed to parse altimeter from: {joined[:300]}",
            )
        try:
            return (
                Sigma5AltimeterReading(
                    pressure_hg=float(m.group(1)),
                    temp_c=float(m.group(2)),
                ),
                None,
            )
        except ValueError as exc:
            return Sigma5AltimeterReading(), f"altimeter parse error: {exc}"

    # ── External flash ───────────────────────────────
    #
    # The nRF52840 app processor exposes three manufacturing-shell
    # commands for the SPI NOR ext-flash (see
    # ``sigma5_mfg_fw/src/app/sensor_handler.c`` for the firmware side):
    #
    #   write_ext_flash <addr> <base64>
    #       Decodes base64 into a 64-byte buffer, prints
    #       ``Writing %d bytes to address: 0x%x`` then a hexdump of
    #       the entire 64-byte buffer, then performs the flash write.
    #
    #   read_ext_flash  <addr> <n>
    #       Prints ``Reading %d bytes from address: 0x%x`` then a
    #       hexdump of n bytes (always rendered in 16-byte rows).
    #
    #   erase_ext_flash
    #       Erases the whole chip; prints ``Erasing flash. ... pages,
    #       ... bytes per page. Chip size ... bytes``.
    #
    # The bounds check on read_ext_flash logs ``Number of bytes (...)
    # must be ablt to fit in 64 bytes`` — the ``ablt`` typo is in the
    # firmware string; preserved here so the regression intent is
    # explicit and the test can pin both sides to the same string.

    def write_ext_flash(
        self,
        address: Union[int, str],
        data: Union[bytes, str],
        timeout_s: float = 15.0,
    ) -> Tuple[bool, Optional[str]]:
        """Write data to external flash.

        ``data`` accepts raw ``bytes`` (preferred — encoded internally)
        or an already-base64-encoded ``str`` (legacy contract). Raw
        bytes are b64-encoded before being put on the wire; passing
        bytes through an f-string ``f"...{data}"`` sends the Python
        ``b'\\xa5...'`` *repr* over UART, which the firmware base64
        decoder rejects with ``Base64 conversion to char array failed.
        Invalid argument``.

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
            f"write_ext_flash {hex_addr(address)} {data_b64}",
            success_patterns=["Writing", "bytes to address:"],
            timeout_s=timeout_s,
        )
        if err:
            return False, err
        # Firmware always emits the success line BEFORE the hexdump,
        # so its presence is a sufficient post-condition. ``Flash write
        # failed`` would have been the alternative — surface it as an
        # error if it ever appears.
        if any("Flash write failed" in l for l in lines):
            joined = "\n".join(lines)
            return False, f"Flash write failed: {joined[:300]}"
        return any("Writing" in l for l in lines), None

    def read_ext_flash(
        self,
        address: Union[int, str],
        num_bytes: int,
        timeout_s: float = 15.0,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """Read data from external flash.

        Returns the actual bytes the firmware reported, parsed from
        the hex dump it prints (``00000000: aa bb cc … |ascii|``).
        Returning bytes — not the hex string — lets callers compare
        directly against the bytes they wrote.

        The firmware always renders the hexdump in 16-byte rows even
        when fewer bytes were requested; the tail past ``num_bytes`` is
        zero-padding from the static buffer, NOT real flash content,
        so the parser slices down to ``num_bytes``.

        Returns:
            (data, error)
        """
        # success_patterns intentionally None: the firmware emits
        # ``Reading %d bytes from address: 0x%x`` BEFORE the underlying
        # SPI flash_read() runs, then the hex-dump, then the prompt.
        # Including "Reading" / "bytes from address" in success_patterns
        # arms ShellCommander.send()'s 3 s fallback the instant the
        # prologue lands — so when flash_read takes longer than 3 s
        # (the comms processor under LTE modem load hits this every
        # time; the app processor only on edge cases) ``send()``
        # returns BEFORE the hex-dump has been buffered. Waiting for
        # the prompt instead lets the full response settle first.
        lines, err = self._cmd.send(
            f"read_ext_flash {hex_addr(address)} {num_bytes}",
            success_patterns=None,
            timeout_s=timeout_s,
        )
        # If send() timed out but UART may still have buffered data,
        # do one last read so we don't lose the response just because
        # the prompt was slow to arrive.
        if err and not lines:
            time.sleep(1)
            text = self._cmd._stream.get_text()
            if text:
                lines = [l for l in text.splitlines() if l.strip()]
        if err and not lines:
            return None, err

        joined = "\n".join(lines)
        # Firmware error lines come back via shell_error and look the
        # same as any other output. Surface them as errors before we
        # try to parse a hex dump that won't exist.
        if "Flash read failed" in joined:
            return None, f"Flash read failed: {joined[:300]}"
        if "must be ablt to fit" in joined:
            return None, joined.strip()

        # Hex-dump shape:
        #   00000000: a5 5a ff 01 02 03 fe ed                          |.Z......        |
        # Strip the leading "<offset>:" column so the regex doesn't
        # mistake the offset for data and prepend 4 extra bytes to the
        # caller's payload.
        offset_re = re.compile(r"^\s*[0-9A-Fa-f]{4,8}\s*:\s*")
        hex_data = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            payload = stripped.split("|", 1)[0]  # drop ASCII sidebar
            payload = offset_re.sub("", payload).strip()
            if not payload:
                continue
            if re.fullmatch(r"(?:[0-9A-Fa-f]{2}\s*)+", payload):
                hex_data += re.sub(r"\s+", "", payload)

        if hex_data:
            try:
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
        used ``["Erasing flash", "pages", "Flash erase failed"]``, but
        the first two tokens match the firmware's *prologue* line
        (``shell_print("Erasing flash. %d pages, ...")``) emitted BEFORE
        the syscall runs — so ``send()``'s 3 s premature-success
        fallback fired ~3 s into the erase and reported success while
        the chip was still busy. The next shell command then raced the
        still-erasing chip and lost (run cmpnd4ifm on panel 0AW2,
        test_08 failures on all 5 slots). The ``Flash erase failed``
        error line is still detected from the captured ``lines`` after
        the prompt arrives. See
        ``shells/tests/test_read_ext_flash_cadence.py``.

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
