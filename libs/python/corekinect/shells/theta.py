"""Theta app processor shell commands.

Usage:
    from corekinect.shells.theta import ThetaAppShell

    shell = ThetaAppShell(mtib_client)
    success, err = shell.lock_shell()
    id_1, id_2, err = shell.get_chip_ids()
"""

import queue
import re
import time
from typing import Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

from corekinect.shells._uart_cmd import send_uart_cmd


class ThetaAppShell:
    """Theta app processor shell commands."""

    def __init__(self, client):
        self._client = client
        self.logger = client.logger

    def lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell on theta app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="lock_shell",
            success_patterns=["Shell locked", "Locking shell mode ON"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Shell locked" in (response or "") or "Locking shell mode" in (response or ""), None

    def debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART on theta app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="debug_enable 0",
            success_patterns=["Debug disabled", "Debug output disabled", "Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return any(p in (response or "") for p in ["Debug disabled", "Debug output disabled", "Debug is not enabled"]), None

    def get_chip_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from theta app processor.

        Supports two firmware response formats:
        - Legacy (Theta): Returns accelerometer and altimeter chip IDs
        - Alpha: Returns external flash chip ID and BLE MAC address

        Returns:
            Tuple of (id_1, id_2, error_string) where:
                - Legacy: (accel_id, alt_id, error)
                - Alpha: (ext_flash_id, ble_mac, error)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="get_chip_ids",
            success_patterns=["BLE MAC:", "Accel:", "Ext flash chip ID:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = response or ""

        # Alpha firmware format
        if "Ext flash chip ID:" in full_response or "BLE MAC:" in full_response:
            ext_flash = re.search(r"Ext flash chip ID:\s*(.+)", full_response)
            ble_mac = re.search(r"BLE MAC:\s*(\S+)", full_response)
            return (
                ext_flash.group(1).strip() if ext_flash else None,
                ble_mac.group(1).strip() if ble_mac else None,
                None,
            )

        # Legacy Theta format
        if "Accel:" in full_response:
            accel = re.search(r"Accel:\s*(.+)", full_response)
            alt = re.search(r"Altimeter.*?:\s*(.+)", full_response)
            return (
                accel.group(1).strip() if accel else None,
                alt.group(1).strip() if alt else None,
                None,
            )

        return None, None, f"Unrecognized format: {full_response[:200]}"

    def read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read accelerometer from theta app processor.

        Returns:
            Tuple of (x_g, y_g, z_g, temp_c, error_string)
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
        match = re.search(r"Accelerometer values.*?:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4)), None
            except ValueError:
                pass
        return None, None, None, None, f"Failed to parse accel: {full_response[:200]}"

    def read_alt(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Read altimeter from theta app processor.

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
        match = re.search(r"Altimeter values.*?:\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), None
            except ValueError:
                pass
        return None, None, f"Failed to parse altimeter: {full_response[:200]}"

    def drone_test(
        self, timeout_ms: int = 10000
    ) -> Tuple[Optional[bool], Optional[int], Optional[int], Optional[str]]:
        """Run drone detection test on theta app processor.

        Args:
            timeout_ms: Test timeout in milliseconds

        Returns:
            Tuple of (success, detected_freq_hz, amplitude_mg, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command=f"drone_test {timeout_ms}",
            success_patterns=["Drone test", "Drone detection"],
            timeout_s=(timeout_ms / 1000) + 10,
        )
        if err:
            return None, None, None, err

        full_response = response or ""
        success = "PASS" in full_response or "detected" in full_response.lower()
        freq_match = re.search(r"(\d+\.?\d*)\s*Hz", full_response)
        amp_match = re.search(r"(\d+\.?\d*)\s*mg", full_response)

        return (
            success,
            int(float(freq_match.group(1))) if freq_match else None,
            int(float(amp_match.group(1))) if amp_match else None,
            None,
        )

    def meas_bat_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Measure battery voltage on theta app processor.

        Returns:
            Tuple of (voltage_v, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="meas_bat_voltage",
            success_patterns=["Battery voltage", "Voltage"],
            timeout_s=15,
        )
        if err:
            return None, err

        full_response = response or ""
        match = re.search(r"(?:Battery )?[Vv]oltage.*?:\s*([\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), None
            except ValueError:
                pass
        return None, f"Failed to parse voltage: {full_response[:200]}"

    def membrane_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Run complete membrane board test on theta app processor.

        Returns:
            Tuple of (results_dict, error_string)
            results_dict contains test results for: bme280, gpio_expander, leds, vibration
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="membrane_test",
            success_patterns=["Membrane test"],
            timeout_s=15,
        )
        if err:
            return None, err

        full_response = (response or "").lower()
        results = {}
        if "bme280" in full_response:
            results["bme280"] = "pass" in full_response or "ok" in full_response
        if "gpio" in full_response or "pca9536" in full_response:
            results["gpio_expander"] = "pass" in full_response or "ok" in full_response
        if "led" in full_response:
            results["leds"] = "pass" in full_response or "ok" in full_response
        if "vibration" in full_response or "motor" in full_response:
            results["vibration"] = "pass" in full_response or "ok" in full_response

        return results, None

    def env_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read BME280 environmental sensors on theta app processor.

        Returns:
            Tuple of (readings_dict, error_string)
            readings_dict contains: temperature_c, humidity_pct, pressure_pa
        """
        response, err = send_uart_cmd(
            self._client,
            target=HostType.HOST_TYPE_NRF52840,
            command="env_test",
            success_patterns=["Temperature", "Humidity", "Pressure"],
            timeout_s=15,
        )
        if err:
            return None, err

        full_response = response or ""
        readings = {}

        temp_match = re.search(r"Temperature.*?:\s*([-\d.]+)", full_response)
        if temp_match:
            readings["temperature_c"] = float(temp_match.group(1))

        humidity_match = re.search(r"Humidity.*?:\s*([-\d.]+)", full_response)
        if humidity_match:
            readings["humidity_pct"] = float(humidity_match.group(1))

        pressure_match = re.search(r"Pressure.*?:\s*([-\d.]+)", full_response)
        if pressure_match:
            readings["pressure_pa"] = float(pressure_match.group(1))

        if readings:
            return readings, None
        return None, f"Failed to parse env data: {full_response[:200]}"

    def vib_test(self, duration_ms: int = 200) -> Tuple[Optional[bool], Optional[str]]:
        """Test vibration motor on theta app processor

        Args:
            duration_ms: Vibration duration in milliseconds (default 200ms, max 2000ms)

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"vib_test {duration_ms}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = (duration_ms / 1000) + 5

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if ("Vibration" in full_response or "Motor" in full_response) and "Mfg shell:" in full_response:
                        return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def gps_status(self) -> Tuple[Optional[dict], Optional[str]]:
        """Get GPS status from theta app processor

        Returns:
            Tuple of (status_dict, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"gps status\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "GPS" in full_response and "Mfg shell:" in full_response:
                        status = {}
                        for line in full_response.split("\n"):
                            if ":" in line and not line.strip().startswith("Mfg shell:"):
                                try:
                                    key, value = line.split(":", 1)
                                    status[key.strip().lower().replace(" ", "_")] = value.strip()
                                except ValueError:
                                    pass
                        return status, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def gps_start(self) -> Tuple[Optional[bool], Optional[str]]:
        """Start GPS tracking on theta app processor

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"gps start\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "GPS started" in full_response
                        or "GPS tracking started" in full_response
                        or "Starting GPS" in full_response
                    ) and "Mfg shell:" in full_response:
                        return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def gps_stop(self) -> Tuple[Optional[bool], Optional[str]]:
        """Stop GPS tracking on theta app processor

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"gps stop\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "GPS stopped" in full_response
                        or "GPS tracking stopped" in full_response
                        or "Stopping GPS" in full_response
                    ) and "Mfg shell:" in full_response:
                        return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def get_ublox(self) -> Tuple[Optional[dict], Optional[str]]:
        """Get u-blox GPS info from theta app processor

        Returns:
            Tuple of (info_dict, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"get_ublox\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "u-blox" in full_response.lower() or "ublox" in full_response.lower()
                    ) and "Mfg shell:" in full_response:
                        info = {}
                        for line in full_response.split("\n"):
                            if ":" in line and not line.strip().startswith("Mfg shell:"):
                                try:
                                    key, value = line.split(":", 1)
                                    info[key.strip().lower().replace(" ", "_")] = value.strip()
                                except ValueError:
                                    pass
                        return info, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def set_gps_power(self, enable: bool) -> Tuple[Optional[bool], Optional[str]]:
        """Set GPS power state on theta app processor

        Args:
            enable: True to enable GPS power, False to disable

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            power_val = "1" if enable else "0"
            input_queue.put(f"set_gps_power {power_val}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "GPS power" in full_response and "Mfg shell:" in full_response:
                        return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def test_ble(self) -> Tuple[Optional[bool], Optional[str]]:
        """Test BLE advertising on theta app processor

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"test_ble\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "BLE" in full_response and (
                        "started" in full_response.lower()
                        or "success" in full_response.lower()
                        or "ok" in full_response.lower()
                    ):
                        if "Mfg shell:" in full_response:
                            return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def test_bms(self) -> Tuple[Optional[dict], Optional[str]]:
        """Test BMS (gas gauge) chip on theta app processor

        Returns:
            Tuple of (bms_data_dict, error_string)
            bms_data_dict contains: connected, chip_id, charge_percent, capacity_mah, temp_c
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"test_bms\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    # Wait for Temperature: (last field) to ensure complete response
                    if "BMS connected:" in full_response and "Temperature:" in full_response:
                        result = {}
                        for line in full_response.split("\n"):
                            if "BMS connected:" in line:
                                result["connected"] = "yes" in line.lower()
                            elif "BMS chip ID:" in line:
                                result["chip_id"] = line.split(":", 1)[1].strip()
                            elif "Charge:" in line:
                                try:
                                    result["charge_percent"] = int(line.split(":")[1].strip().replace("%", ""))
                                except:
                                    pass
                            elif "Capacity:" in line:
                                try:
                                    result["capacity_mah"] = int(line.split(":")[1].strip().split()[0])
                                except:
                                    pass
                            elif "Temperature:" in line:
                                try:
                                    result["temp_c"] = int(line.split(":")[1].strip().split()[0])
                                except:
                                    pass
                        return result, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def test_charger(self) -> Tuple[Optional[dict], Optional[str]]:
        """Test battery charger chip on theta app processor

        Returns:
            Tuple of (charger_data_dict, error_string)
            charger_data_dict contains: chip_id, on_charger, charging, charge_done, voltage_mv
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"test_charger\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    # Wait for Battery voltage: (last field) to ensure complete response
                    if "Charger chip ID:" in full_response and "Battery voltage:" in full_response:
                        result = {}
                        for line in full_response.split("\n"):
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
                                except:
                                    pass
                        return result, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def test_gps(self) -> Tuple[Optional[dict], Optional[str]]:
        """Test GPS (GNSS) module on theta app processor

        Returns:
            Tuple of (gps_data_dict, error_string)
            gps_data_dict contains: shutdown, tracking, comms_ok
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"test_gps\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    # Wait for GPS comms: (last field) to ensure complete response
                    if "GPS shutdown:" in full_response and "GPS comms:" in full_response:
                        result = {}
                        for line in full_response.split("\n"):
                            if "GPS shutdown:" in line:
                                result["shutdown"] = "yes" in line.lower()
                            elif "GPS tracking:" in line:
                                result["tracking"] = "yes" in line.lower()
                            elif "GPS comms:" in line:
                                result["comms_ok"] = "OK" in line
                        return result, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def read_ext_flash(
        self, address: str, num_bytes: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from app processor external flash

        Args:
            address: The address to read from
            num_bytes: The number of bytes to read
        Returns:
            Tuple of (hex_data, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"read_ext_flash {address} {num_bytes}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Reading" in full_response and "bytes from address:" in full_response:
                        lines = full_response.split("\n")
                        read_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "read_ext_flash" in line:
                                read_command_found = True
                            elif read_command_found and "Mfg shell:" in line.strip():
                                prompt_found = True
                                break

                        if prompt_found:
                            hex_data = ""
                            lines = full_response.split("\n")
                            for line in lines:
                                if ":" in line and "|" in line:
                                    hex_part = line.split("|")[0].strip()
                                    if ":" in hex_part:
                                        hex_values = hex_part.split(":", 1)[1].strip()
                                        hex_data += hex_values.replace(" ", "")
                            return hex_data, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in read_ext_flash: {str(e)}"

    def write_ext_flash(
        self, address: str, data: str
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to app processor external flash (data should be base64 encoded)

        Args:
            address: The address to write to
            data: The data to write (base64 encoded)
        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"write_ext_flash {address} {data}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        cmd_data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=cmd_data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Writing" in full_response and "bytes to address:" in full_response:
                        lines = full_response.split("\n")
                        write_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "write_ext_flash" in line:
                                write_command_found = True
                            elif write_command_found and "Mfg shell:" in line.strip():
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return False, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in write_ext_flash: {str(e)}"

    def erase_ext_flash(self) -> Tuple[Optional[bool], Optional[str]]:
        """Erase app processor external flash

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"erase_ext_flash\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30  # Erase can take longer

            for resp in self._client.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Erasing flash" in full_response and "pages" in full_response:
                        lines = full_response.split("\n")
                        erase_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "erase_ext_flash" in line:
                                erase_command_found = True
                            elif erase_command_found and "Mfg shell:" in line.strip():
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return False, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in erase_ext_flash: {str(e)}"
