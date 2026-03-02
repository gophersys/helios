# Standard includes
import concurrent.futures
import logging
import os
import queue
import time
from typing import Dict, Iterator, List, Optional, Tuple, Any

# 3rd party includes
import grpc

# Protocol includes
from protocols.mtib.mtib_pb2 import (
    Empty,
    AdcReadRequest,
    AdcReadResponse,
    AccelReadResponse,
    DutPowerReadResponse,
    DutPowerRequest,
    DutPowerResponse,
    GpioConfigRequest,
    GpioConfigResponse,
    GpioDirection,
    GpioResistorConfig,
    GpioReadRequest,
    GpioReadResponse,
    GpioWriteRequest,
    GpioWriteResponse,
    HostType,
    FwFileInfo,
    UploadFwFileRequest,
    UploadFwFileResponse,
    ListFwFilesResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    UartStreamRequest,
    UartStreamResponse,
    EnableAppProtectRequest,
    EnableAppProtectResponse,
)
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub

# App includes
from tests.lib import *

# ---------------------------------------------------------------------------------
#                                                                    Test Constants
# -------------------------------------------------------------------------------*/

# ADC Channel Mapping for Theta Fixture
# TODO: Update these channel numbers to match actual MTIB hardware mapping
ADC_BATT_SYS = 1  # TP201: +BATT_SYS
ADC_SYS = 3  # TP202: +SYS
ADC_3V3 = 0  # TP301: +3.3V
ADC_VBCKP = 2  # TP607: +VBCKP

# UART targets
THETA_COMMS_UART_TARGET = HostType.HOST_TYPE_NRF9151
THETA_APP_UART_TARGET = HostType.HOST_TYPE_NRF52840

# mtib gRPC server port
MTIB_SERVICE_GRPC_SERVER_PORT = 50053


# ---------------------------------------------------------------------------------
#                                                                             Class
# -------------------------------------------------------------------------------*/
class ThetaMtibServers:
    def __init__(self):
        self.mtibs: Dict[str, MtibV1Stub] = {}
        self.channels: Dict[str, grpc.Channel] = {}

    def init(self, hosts: List[str]) -> str:
        errors = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._connect_mtib, host): host for host in hosts}
            for future in concurrent.futures.as_completed(futures):
                error = future.result()
                if error:
                    errors.append(error)

        if errors:
            return f"Errors occurred during mtib initialization: {', '.join(errors)}"

        return None

    def _connect_mtib(self, host: str) -> str:
        try:
            channel = grpc.insecure_channel(f"{host}:{MTIB_SERVICE_GRPC_SERVER_PORT}")
            self.channels[host] = channel

            stub = MtibV1Stub(channel)
            response = stub.HealthCheck(Empty(), timeout=5)

            self.mtibs[host] = stub

            logging.info(f"mtib at {host} connected successfully")
            return ""
        except grpc.RpcError as e:
            logging.error(f"Failed to connect to mtib at {host}. Error: {str(e.details())}")
            return f"Failed to connect to mtib at {host}. Error: {str(e.details())}"
        except Exception as e:
            logging.error(f"Unexpected error when connecting to mtib at {host}. Error: {str(e)}")
            return f"Unexpected error when connecting to mtib at {host}. Error: {str(e)}"

    def deinit(self) -> str:
        try:
            for host, channel in self.channels.items():
                channel.close()
                logging.info(f"mtib at {host} disconnected successfully")

            self.mtibs.clear()
            self.channels.clear()

            return ""
        except Exception as e:
            return f"An error occurred during deinitialization: {str(e)}"

    # ---------------------------------------------------------------------------------
    #                                                                    Power Control
    # -------------------------------------------------------------------------------*/
    def disable_power(self, host: str) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: DutPowerResponse = stub.DutPowerDisable(Empty())
            if not response.success:
                return f"DutPowerDisable Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to disable power for mtib at {host}. Error: {str(e.details())}"

    def disable_charge_power(self, host: str) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: DutPowerResponse = stub.DutChargePowerDisable(Empty())
            if not response.success:
                return f"DutChargePowerDisable Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to disable charge power for mtib at {host}. Error: {str(e.details())}"

    def enable_power(self, host: str, voltage: float) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: DutPowerResponse = stub.DutPowerEnable(DutPowerRequest(voltage_v=voltage))
            if not response.success:
                return f"DutPowerEnable Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to enable power for mtib at {host}. Error: {str(e.details())}"

    def enable_charge_power(self, host: str) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: DutPowerResponse = stub.DutChargePowerEnable(Empty())
            if not response.success:
                return f"DutChargePowerEnable Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to enable charge power for mtib at {host}. Error: {str(e.details())}"

    # ---------------------------------------------------------------------------------
    #                                                                       ADC Reads
    # -------------------------------------------------------------------------------*/
    def read_batt_sys(self, host: str) -> Tuple[str, Optional[float]]:
        return self._read_adc(host, ADC_BATT_SYS, "BATT_SYS")

    def read_sys(self, host: str) -> Tuple[str, Optional[float]]:
        return self._read_adc(host, ADC_SYS, "SYS")

    def read_3v3(self, host: str) -> Tuple[str, Optional[float]]:
        return self._read_adc(host, ADC_3V3, "3V3")

    def read_vbckp(self, host: str) -> Tuple[str, Optional[float]]:
        return self._read_adc(host, ADC_VBCKP, "VBCKP")

    def _read_adc(self, host: str, channel: int, name: str) -> Tuple[str, Optional[float]]:
        if host not in self.mtibs:
            return f"No mtib found for host {host}", None

        try:
            stub = self.mtibs[host]
            response: AdcReadResponse = stub.AdcRead(AdcReadRequest(channel=channel))
            if not response.success:
                return f"AdcRead Channel {channel} ({name}) Error: {response.message}", None
            return "", response.voltage_v
        except grpc.RpcError as e:
            return f"Failed to read {name} for mtib at {host}. Error: {str(e.details())}", None

    def read_current(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.mtibs:
            return f"No mtib found for host {host}", None

        try:
            stub = self.mtibs[host]
            response: DutPowerReadResponse = stub.DutPowerRead(Empty())
            if not response.success:
                return f"DutPowerRead Error: {response.message}", None
            return "", float(response.current_a)
        except grpc.RpcError as e:
            return f"Failed to read current for mtib at {host}. Error: {str(e.details())}", None

    def read_accelerometer(self, host: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        if host not in self.mtibs:
            return None, None, None, f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: AccelReadResponse = stub.AccelRead(Empty())
            if not response.success:
                return None, None, None, f"Failed to read accelerometer from MTIB. Error: {response.message}"
            return response.x_g, response.y_g, response.z_g, None
        except grpc.RpcError as e:
            return None, None, None, f"Failed to read accelerometer for mtib at {host}. Error: {str(e.details())}"

    # ---------------------------------------------------------------------------------
    #                                                                  Firmware Upload
    # -------------------------------------------------------------------------------*/
    def upload_fw_file(self, host: str, file_path: str, host_type: HostType) -> Optional[str]:
        try:
            file_name = os.path.basename(file_path)
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks

            def request_iterator():
                with open(file_path, "rb") as f:
                    first_chunk = True
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        if first_chunk:
                            request = UploadFwFileRequest()
                            request.name = file_name
                            request.target = host_type
                            request.content = chunk
                            yield request
                            first_chunk = False
                        else:
                            request = UploadFwFileRequest()
                            request.content = chunk
                            yield request

            try:
                stub = self.mtibs[host]
                response: UploadFwFileResponse = stub.UploadFwFile(request_iterator())
                if not response.success:
                    return f"UploadFwFile error: {response.message}"
                return None
            except grpc.RpcError as e:
                return f"gRPC error for UploadFwFile at {host}. Error: {str(e.details())}"

        except FileNotFoundError:
            return f"UploadFwFile error: File not found at {file_path}"
        except PermissionError:
            return f"UploadFwFile error: Permission denied reading file {file_path}"
        except Exception as e:
            return f"Unexpected error in UploadFwFile at {host}: {str(e)}"

    def delete_fw_file(self, host: str, filename: str, host_type: HostType) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]

            list_response: ListFwFilesResponse = stub.ListFwFiles(Empty())
            if not any(file_info.name == filename for file_info in list_response.files):
                return ""  # File doesn't exist, nothing to delete

            delete_response: DeleteFwFileResponse = stub.DeleteFwFile(
                DeleteFwFileRequest(file_info=FwFileInfo(name=filename, target=host_type))
            )
            if delete_response.success:
                logging.info(f"File {filename} deleted successfully")
                return ""
            else:
                return f"Failed to delete file {filename}: {delete_response.message}"
        except grpc.RpcError as e:
            return f"RPC Error: {str(e.details())}"
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def flash_fw_file(
        self, host: str, file_info: FwFileInfo, sector_erase: bool = False, recover: bool = False
    ) -> Tuple[Optional[int], Optional[str]]:
        if host not in self.mtibs:
            return None, f"No mtib stub found for host {host}"

        try:
            stub = self.mtibs[host]
            response: FlashFwFileResponse = stub.FlashFwFile(
                FlashFwFileRequest(file_info=file_info, sector_erase=sector_erase, recover=recover)
            )
            if not response.success:
                return None, f"FlashFwFile error: {response.message}"
            return response.time_ms, None
        except grpc.RpcError as e:
            return None, f"gRPC error for FlashFwFile at {host}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in FlashFwFile at {host}: {str(e)}"

    def enable_app_protect(self, host: str, target: HostType) -> Tuple[Optional[bool], Optional[str]]:
        if host not in self.mtibs:
            return None, f"No mtib stub found for host {host}"

        try:
            stub = self.mtibs[host]
            response: EnableAppProtectResponse = stub.EnableAppProtect(EnableAppProtectRequest(target=target))
            if not response.success:
                return None, f"EnableAppProtect error: {response.message}"
            return response.success, None
        except grpc.RpcError as e:
            return None, f"gRPC error for EnableAppProtect at {host}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in EnableAppProtect at {host}: {str(e)}"

    # ---------------------------------------------------------------------------------
    #                                                                   GPIO Control
    # -------------------------------------------------------------------------------*/
    def gpio_config(self, host: str, gpio: int, direction: GpioDirection, resistor: GpioResistorConfig) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: GpioConfigResponse = stub.GpioConfig(
                GpioConfigRequest(gpio=gpio, direction=direction, resistor=resistor)
            )
            if not response.success:
                return f"GpioConfig Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to configure GPIO {gpio} for mtib at {host}. Error: {str(e.details())}"

    def gpio_write(self, host: str, gpio: int, state: bool) -> str:
        if host not in self.mtibs:
            return f"No mtib found for host {host}"

        try:
            stub = self.mtibs[host]
            response: GpioWriteResponse = stub.GpioWrite(GpioWriteRequest(gpio=gpio, state=state))
            if not response.success:
                return f"GpioWrite Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to write GPIO {gpio} for mtib at {host}. Error: {str(e.details())}"

    # ---------------------------------------------------------------------------------
    #                                                              UART Stream Helper
    # -------------------------------------------------------------------------------*/
    def UartStream(
        self, host: str, target: HostType, request_iterator: Iterator[UartStreamRequest]
    ) -> Iterator[UartStreamResponse]:
        try:
            response_iterator = self.mtibs[host].UartStream(request_iterator)
            for response in response_iterator:
                yield response
        except grpc.RpcError as e:
            logging.error(f"gRPC error for UartStream at {host}. Error: {str(e.details())}")
            yield UartStreamResponse(success=False, message=f"gRPC error: {str(e.details())}", target=target)
        except Exception as e:
            logging.error(f"Unexpected error in UartStream at {host}: {str(e)}")
            yield UartStreamResponse(success=False, message=f"Unexpected error: {str(e)}", target=target)

    # ---------------------------------------------------------------------------------
    #                                                     Theta UART Command Helpers
    # -------------------------------------------------------------------------------*/
    def _send_uart_command(
        self, host: str, command: str, expected_responses: List[str], timeout: int = 10
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Send a UART command to the nRF9151 and wait for expected response patterns.

        Returns:
            Tuple of (full_response_text, error_string)
        """
        try:
            input_queue = queue.Queue()

            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"{command}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()

            for resp in self.UartStream(host, THETA_COMMS_UART_TARGET, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)

                    # Check if all expected response patterns are present
                    all_found = all(pattern in full_response for pattern in expected_responses)
                    if all_found:
                        # Look for prompt after the command to confirm completion
                        lines = full_response.split("\n")
                        command_found = False
                        prompt_found = False

                        for i, ln in enumerate(lines):
                            if command.split()[0] in ln:
                                command_found = True
                            elif command_found and "Mfg shell:" in ln.strip():
                                prompt_found = True
                                break

                        if prompt_found:
                            return full_response, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout waiting for response. Got: {full_response[:300]}..."

        except Exception as e:
            return None, f"Exception in UART command '{command}': {str(e)}"

    def theta_cmd_nop(self, host: str) -> Tuple[bool, Optional[str]]:
        """Send NOP command and verify board responds."""
        response, error = self._send_uart_command(host, "nop", ["nop: OK"])
        if error:
            return False, error
        return True, None

    def theta_cmd_get_battery(self, host: str) -> Tuple[Optional[float], Optional[str]]:
        """Query board for battery voltage reading."""
        response, error = self._send_uart_command(host, "get_battery", ["Battery voltage:"])
        if error:
            return None, error

        try:
            # Parse "Battery voltage: X.XXX V"
            voltage_start = response.find("Battery voltage:")
            if voltage_start == -1:
                return None, "Could not find battery voltage in response"

            voltage_line = response[voltage_start:]
            voltage_end = voltage_line.find("\n")
            if voltage_end != -1:
                voltage_line = voltage_line[:voltage_end]

            value_str = voltage_line.split(":")[1].strip().rstrip("V").strip()
            voltage = float(value_str)
            return voltage, None
        except (ValueError, IndexError) as e:
            return None, f"Failed to parse battery voltage: {e}"

    def theta_cmd_post(self, host: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        """
        Send POST command and parse results.
        Returns dict with chip IDs and flash test results.
        """
        response, error = self._send_uart_command(host, "post", ["POST result:"], timeout=30)
        if error:
            return None, error

        results = {}

        # Parse chip IDs
        for key in ["Accel chip ID", "Ext flash chip ID", "Modem chip ID"]:
            start = response.find(f"{key}:")
            if start != -1:
                line_end = response.find("\n", start)
                if line_end == -1:
                    line_end = len(response)
                value = response[start:line_end].split(":", 1)[1].strip()
                results[key] = value

        # Parse flash test result
        if "Flash test: PASS" in response:
            results["flash_test"] = "PASS"
        elif "Flash test: FAIL" in response:
            results["flash_test"] = "FAIL"

        # Parse overall POST result
        if "POST result: PASS" in response:
            results["post_result"] = "PASS"
        elif "POST result: FAIL" in response:
            results["post_result"] = "FAIL"

        return results, None

    def theta_cmd_get_imei_iccid(self, host: str) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Read IMEI and all ICCIDs from the modem."""
        response, error = self._send_uart_command(host, "imei_iccid", ["IMEI"], timeout=30)
        if error:
            return None, None, error

        imei = None
        iccids = []

        # Alpha format: "IMEI,ICCID0[,ICCID1]: value1,value2[,value3]"
        for line in response.split("\n"):
            if "IMEI" in line and ":" in line:
                values_part = line.split(":", 1)[1].strip()
                parts = [p.strip() for p in values_part.split(",") if p.strip()]
                if parts:
                    imei = parts[0]
                    iccids = parts[1:]
                break

        # Fallback: legacy format with separate "IMEI:" and "ICCID:" lines
        if not imei:
            imei_start = response.find("IMEI:")
            if imei_start != -1:
                imei_line_end = response.find("\n", imei_start)
                if imei_line_end == -1:
                    imei_line_end = len(response)
                imei = response[imei_start:imei_line_end].split(":", 1)[1].strip()

            idx = 0
            while True:
                iccid_start = response.find("ICCID:", idx)
                if iccid_start == -1:
                    break
                iccid_line_end = response.find("\n", iccid_start)
                if iccid_line_end == -1:
                    iccid_line_end = len(response)
                iccid = response[iccid_start:iccid_line_end].split(":", 1)[1].strip()
                if iccid:
                    iccids.append(iccid)
                idx = iccid_line_end + 1

        return imei, iccids, None

    def theta_cmd_read_accel(
        self, host: str
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read accelerometer X/Y/Z and temperature values."""
        response, error = self._send_uart_command(host, "read_accel", ["Accelerometer values:"])
        if error:
            return None, None, None, None, error

        try:
            accel_start = response.find("Accelerometer values:")
            if accel_start == -1:
                return None, None, None, None, "Could not find accelerometer values in response"

            accel_line = response[accel_start:]
            accel_line_end = accel_line.find("\n")
            if accel_line_end != -1:
                accel_line = accel_line[:accel_line_end]

            # Parse format: "Accelerometer values: (x, y, z, temp): X.XX, Y.YY, Z.ZZ, T.TT"
            values_part = accel_line.split(":", 1)[1].strip()
            if ":" in values_part:
                values_str = values_part.split(":", 1)[1].strip()
            else:
                values_str = values_part

            values = [float(v.strip()) for v in values_str.split(",")]
            if len(values) >= 4:
                return values[0], values[1], values[2], values[3], None
            elif len(values) == 3:
                return values[0], values[1], values[2], None, None
            else:
                return None, None, None, None, f"Expected at least 3 values, got {len(values)}"

        except (ValueError, IndexError) as e:
            return None, None, None, None, f"Failed to parse accelerometer values: {e}"

    def theta_cmd_hard_reset(self, host: str) -> Optional[str]:
        """Send hard reset command via UART. Does not wait for response (device will reset)."""
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"hard_reset\r")

            def request_iterator():
                try:
                    data = input_queue.get_nowait()
                    yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=data)
                except queue.Empty:
                    yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=b"")

                try:
                    data = input_queue.get_nowait()
                    yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=data)
                except queue.Empty:
                    yield UartStreamRequest(target=THETA_COMMS_UART_TARGET, data=b"")

            # Send the command - we don't wait for a response since the device will reset
            for resp in self.UartStream(host, THETA_COMMS_UART_TARGET, request_iterator()):
                break  # Just send the command and return

            return None
        except Exception as e:
            return f"Exception sending hard_reset: {str(e)}"

    def theta_cmd_lock_shell(self, host: str) -> Tuple[bool, Optional[str]]:
        """Lock shell to manufacturing mode."""
        response, error = self._send_uart_command(host, "lock_shell", ["Locking shell mode ON"], timeout=120)
        if error:
            return False, error
        return True, None

    def theta_cmd_debug_uart_disable(self, host: str) -> Tuple[bool, Optional[str]]:
        """Disable debug UART output."""
        response, error = self._send_uart_command(host, "debug_enable 0", ["Debug is not enabled"], timeout=60)
        if error:
            return False, error
        return True, None

    def theta_cmd_personalize(self, host: str, device_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Personalize device with given device ID.
        Returns (hex_key, base64_key, error)
        """
        response, error = self._send_uart_command(
            host, f"personalize {device_id}", ["Public key (base64)"], timeout=15
        )
        if error:
            return None, None, error

        hex_key = None
        base64_key = None

        # Parse line-by-line to handle variable whitespace in key labels
        for line in response.split("\n"):
            stripped = line.strip()
            if "Public key (hex)" in stripped and ":" in stripped:
                hex_key = stripped.split(":", 1)[1].strip()
            elif "Public key (base64)" in stripped and ":" in stripped:
                base64_key = stripped.split(":", 1)[1].strip()

        return hex_key, base64_key, None

    def theta_cmd_get_chip_ids(self, host: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get chip IDs from the comms processor (nRF9151).
        Returns (lora_available, ext_flash_id, error)
        """
        response, error = self._send_uart_command(host, "get_chip_ids", ["Ext flash chip ID:"], timeout=10)
        if error:
            return None, None, error

        lora_available = None
        ext_flash_id = None

        lora_start = response.find("LoRa hardware available:")
        if lora_start != -1:
            lora_line_end = response.find("\n", lora_start)
            if lora_line_end == -1:
                lora_line_end = len(response)
            lora_available = response[lora_start:lora_line_end].split(":", 1)[1].strip()

        flash_start = response.find("Ext flash chip ID:")
        if flash_start != -1:
            flash_line_end = response.find("\n", flash_start)
            if flash_line_end == -1:
                flash_line_end = len(response)
            ext_flash_id = response[flash_start:flash_line_end].split(":", 1)[1].strip()

        return lora_available, ext_flash_id, None

    def theta_cmd_get_modem_fw_version(self, host: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get modem firmware version from the comms processor.
        Returns (fw_version, error)
        """
        response, error = self._send_uart_command(host, "get_modem_fw", ["Modem FW:"], timeout=10)
        if error:
            return None, error

        modem_start = response.find("Modem FW:")
        if modem_start != -1:
            line_end = response.find("\n", modem_start)
            if line_end == -1:
                line_end = len(response)
            fw_version = response[modem_start:line_end].split(":", 1)[1].strip()
            return fw_version, None

        return None, "Could not find modem FW version in response"

    def theta_cmd_write_ext_flash(
        self, host: str, address: str, data_b64: str
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to comms processor external flash (data is base64 encoded)."""
        response, error = self._send_uart_command(
            host, f"write_ext_flash {address} {data_b64}", ["Writing"], timeout=10
        )
        if error:
            return False, error
        return True, None

    def theta_cmd_read_ext_flash(self, host: str, address: str, num_bytes: int) -> Tuple[Optional[str], Optional[str]]:
        """Read data from comms processor external flash. Returns hex data string."""
        response, error = self._send_uart_command(
            host, f"read_ext_flash {address} {num_bytes}", ["Reading"], timeout=10
        )
        if error:
            return None, error

        # Parse hex dump format: "addr: xx xx xx ... | ascii"
        hex_data = ""
        for line in response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")
        return hex_data, None

    def theta_cmd_erase_ext_flash(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Erase comms processor external flash."""
        response, error = self._send_uart_command(host, "erase_ext_flash", ["Erase complete", "erased"], timeout=30)
        if error:
            return False, error
        return True, None

    def theta_cmd_rekey_ipc(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Rekey IPC to replace hard coded keys with device-specific keys."""
        response, error = self._send_uart_command(host, "rekey_ipc", ["IPC rekey completed successfully"], timeout=10)
        if error:
            if "IPC rekey failed" in (response or ""):
                return False, "IPC rekey failed"
            return False, error
        return True, None

    # ---------------------------------------------------------------------------------
    #                                                    App Processor UART Commands
    # -------------------------------------------------------------------------------*/
    def _send_app_uart_command(
        self, host: str, command: str, expected_responses: List[str], timeout: int = 10
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Send a UART command to the nRF52840 app processor and wait for expected response patterns.
        """
        try:
            input_queue = queue.Queue()

            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"{command}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=THETA_APP_UART_TARGET, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=THETA_APP_UART_TARGET, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()

            for resp in self.UartStream(host, THETA_APP_UART_TARGET, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)

                    all_found = all(pattern in full_response for pattern in expected_responses)
                    if all_found:
                        lines = full_response.split("\n")
                        command_found = False
                        prompt_found = False

                        for i, ln in enumerate(lines):
                            if command.split()[0] in ln:
                                command_found = True
                            elif command_found and "Mfg shell:" in ln.strip():
                                prompt_found = True
                                break

                        if prompt_found:
                            return full_response, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout waiting for response. Got: {full_response[:300]}..."

        except Exception as e:
            return None, f"Exception in app UART command '{command}': {str(e)}"

    def theta_app_cmd_lock_shell(self, host: str) -> Tuple[bool, Optional[str]]:
        """Lock shell on app processor to manufacturing mode."""
        response, error = self._send_app_uart_command(
            host, "lock_shell", ["Locking shell mode ON"], timeout=30
        )
        if error:
            # Shell may already be locked — retry by checking if the prompt is still responsive
            return False, error
        return True, None

    def theta_app_cmd_debug_uart_disable(self, host: str) -> Tuple[bool, Optional[str]]:
        """Disable debug UART output on app processor."""
        response, error = self._send_app_uart_command(host, "debug_enable 0", ["Debug is not enabled"], timeout=10)
        if error:
            return False, error
        return True, None

    def theta_app_cmd_get_chip_ids(self, host: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get chip IDs from the app processor (nRF52840).
        Supports both legacy Theta (Accel/Altimeter) and Alpha (Ext flash/BLE MAC) responses.
        Returns (id_1, id_2, error)
        """
        # Send command and wait for prompt completion without requiring specific response patterns.
        # The _send_app_uart_command prompt detection will match once the command echo
        # and a subsequent "Mfg shell:" prompt are both found.
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"get_chip_ids\r")

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=THETA_APP_UART_TARGET, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=THETA_APP_UART_TARGET, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 10

            for resp in self.UartStream(host, THETA_APP_UART_TARGET, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)

                    # Check for prompt after command output
                    lines = full_response.split("\n")
                    command_found = False
                    prompt_found = False
                    for ln in lines:
                        if "get_chip_ids" in ln:
                            command_found = True
                        elif command_found and "Mfg shell:" in ln.strip():
                            prompt_found = True
                            break

                    if prompt_found:
                        # Alpha firmware format: Ext flash chip ID + BLE MAC
                        if "Ext flash chip ID:" in full_response or "BLE MAC:" in full_response:
                            ext_flash_id = None
                            ble_mac = None
                            for ln in lines:
                                if "Ext flash chip ID:" in ln:
                                    ext_flash_id = ln.split(":", 1)[1].strip()
                                elif "BLE MAC:" in ln:
                                    ble_mac = ln.split(":", 1)[1].strip()
                            return ext_flash_id, ble_mac, None

                        # Legacy Theta firmware format: Accel + Altimeter
                        if "Accel:" in full_response:
                            accel_id = None
                            alt_id = None
                            for ln in lines:
                                if "Accel:" in ln:
                                    accel_id = ln.split(":", 1)[1].strip()
                                elif "Altimeter" in ln and ":" in ln:
                                    alt_id = ln.split(":", 1)[1].strip()
                            return accel_id, alt_id, None

                        return None, None, f"Unrecognized response format: {full_response[:200]}..."

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception: {str(e)}"

    def theta_app_cmd_test_bms(self, host: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Test BMS (gas gauge) chip on the app processor.
        Returns (result_dict, error)
        """
        response, error = self._send_app_uart_command(host, "test_bms", ["BMS connected:", "Temperature:"], timeout=10)
        if error:
            return None, error

        result = {}
        for line in response.split("\n"):
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

    def theta_app_cmd_test_charger(self, host: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Test battery charger chip on the app processor.
        Returns (result_dict, error)
        """
        response, error = self._send_app_uart_command(
            host, "test_charger", ["Charger chip ID:", "Battery voltage:"], timeout=10
        )
        if error:
            return None, error

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
                except:
                    pass

        return result, None

    def theta_app_cmd_test_gps(self, host: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Test GPS (GNSS) module on the app processor.
        Returns (result_dict, error)
        """
        response, error = self._send_app_uart_command(host, "test_gps", ["GPS shutdown:", "GPS comms:"], timeout=10)
        if error:
            return None, error

        result = {}
        for line in response.split("\n"):
            if "GPS shutdown:" in line:
                result["shutdown"] = "yes" in line.lower()
            elif "GPS tracking:" in line:
                result["tracking"] = "yes" in line.lower()
            elif "GPS comms:" in line:
                result["comms_ok"] = "OK" in line

        return result, None

    def theta_app_cmd_write_ext_flash(
        self, host: str, address: str, data_b64: str
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to app processor external flash (data is base64 encoded)."""
        response, error = self._send_app_uart_command(
            host, f"write_ext_flash {address} {data_b64}", ["Writing"], timeout=10
        )
        if error:
            return False, error
        return True, None

    def theta_app_cmd_read_ext_flash(
        self, host: str, address: str, num_bytes: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from app processor external flash. Returns hex data string."""
        response, error = self._send_app_uart_command(
            host, f"read_ext_flash {address} {num_bytes}", ["Reading"], timeout=10
        )
        if error:
            return None, error

        hex_data = ""
        for line in response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")
        return hex_data, None

    def theta_app_cmd_erase_ext_flash(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Erase app processor external flash."""
        response, error = self._send_app_uart_command(
            host, "erase_ext_flash", ["Erase complete", "erased"], timeout=30
        )
        if error:
            return False, error
        return True, None


# Singleton instance
mtib_servers = ThetaMtibServers()
