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

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells.base import ShellCommander


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
