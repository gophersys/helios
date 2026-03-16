"""Sigma5 app processor shell commands.

Usage:
    from corekinect.shells.sigma5 import Sigma5AppShell

    shell = Sigma5AppShell(mtib_client)
    success, err = shell.lock_shell()
    accel_id, alt_id, flash_id, gps_hw, ble_mac, err = shell.get_chip_ids()
"""

import re
from typing import Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells._uart_cmd import send_uart_cmd


class Sigma5AppShell:
    """Sigma5 app processor shell commands."""

    def __init__(self, client):
        self._client = client
        self.logger = client.logger

    def lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode for the Sigma5 app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="lock_shell",
            success_patterns=["Locking shell mode ON"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Locking shell mode ON" in (response or ""), None

    def debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART for the Sigma5 app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="debug_enable 0",
            success_patterns=["Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Debug is not enabled" in (response or ""), None

    def get_chip_ids(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Sigma5 app processor.

        Returns:
            Tuple of (accel_id, altimeter_id, ext_flash_id, gps_hw_version, ble_mac, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, None, err

        full_response = response or ""

        # Parse each field with regex
        accel_match = re.search(r"Accel chip ID:\s*(.+)", full_response)
        alt_match = re.search(r"Altimeter chip ID:\s*(.+)", full_response)
        flash_match = re.search(r"Ext flash chip ID:\s*(.+)", full_response)
        gps_match = re.search(r"GPS HW version:\s*(.+)", full_response)
        ble_match = re.search(r"BLE MAC:\s*(\S+)", full_response)

        return (
            accel_match.group(1).strip() if accel_match else None,
            alt_match.group(1).strip() if alt_match else None,
            flash_match.group(1).strip() if flash_match else None,
            gps_match.group(1).strip() if gps_match else None,
            ble_match.group(1).strip() if ble_match else None,
            None,
        )

    def get_ublox_version_info(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get ublox version info from the Sigma5 app processor.

        Returns:
            Tuple of (hw_version, fw_version, sw_version, proto_version, constellations, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="get_ublox",
            success_patterns=["GPS constellations:"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, None, err

        full_response = response or ""

        hw_match = re.search(r"GPS HW version:\s*(.+)", full_response)
        fw_match = re.search(r"GPS FW version:\s*(.+)", full_response)
        sw_match = re.search(r"GPS SW version:\s*(.+)", full_response)
        proto_match = re.search(r"GPS protocol version:\s*(.+)", full_response)
        const_match = re.search(r"GPS constellations:\s*(.+)", full_response)

        return (
            hw_match.group(1).strip() if hw_match else None,
            fw_match.group(1).strip() if fw_match else None,
            sw_match.group(1).strip() if sw_match else None,
            proto_match.group(1).strip() if proto_match else None,
            const_match.group(1).strip() if const_match else None,
            None,
        )

    def read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Get accelerometer values from the Sigma5 app processor.

        Returns:
            Tuple of (x_raw, y_raw, z_raw, temp, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="read_accel",
            success_patterns=["Accelerometer values"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, err

        full_response = response or ""
        # Parse format: "Accelerometer values: (x, y, z, temp): 0.890625, -0.015625, 0.437500, 31.000000"
        match = re.search(r"Accelerometer values.*?:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4)), None
            except ValueError:
                pass
        return None, None, None, None, f"Failed to parse accel from: {full_response[:200]}"

    def read_altimeter(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Get altimeter values from the Sigma5 app processor.

        Returns:
            Tuple of (pressure_hg, temperature_c, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="read_alt",
            success_patterns=["Altimeter values"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = response or ""
        # Parse format: "Altimeter values (pressure, temp): 28.722524, 25.412672"
        match = re.search(r"Altimeter values.*?:\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), None
            except ValueError:
                pass
        return None, None, f"Failed to parse altimeter from: {full_response[:200]}"
