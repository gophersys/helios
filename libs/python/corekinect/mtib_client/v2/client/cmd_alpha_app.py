"""Alpha app processor (nRF52840) shell commands for V2 MTIB client.

Provides manufacturing shell commands for the Alpha B0 application processor.
Each method sends a command on an existing shell session and parses the
response, returning a Go-style (value, error) tuple.

Shell sessions must be initialized via boot_and_lock_shells() before
calling these methods, which provides a locked ShellCommandHelper.
"""

import re
from typing import Dict, Optional, Tuple

from .shell import ShellCommandHelper, parse_key_value, parse_numeric_value


class AlphaAppShellCommands:
    """Shell commands for the Alpha app processor (nRF52840).

    Args:
        shell: A locked ShellCommandHelper for the app proc UART.
    """

    def __init__(self, shell: ShellCommandHelper):
        self.shell = shell

    def get_chip_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the app processor.

        Alpha firmware returns external flash chip ID and BLE MAC address.

        Returns:
            (ext_flash_id, ble_mac, error) tuple.
        """
        err, response = self.shell.send_command("get_chip_ids")
        if err:
            return None, None, err

        ext_flash_id = parse_key_value(response, "Ext flash chip ID")
        ble_mac = parse_key_value(response, "BLE MAC")

        if ext_flash_id is None:
            ext_flash_id = parse_key_value(response, "ext_flash")
        if ble_mac is None:
            ble_mac = parse_key_value(response, "ble_mac")

        if ext_flash_id is None and ble_mac is None:
            return None, None, f"Could not parse chip IDs from: {response[:200]}"

        return ext_flash_id, ble_mac, None

    def env_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read BME280 environmental sensors.

        Returns:
            (readings_dict, error) tuple.
            readings_dict contains: temperature_c, humidity_pct, pressure_pa
        """
        err, response = self.shell.send_command("env_test")
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

    def meas_bat_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Measure battery voltage.

        Returns:
            (voltage_v, error) tuple.
        """
        err, response = self.shell.send_command("meas_bat_voltage")
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

    def read_accel(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read accelerometer data.

        Returns:
            (accel_dict, error) tuple.
            accel_dict contains: x_g, y_g, z_g
        """
        err, response = self.shell.send_command("read_accel")
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

    def test_bms(self) -> Tuple[Optional[Dict], Optional[str]]:
        """Test BMS (gas gauge) chip.

        Returns:
            (result_dict, error) tuple.
            result_dict contains: connected, chip_id, charge_percent, capacity_mah, temp_c
        """
        err, response = self.shell.send_command("test_bms")
        if err:
            return None, err

        result = {}
        for line in response.split("\n"):
            if "BMS connected:" in line:
                result["connected"] = "yes" in line.lower()
            elif "BMS chip ID:" in line:
                result["chip_id"] = line.split(":", 1)[1].strip()
            elif "Charge:" in line:
                try:
                    result["charge_percent"] = int(line.split(":")[1].strip().replace("%", ""))
                except (ValueError, IndexError):
                    pass
            elif "Capacity:" in line:
                try:
                    result["capacity_mah"] = int(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif "Temperature:" in line:
                try:
                    result["temp_c"] = int(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

        if not result:
            return None, f"Could not parse BMS data from: {response[:200]}"

        return result, None

    def test_charger(self) -> Tuple[Optional[Dict], Optional[str]]:
        """Test battery charger chip.

        Returns:
            (result_dict, error) tuple.
            result_dict contains: chip_id, on_charger, charging, charge_done, voltage_mv
        """
        err, response = self.shell.send_command("test_charger")
        if err:
            return None, err

        result = {}
        for line in response.split("\n"):
            if "Charger chip ID:" in line:
                result["chip_id"] = line.split(":", 1)[1].strip().split()[0]
            elif "On charger:" in line:
                result["on_charger"] = "yes" in line.lower()
            elif "Charging:" in line and "On" not in line:
                result["charging"] = "yes" in line.lower()
            elif "Charge done:" in line:
                result["charge_done"] = "yes" in line.lower()
            elif "Battery voltage:" in line:
                try:
                    result["voltage_mv"] = int(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

        if not result:
            return None, f"Could not parse charger data from: {response[:200]}"

        return result, None

    def test_gps(self) -> Tuple[Optional[Dict], Optional[str]]:
        """Test GPS (GNSS) module.

        Returns:
            (result_dict, error) tuple.
            result_dict contains: shutdown, tracking, comms_ok
        """
        err, response = self.shell.send_command("test_gps")
        if err:
            return None, err

        result = {}
        for line in response.split("\n"):
            if "GPS shutdown:" in line:
                result["shutdown"] = "yes" in line.lower()
            elif "GPS tracking:" in line:
                result["tracking"] = "yes" in line.lower()
            elif "GPS comms:" in line:
                result["comms_ok"] = "OK" in line

        if not result:
            return None, f"Could not parse GPS data from: {response[:200]}"

        return result, None

    def write_ext_flash(self, address: str, data_b64: str) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to external flash (data is base64 encoded).

        Returns:
            (success, error) tuple.
        """
        err, response = self.shell.send_command(f"write_ext_flash {address} {data_b64}")
        if err:
            return False, err
        return True, None

    def read_ext_flash(self, address: str, num_bytes: int) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash. Returns hex data string.

        Returns:
            (hex_data, error) tuple.
        """
        err, response = self.shell.send_command(f"read_ext_flash {address} {num_bytes}")
        if err:
            return None, err

        hex_data = ""
        for line in response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")
        return hex_data, None

    def erase_ext_flash(self) -> Tuple[Optional[bool], Optional[str]]:
        """Erase external flash.

        Returns:
            (success, error) tuple.
        """
        err, response = self.shell.send_command("erase_ext_flash", timeout=30.0)
        if err:
            if response and ("Erase complete" in response or "erased" in response):
                return True, None
            return False, err
        return True, None
