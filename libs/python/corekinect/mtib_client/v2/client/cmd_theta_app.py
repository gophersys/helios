"""Theta app processor (nRF52840) shell commands for V2 MTIB client.

Provides manufacturing shell commands for the Theta application processor.
Each method opens a UART session, sends a command, parses the response,
and returns a Go-style (value, error) tuple.
"""

import re
from typing import Optional, Tuple

from .shell import (
    ShellCommandHelper,
    parse_key_value,
    parse_numeric_value,
    LOCK_SHELL_TIMEOUT,
)


class ThetaAppShellCommands:
    """Shell commands for the Theta app processor (nRF52840).

    Args:
        client: Connected MtibV2Client instance.
        port_name: UART port name (default "uart0").
    """

    TARGET_ID = "nrf52840"

    def __init__(self, client, port_name: str = "uart0"):
        self.client = client
        self.port_name = port_name

    def _shell(self) -> ShellCommandHelper:
        return ShellCommandHelper(
            self.client,
            target_id=self.TARGET_ID,
            port_name=self.port_name,
        )

    def lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock the manufacturing shell.

        Returns:
            (success, error) tuple.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command(
                "lock_shell",
                timeout=LOCK_SHELL_TIMEOUT,
                completion_marker="Shell locked",
            )
            if err and response:
                if "Shell locked" in response or "Locking shell mode" in response:
                    return True, None
            if err:
                return None, err
            if response and ("Shell locked" in response or "Locking shell mode" in response):
                return True, None
            return None, f"Unexpected response: {response[:200] if response else 'None'}"
        finally:
            shell.close()

    def debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART output.

        Returns:
            (success, error) tuple.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command("debug_enable 0")
            if err:
                return None, err
            if response and (
                "Debug disabled" in response
                or "Debug output disabled" in response
                or "Debug is not enabled" in response
            ):
                return True, None
            return None, f"Unexpected response: {response[:200] if response else 'None'}"
        finally:
            shell.close()

    def get_chip_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the theta app processor.

        Returns:
            (id_1, id_2, error) tuple.
            For Theta: id_1=accelerometer, id_2=altimeter chip IDs.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command("get_chip_ids")
            if err:
                return None, None, err

            id_1 = parse_key_value(response, "Accelerometer chip ID")
            id_2 = parse_key_value(response, "Altimeter chip ID")

            # Also try Alpha-style format
            if id_1 is None:
                id_1 = parse_key_value(response, "Ext flash chip ID")
            if id_2 is None:
                id_2 = parse_key_value(response, "BLE MAC")

            if id_1 is None and id_2 is None:
                return None, None, f"Could not parse chip IDs from: {response[:200]}"

            return id_1, id_2, None
        finally:
            shell.close()

    def env_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read BME280 environmental sensors.

        Returns:
            (readings_dict, error) tuple.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command("env_test")
            if err:
                return None, err

            readings = {}
            temp = parse_numeric_value(response, "Temperature")
            humidity = parse_numeric_value(response, "Humidity")
            pressure = parse_numeric_value(response, "Pressure")

            if temp is not None:
                readings["temperature_c"] = temp
            if humidity is not None:
                readings["humidity_pct"] = humidity
            if pressure is not None:
                readings["pressure_pa"] = pressure

            if not readings:
                return None, f"Could not parse env readings from: {response[:200]}"

            return readings, None
        finally:
            shell.close()

    def meas_bat_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Measure battery voltage.

        Returns:
            (voltage_v, error) tuple.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command("meas_bat_voltage")
            if err:
                return None, err

            voltage = parse_numeric_value(response, "Battery voltage")
            if voltage is None:
                voltage = parse_numeric_value(response, "Voltage")
            if voltage is None:
                for line in response.split("\n"):
                    match = re.search(r"(\d+\.\d+)\s*[Vv]", line)
                    if match:
                        voltage = float(match.group(1))
                        break

            if voltage is None:
                return None, f"Could not parse voltage from: {response[:200]}"

            return voltage, None
        finally:
            shell.close()

    def read_accel(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read accelerometer.

        Returns:
            (accel_dict, error) tuple.
        """
        shell = self._shell()
        try:
            err, response = shell.send_command("read_accel")
            if err:
                return None, err

            readings = {}
            for axis in ["X", "Y", "Z"]:
                val = parse_numeric_value(response, axis)
                if val is not None:
                    readings[f"{axis.lower()}_g"] = val

            if not readings:
                return None, f"Could not parse accel data from: {response[:200]}"

            return readings, None
        finally:
            shell.close()
