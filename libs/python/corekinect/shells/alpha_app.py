"""Alpha nRF52840 application processor shell commands.

Usage:
    from corekinect.shells.alpha_app import AlphaAppShell

    app = AlphaAppShell(mtib_client)
    app.lock()
    app.debug_off()

    ids = app.get_chip_ids()
    print(f"BLE MAC: {ids.ble_mac}")

    bms = app.test_bms()
    print(f"BMS connected: {bms.connected}")
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells.base import ShellCommander


# ── Result types ─────────────────────────────────────────

@dataclass
class ChipIds:
    """Result from get_chip_ids on nRF52840."""
    ext_flash_id: Optional[str] = None
    ble_mac: Optional[str] = None


@dataclass
class BmsStatus:
    """Result from test_bms."""
    connected: bool = False
    chip_id: Optional[str] = None
    charge_percent: Optional[int] = None
    capacity_mah: Optional[int] = None
    temperature_c: Optional[int] = None


@dataclass
class ChargerStatus:
    """Result from test_charger."""
    chip_id: Optional[str] = None
    chip_id_error: Optional[int] = None
    on_charger: bool = False
    charging: bool = False
    charge_done: bool = False
    battery_voltage_mv: Optional[int] = None


@dataclass
class GpsStatus:
    """Result from test_gps."""
    in_shutdown: bool = True
    tracking: bool = False
    comms_ok: bool = False


@dataclass
class ExtFlashResult:
    """Result from test_ext_flash."""
    write_ok: bool = False
    read_ok: bool = False
    data_match: bool = False


# ── Shell interface ──────────────────────────────────────

class AlphaAppShell:
    """nRF52840 application processor manufacturing shell.

    Args:
        mtib: Connected MtibV1Client instance.
    """

    TARGET = HostType.HOST_TYPE_NRF52840

    def __init__(self, mtib):
        self._cmd = ShellCommander(mtib, self.TARGET, label="APP")

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

    # ── Hardware tests ───────────────────────────────

    def get_chip_ids(self, timeout_s: float = 30.0) -> Tuple[ChipIds, Optional[str]]:
        """Get external flash ID and BLE MAC address.

        Returns:
            (ChipIds, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=timeout_s,
        )
        if err:
            return ChipIds(), err

        result = ChipIds()
        for line in lines:
            m = re.search(r"Ext flash chip ID:\s*(.+)", line)
            if m:
                result.ext_flash_id = m.group(1).strip()
            m = re.search(r"BLE MAC:\s*(\S+)", line)
            if m:
                result.ble_mac = m.group(1).strip()

        if result.ext_flash_id or result.ble_mac:
            return result, None
        return result, f"Failed to parse chip IDs from: {lines}"

    def test_bms(self, timeout_s: float = 30.0) -> Tuple[BmsStatus, Optional[str]]:
        """Test BMS (gas gauge) chip.

        Returns:
            (BmsStatus, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "test_bms",
            success_patterns=["BMS connected:", "Temperature:"],
            timeout_s=timeout_s,
        )
        if err:
            return BmsStatus(), err

        result = BmsStatus()
        joined = "\n".join(lines)

        result.connected = "BMS connected: yes" in joined

        m = re.search(r"BMS chip ID:\s*(0x[0-9a-fA-F]+)", joined)
        if m:
            result.chip_id = m.group(1)

        m = re.search(r"Charge:\s*(\d+)%", joined)
        if m:
            result.charge_percent = int(m.group(1))

        m = re.search(r"Capacity:\s*(\d+)\s*mAh", joined)
        if m:
            result.capacity_mah = int(m.group(1))

        m = re.search(r"Temperature:\s*(-?\d+)\s*C", joined)
        if m:
            result.temperature_c = int(m.group(1))

        return result, None

    def test_charger(self, timeout_s: float = 30.0) -> Tuple[ChargerStatus, Optional[str]]:
        """Test battery charger (BQ25180) chip.

        Returns:
            (ChargerStatus, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "test_charger",
            success_patterns=["Battery voltage:"],
            timeout_s=timeout_s,
        )
        if err:
            return ChargerStatus(), err

        result = ChargerStatus()
        joined = "\n".join(lines)

        m = re.search(r"Charger chip ID:\s*(0x[0-9a-fA-F]+)\s*\(err:\s*(-?\d+)\)", joined)
        if m:
            result.chip_id = m.group(1)
            result.chip_id_error = int(m.group(2))

        result.on_charger = "On charger: yes" in joined
        result.charging = "Charging: yes" in joined
        result.charge_done = "Charge done: yes" in joined

        m = re.search(r"Battery voltage:\s*(\d+)\s*mV", joined)
        if m:
            result.battery_voltage_mv = int(m.group(1))

        return result, None

    def test_gps(self, timeout_s: float = 30.0) -> Tuple[GpsStatus, Optional[str]]:
        """Test GPS (GNSS) module.

        Returns:
            (GpsStatus, error) — error is None on success.
        """
        lines, err = self._cmd.send(
            "test_gps",
            success_patterns=["GPS comms:"],
            timeout_s=timeout_s,
        )
        if err:
            return GpsStatus(), err

        result = GpsStatus()
        joined = "\n".join(lines)

        result.in_shutdown = "GPS shutdown: yes" in joined
        result.tracking = "GPS tracking: yes" in joined
        result.comms_ok = "GPS comms: OK" in joined

        return result, None

    def test_ext_flash(self, timeout_s: float = 30.0) -> Tuple[ExtFlashResult, Optional[str]]:
        """Write/read/verify external flash.

        Returns:
            (ExtFlashResult, error) — error is None on success.
        """
        result = ExtFlashResult()
        test_data = base64.b64encode(b"POST_TEST").decode("ascii")
        test_addr = "0x100000"

        # Write
        lines, err = self._cmd.send(
            f"write_ext_flash {test_addr} {test_data}",
            success_patterns=["Writing", "Mfg shell:"],
            timeout_s=timeout_s,
        )
        if err:
            return result, err
        result.write_ok = any("Writing" in l or "Mfg shell:" in l for l in lines)

        if not result.write_ok:
            return result, f"Write failed: {lines}"

        # Read back
        lines, err = self._cmd.send(
            f"read_ext_flash {test_addr} 9",
            success_patterns=["Reading", "Mfg shell:"],
            timeout_s=timeout_s,
        )
        if err:
            return result, err

        joined = "\n".join(lines)
        result.read_ok = bool(lines)
        if "504F53545F54455354" in joined.upper().replace(" ", "") or "POST_TEST" in joined:
            result.data_match = True

        return result, None
