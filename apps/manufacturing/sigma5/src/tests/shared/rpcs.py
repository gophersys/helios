# Standard includes
import asyncio
import concurrent.futures
import hashlib
import os
import socket
import struct
from token import OP
import zlib
from dataclasses import dataclass
from time import sleep
from typing import Iterator, Type, List, Optional, Callable, Any
import queue
import time

# 3rd party includes
import grpc

# Protocol includes
from protocols.mtib.mtib_pb2 import (
    Empty,
    # AccelReadRequest,
    # AccelReadResponse,
    # AdcChannel,
    AdcReadRequest,
    AdcReadResponse,
    # AltimeterReadRequest,
    # AltimeterReadResponse,
    # DeleteFwFileRequest,
    # DeleteFwFileResponse,
    # DeviceType,
    DutPowerReadResponse,
    DutPowerRequest,
    DutPowerResponse,
    # DutVoltageReadRequest,
    # DutVoltageReadResponse,
    # FlashHexFileRequest,
    # FlashHexFileResponse,
    # Gpio,
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
    # HealthCheckRequest,
    # HealthCheckResponse,
    # ListFwFilesRequest,
    # ListFwFilesResponse,
    UartStreamRequest,
    UartStreamResponse,
    # UploadFwFileRequest,
    # UploadFwFileResponse,
)
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub

# App includes
from tests.lib import *

# ---------------------------------------------------------------------------------
#                                                                    Test Constants
# -------------------------------------------------------------------------------*/
# Power
TP8_BATT = 0
TP47_5V_IN = 0

# Adc
TP11_3V3 = 7
TP52_VIN = 0
TP30_VBCKP = 1
TP7_VBAT_MEAS = 2
TP24_3V3_GPS = 3

# Gpio
TP50_HARD_RESET = 0
TP49_CHRG_DET = 1
TP12_UVP_N = 2
TP1_3V3_PSM = 3

# Runner gRPC server port, as defined in the .proto file
RUNNER_SERVICE_GRPC_SERVER_PORT = 50053  # TODO: This should come from env variable

# ---------------------------------------------------------------------------------
#                                                                             Class
# -------------------------------------------------------------------------------*/


class Sigma5RunnersController:
    def __init__(self):
        self.runners: Dict[str, MtibV1Stub] = {}
        self.channels: Dict[str, grpc.Channel] = {}

        self.cmd_responses_queues: Dict[str, queue.Queue] = {}
        self.cmd_requests_queues: Dict[str, queue.Queue] = {}
        self.interpreter_running: Dict[str, bool] = {}
        self.interpreter_threads: Dict[str, threading.Thread] = {}
        self.uart_rpc_streams: Dict[str, Any] = {}

    def init(self, hosts: List[str]) -> str:
        errors = []

        # Use ThreadPoolExecutor to parallelize the connection process
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._connect_runner, host): host for host in hosts}
            for future in concurrent.futures.as_completed(futures):
                error = future.result()
                if error:
                    errors.append(error)

        if errors:
            return f"Errors occurred during runner initialization: {', '.join(errors)}"

        # Configure any GPIOs
        error = self._setup_runners()
        if error:
            return f"Failed to setup runners for sigma5 manufacturing configuration: {error}"

        return None  # No error

    def _connect_runner(self, host: str) -> str:
        try:
            # Create a gRPC channel
            channel = grpc.insecure_channel(f"{host}:{RUNNER_SERVICE_GRPC_SERVER_PORT}")
            self.channels[host] = channel

            # Create a stub using the insecure channel
            stub = MtibV1Stub(channel)

            # Do an initial health check with a timeout
            response = stub.HealthCheck(Empty(), timeout=5)

            # Add the runner to the dictionary
            self.runners[host] = stub

            # Create the needed objects for this runner
            self.cmd_responses_queues[host] = queue.Queue()
            self.cmd_requests_queues[host] = queue.Queue()

            logging.info(f"Runner at {host} connected successfully")
            return ""
        except grpc.RpcError as e:
            logging.error(f"Failed to connect to runner at {host}. Error: {str(e.details())}")
            return f"Failed to connect to runner at {host}. Error: {str(e.details())}"
        except Exception as e:
            logging.error(f"Unexpected error when connecting to runner at {host}. Error: {str(e)}")
            return f"Unexpected error when connecting to runner at {host}. Error: {str(e)}"

    def _setup_runners(self) -> str:
        for _, stub in self.runners.items():
            error = self._config_gpio(
                stub, TP50_HARD_RESET, GpioDirection.GPIO_DIRECTION_OUTPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_UP
            )
            if error:
                return error

            error = self._config_gpio(
                stub, TP49_CHRG_DET, GpioDirection.GPIO_DIRECTION_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN
            )
            if error:
                return error

            error = self._config_gpio(
                stub, TP12_UVP_N, GpioDirection.GPIO_DIRECTION_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_UP
            )
            if error:
                return error

            error = self._config_gpio(
                stub, TP1_3V3_PSM, GpioDirection.GPIO_DIRECTION_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN
            )
            if error:
                return error

        return ""

    def _config_gpio(
        self, server: MtibV1Stub, gpio: int, direction: GpioDirection, resistor: GpioResistorConfig
    ) -> str:
        try:
            response = server.GpioConfig(GpioConfigRequest(gpio=gpio, direction=direction, resistor=resistor))
            if response.success:
                return ""
            else:
                return f"Error: {response.message}, for GPIO {gpio}, type: {direction}"
        except grpc.RpcError as e:
            return f"RPC Error: {str(e.details())} for GPIO {gpio}, type: {direction}"

    def deinit(self) -> str:
        try:
            for host, channel in self.channels.items():
                # Close the gRPC channel for each runner
                channel.close()
                logging.info(f"Runner at {host} disconnected successfully")

            # Clear the runners and channels dictionaries
            self.runners.clear()
            self.channels.clear()

            self.cmd_requests_queues = {}
            self.cmd_responses_queues = {}

            return ""
        except Exception as e:
            return f"An error occurred during deinitialization: {str(e)}"

    def disable_power(self, host: str) -> str:
        if host not in self.runners:
            return f"No runner found for host {host}"

        try:
            stub = self.runners[host]
            response: DutPowerResponse = stub.DutPowerDisable(Empty())
            if not response.success:
                return f"DutPowerDisable Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to disable power for runner at {host}. Error: {str(e.details())}"

    def set_vbat(self, host: str, voltage: float) -> str:
        try:
            stub = self.runners[host]
            response: DutPowerResponse = stub.DutPowerEnable(DutPowerRequest(voltage_v=voltage))
            if not response.success:
                return f"DutVoltageSet Error: {response.message}"

            return ""
        except grpc.RpcError as e:
            return f"Failed to set VBAT for runner at {host}. Error: {str(e.details())}"

    def set_5vin(self, host: str, state: bool) -> str:
        if host not in self.runners:
            return f"No runner found for host {host}"

        try:
            if state:
                stub = self.runners[host]
                response: DutPowerResponse = stub.DutChargePowerEnable(Empty())
                if not response.success:
                    return f"DutChargePowerEnable failed Error: {response.message}"
            else:
                stub = self.runners[host]
                response: DutPowerResponse = stub.DutChargePowerDisable(Empty())
                if not response.success:
                    return f"DutChargePowerDisable failed Error: {response.message}"
            return ""
        except grpc.RpcError as e:
            return f"Failed to set 5VIN for runner at {host}. Error: {str(e.details())}"

    # def read_altimeter(self, host: str) -> Tuple[str, Optional[Any]]:
    #     if host not in self.runners:
    #         return f"No runner found for host {host}"

    #     try:
    #         stub = self.runners[host]
    #         response: AltimeterReadResponse = stub.AltimeterRead(AltimeterReadRequest())
    #         if not response.success:
    #             return f"Failed to read altimeter form MTIB. Error: {response.error}", None
    #         return "", response
    #     except grpc.RpcError as e:
    #         return f"Failed to read altimeter for runner at {host}. Error: {str(e.details())}", None

    # def read_accelerometer(self, host: str) -> Tuple[str, Optional[Any]]:
    #     if host not in self.runners:
    #         return f"No runner found for host {host}"

    #     try:
    #         stub = self.runners[host]
    #         response: AccelReadResponse = stub.AccelRead(AccelReadRequest())
    #         if not response.success:
    #             return f"Failed to read accelerometer from MTIB. Error: {response.error}", None
    #         return "", response
    #     except grpc.RpcError as e:
    #         return f"Failed to read accelerometer for runner at {host}. Error: {str(e.details())}", None

    # def set_hard_reset(self, host: str, state: bool) -> str:
    #     if host not in self.runners:
    #         return f"No runner found for host {host}"

    #     try:
    #         stub = self.runners[host]
    #         response: GpioWriteResponse = stub.GpioWrite(GpioWriteRequest(gpio=TP50_HARD_RESET, state=state))
    #         if not response.success:
    #             return f"GpioWrite for {TP50_HARD_RESET} Error: {response.error}"
    #         return ""
    #     except grpc.RpcError as e:
    #         return f"Failed to set hard reset for runner at {host}. Error: {str(e.details())}"

    def read_vin(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: AdcReadResponse = stub.AdcRead(AdcReadRequest(channel=TP52_VIN))
            if not response.success:
                return f"AdcRead Channel {TP52_VIN} Error: {response.message}", None
            return "", response.voltage_v
        except grpc.RpcError as e:
            return f"Failed to read VIN for runner at {host}. Error: {str(e.details())}", None

    def read_3v3(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: AdcReadResponse = stub.AdcRead(AdcReadRequest(channel=TP11_3V3))
            if not response.success:
                return f"AdcRead Channel {TP11_3V3} Error: {response.message}", None
            return "", response.voltage_v
        except grpc.RpcError as e:
            return f"Failed to read 3V3 for runner at {host}. Error: {str(e.details())}", None

    # def read_voltage(self, host: str) -> Tuple[str, Optional[float]]:
    #     if host not in self.runners:
    #         return f"No runner found for host {host}", None

    #     try:
    #         stub = self.runners[host]
    #         response: DutVoltageReadResponse = stub.DutVoltageRead(DutVoltageReadRequest())
    #         if not response.success:
    #             return f"DutVoltageRead Error: {response.error}", None
    #         return "", float(response.voltage_mv / 1000)
    #     except grpc.RpcError as e:
    #         return f"Failed to read voltage for runner at {host}. Error: {str(e.details())}", None

    def read_current(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: DutPowerReadResponse = stub.DutPowerRead(Empty())
            if not response.success:
                return f"DutPowerRead Error: {response.message}", None
            return "", float(response.current_a)
        except grpc.RpcError as e:
            return f"Failed to read current for runner at {host}. Error: {str(e.details())}", None

    def read_vbat(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: DutPowerReadResponse = stub.DutPowerRead(Empty())
            if not response.success:
                return f"DutPowerRead Error: {response.message}", None
            return "", float(response.voltage_v)
        except grpc.RpcError as e:
            return f"Failed to read VBAT for runner at {host}. Error: {str(e.details())}", None

    def read_vbckp(self, host: str) -> Tuple[str, Optional[float]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: AdcReadResponse = stub.AdcRead(AdcReadRequest(channel=TP30_VBCKP))
            if not response.success:
                return f"AdcRead Channel {TP30_VBCKP} Error: {response.message}", None
            return "", response.voltage_v
        except grpc.RpcError as e:
            return f"Failed to read VBCKP for runner at {host}. Error: {str(e.details())}", None

    def read_uvp_n(self, host: str) -> Tuple[str, Optional[bool]]:
        if host not in self.runners:
            return f"No runner found for host {host}", None

        try:
            stub = self.runners[host]
            response: GpioReadResponse = stub.GpioRead(GpioReadRequest(gpio=TP12_UVP_N))
            if not response.success:
                return f"GpioRead for {TP12_UVP_N} Error: {response.message}", None
            return "", response.state
        except grpc.RpcError as e:
            return f"Failed to read UVP_N for runner at {host}. Error: {str(e.details())}", None

    # def read_chrg_det(self, host: str) -> Tuple[str, Optional[bool]]:
    #     if host not in self.runners:
    #         return f"No runner found for host {host}", None

    #     try:
    #         stub = self.runners[host]
    #         response: GpioReadResponse = stub.GpioRead(GpioReadRequest(gpio=TP49_CHRG_DET))
    #         if not response.success:
    #             return f"GpioRead for {TP49_CHRG_DET} Error: {response.error}", None
    #         return "", response.state
    #     except grpc.RpcError as e:
    #         return f"Failed to read CHRG_DET for runner at {host}. Error: {str(e.details())}", None

    def upload_fw_file(self, host: str, file_path: str, host_type: HostType) -> Optional[str]:
        try:
            # Get file info first
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            # Read file in chunks to avoid loading entire file into memory
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks

            def request_iterator():
                # Stream the file content in chunks
                with open(file_path, "rb") as f:
                    first_chunk = True
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        if first_chunk:
                            # First request contains name, target, and first chunk
                            request = UploadFwFileRequest()
                            request.name = file_name
                            request.target = host_type
                            request.content = chunk
                            yield request
                            first_chunk = False
                        else:
                            # Subsequent requests contain only content
                            request = UploadFwFileRequest()
                            request.content = chunk
                            yield request

            # Make the streaming call
            try:
                stub = self.runners[host]
                response: UploadFwFileResponse = stub.UploadFwFile(request_iterator())
                if not response.success:
                    return f"UploadFwFile error: {response.message}"
                return None
            except grpc.RpcError as e:
                return f"gRPC error for UploadFwFile at {self.config.net.addr}. Error: {str(e.details())}"

        except FileNotFoundError:
            return f"UploadFwFile error: File not found at {file_path}"
        except PermissionError:
            return f"UploadFwFile error: Permission denied reading file {file_path}"
        except Exception as e:
            return f"Unexpected error in UploadFwFile at {self.config.net.addr}: {str(e)}"

    def delete_fw_file(self, host: str, filename: str, host_type: HostType) -> str:
        if host not in self.runners:
            return f"No runner found for host {host}"

        try:
            stub = self.runners[host]

            # Check if the file already exists on the server
            list_response: ListFwFilesResponse = stub.ListFwFiles(Empty())
            if not any(file_info.name == filename for file_info in list_response.files):
                return f"File {filename} does not exist on the server"

            # Delete the file
            delete_response: DeleteFwFileResponse = stub.DeleteFwFile(
                DeleteFwFileRequest(file_info=FwFileInfo(name=filename, target=host_type))
            )
            if delete_response.success:
                logging.info(f"File {filename} deleted successfully")
                return ""
            else:
                return f"Failed to delete file {filename}: {delete_response.error}"
        except grpc.RpcError as e:
            return f"RPC Error: {str(e.details())}"
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def flash_fw_file(
        self, host: str, file_info: FwFileInfo, sector_erase: bool = False, recover: bool = False
    ) -> Tuple[Optional[bool], Optional[str]]:
        # Retrieve the runner stub
        if host not in self.runners:
            return None, f"No runner stub found for host {host}"

        try:
            stub = self.runners[host]
            response: FlashFwFileResponse = stub.FlashFwFile(
                FlashFwFileRequest(file_info=file_info, sector_erase=sector_erase, recover=recover)
            )
            if not response.success:
                return None, f"FlashFwFile error: {response.message}"
            return response.time_ms, None
        except grpc.RpcError as e:
            return None, f"gRPC error for FlashFwFile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in FlashFwFile at {self.config.net.addr}: {str(e)}"

    def UartStream(
        self, host: str, target: HostType, request_iterator: Iterator[UartStreamRequest]
    ) -> Iterator[UartStreamResponse]:
        """Stream UART data to/from a target device using a custom request iterator.

        Args:
            target: Target host type (NRF9160, NRF52840, etc.)
            request_iterator: Iterator that yields UartStreamRequest objects

        Yields:
            UartStreamResponse objects containing received data or status
        """
        try:
            # Make the streaming call with the provided request iterator
            # The gRPC stub's UartStream method only takes the request_iterator, not the target
            response_iterator = self.runners[host].UartStream(request_iterator)

            for response in response_iterator:
                yield response

        except grpc.RpcError as e:
            logging.error(f"gRPC error for UartStream at {host}. Error: {str(e.details())}")
            yield UartStreamResponse(success=False, message=f"gRPC error: {str(e.details())}", target=target)
        except Exception as e:
            logging.error(f"Unexpected error in UartStream at {host}: {str(e)}")
            yield UartStreamResponse(success=False, message=f"Unexpected error: {str(e)}", target=target)

    # ---------------------------------------------------------------------------------
    #                                                             App Coproc Commands
    # -------------------------------------------------------------------------------*/

    def sigma5_cmd_app_lock_shell(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Simplified UART stream listener for lock_shell command"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"lock_shell\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF52840
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the success message
                    full_response = "".join(response_lines)
                    if "Locking shell mode ON" in full_response:
                        # Got the response
                        return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def sigma5_cmd_app_debug_uart_disable(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Simplified UART stream listener for debug_uart_off command"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"debug_enable 0\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF52840
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the success message
                    full_response = "".join(response_lines)
                    if "Debug is not enabled" in full_response:
                        # Got the response
                        return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def sigma5_cmd_app_get_chip_ids(self, host: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the device and return LoRa status and Ext flash chip ID"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_chip_ids\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF52840
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "LoRa hardware available:" in full_response and "Ext flash chip ID:" in full_response:
                        # Check if we also have the command prompt, indicating the response is complete
                        if "Mfg shell" in full_response:
                            # Parse the response
                            lora_status = None
                            ext_flash_id = None

                            # Extract LoRa status
                            lora_start = full_response.find("LoRa hardware available:")
                            if lora_start != -1:
                                lora_line_start = full_response.rfind("\n", 0, lora_start) + 1
                                lora_line_end = full_response.find("\n", lora_start)
                                if lora_line_end == -1:
                                    lora_line_end = len(full_response)
                                lora_line = full_response[lora_line_start:lora_line_end].strip()
                                if ":" in lora_line:
                                    lora_status = lora_line.split(":", 1)[1].strip()

                            # Extract Ext flash chip ID
                            flash_start = full_response.find("Ext flash chip ID:")
                            if flash_start != -1:
                                flash_line_start = full_response.rfind("\n", 0, flash_start) + 1
                                flash_line_end = full_response.find("\n", flash_start)
                                if flash_line_end == -1:
                                    flash_line_end = len(full_response)
                                flash_line = full_response[flash_line_start:flash_line_end].strip()
                                if ":" in flash_line:
                                    ext_flash_id = flash_line.split(":", 1)[1].strip()

                            return lora_status, ext_flash_id, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception in get_chip_ids: {str(e)}"

    # ---------------------------------------------------------------------------------
    #                                                             Comms Coproc Commands
    # -------------------------------------------------------------------------------*/
    def sigma5_cmd_comms_lock_shell(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Simplified UART stream listener for lock_shell command"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"lock_shell\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF9160
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the success message
                    full_response = "".join(response_lines)
                    if "Locking shell mode ON" in full_response:
                        # Got the response
                        return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def sigma5_cmd_comms_debug_uart_disable(self, host: str) -> Tuple[Optional[bool], Optional[str]]:
        """Simplified UART stream listener for debug_uart_off command"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"debug_enable 0\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF9160
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the success message
                    full_response = "".join(response_lines)
                    if "Debug is not enabled" in full_response:
                        # Got the response
                        return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def sigma5_cmd_comms_get_chip_ids(
        self, host: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the comms co-processor device"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_chip_ids\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF9160
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, None, None, None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if (
                        "Accel chip ID:" in full_response
                        and "Altimeter chip ID:" in full_response
                        and "Ext flash chip ID:" in full_response
                        and "GPS HW version:" in full_response
                        and "BLE MAC:" in full_response
                    ):
                        # Check if we also have the command prompt, indicating the response is complete
                        if "Mfg shell" in full_response:
                            # Parse the response
                            accel_id = None
                            altimeter_id = None
                            ext_flash_id = None
                            gps_hw_version = None
                            ble_mac = None

                            # Extract Accel chip ID
                            accel_start = full_response.find("Accel chip ID:")
                            if accel_start != -1:
                                accel_line_start = full_response.rfind("\n", 0, accel_start) + 1
                                accel_line_end = full_response.find("\n", accel_start)
                                if accel_line_end == -1:
                                    accel_line_end = len(full_response)
                                accel_line = full_response[accel_line_start:accel_line_end].strip()
                                if ":" in accel_line:
                                    accel_id = accel_line.split(":", 1)[1].strip()

                            # Extract Altimeter chip ID
                            altimeter_start = full_response.find("Altimeter chip ID:")
                            if altimeter_start != -1:
                                altimeter_line_start = full_response.rfind("\n", 0, altimeter_start) + 1
                                altimeter_line_end = full_response.find("\n", altimeter_start)
                                if altimeter_line_end == -1:
                                    altimeter_line_end = len(full_response)
                                altimeter_line = full_response[altimeter_line_start:altimeter_line_end].strip()
                                if ":" in altimeter_line:
                                    altimeter_id = altimeter_line.split(":", 1)[1].strip()

                            # Extract Ext flash chip ID
                            flash_start = full_response.find("Ext flash chip ID:")
                            if flash_start != -1:
                                flash_line_start = full_response.rfind("\n", 0, flash_start) + 1
                                flash_line_end = full_response.find("\n", flash_start)
                                if flash_line_end == -1:
                                    flash_line_end = len(full_response)
                                flash_line = full_response[flash_line_start:flash_line_end].strip()
                                if ":" in flash_line:
                                    ext_flash_id = flash_line.split(":", 1)[1].strip()

                            # Extract GPS HW version
                            gps_start = full_response.find("GPS HW version:")
                            if gps_start != -1:
                                gps_line_start = full_response.rfind("\n", 0, gps_start) + 1
                                gps_line_end = full_response.find("\n", gps_start)
                                if gps_line_end == -1:
                                    gps_line_end = len(full_response)
                                gps_line = full_response[gps_line_start:gps_line_end].strip()
                                if ":" in gps_line:
                                    gps_hw_version = gps_line.split(":", 1)[1].strip()

                            # Extract BLE MAC
                            ble_start = full_response.find("BLE MAC:")
                            if ble_start != -1:
                                ble_line_start = full_response.rfind("\n", 0, ble_start) + 1
                                ble_line_end = full_response.find("\n", ble_start)
                                if ble_line_end == -1:
                                    ble_line_end = len(full_response)
                                ble_line = full_response[ble_line_start:ble_line_end].strip()
                                if ":" in ble_line:
                                    ble_mac = ble_line.split(":", 1)[1].strip()

                            return accel_id, altimeter_id, ext_flash_id, gps_hw_version, ble_mac, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return (
                None,
                None,
                None,
                None,
                None,
                f"Timeout or no success message found. Response: {full_response[:200]}...",
            )

        except Exception as e:
            return None, None, None, None, None, f"Exception in get_chip_ids: {str(e)}"

    def sigma5_cmd_comms_get_ublox_version_info(
        self, host: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get ublox version info from the device"""
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_ublox\r".encode("utf-8"))  # Send command

            def request_iterator():
                while True:
                    try:
                        # Get input from queue (non-blocking)
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=data)
                    except queue.Empty:
                        # No input, send empty request to keep stream alive
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=b"")
                        time.sleep(0.1)

            # Collect response like the working terminal
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            target = HostType.HOST_TYPE_NRF9160
            for resp in self.UartStream(host, target, request_iterator()):
                if not resp.success:
                    return None, None, None, None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if (
                        "GPS HW version:" in full_response
                        and "GPS FW version:" in full_response
                        and "GPS SW version:" in full_response
                        and "GPS protocol version:" in full_response
                        and "GPS constellations:" in full_response
                    ):
                        # Check if we also have the command prompt, indicating the response is complete
                        if "Mfg shell" in full_response:
                            # Parse the response
                            hw_version = None
                            fw_version = None
                            sw_version = None
                            proto_version = None
                            constellations = None

                            # Extract HW version
                            hw_start = full_response.find("GPS HW version:")
                            if hw_start != -1:
                                hw_line_start = full_response.rfind("\n", 0, hw_start) + 1
                                hw_line_end = full_response.find("\n", hw_start)
                                if hw_line_end == -1:
                                    hw_line_end = len(full_response)
                                hw_line = full_response[hw_line_start:hw_line_end].strip()
                                if ":" in hw_line:
                                    hw_version = hw_line.split(":", 1)[1].strip()

                            # Extract FW version
                            fw_start = full_response.find("GPS FW version:")
                            if fw_start != -1:
                                fw_line_start = full_response.rfind("\n", 0, fw_start) + 1
                                fw_line_end = full_response.find("\n", fw_start)
                                if fw_line_end == -1:
                                    fw_line_end = len(full_response)
                                fw_line = full_response[fw_line_start:fw_line_end].strip()
                                if ":" in fw_line:
                                    fw_version = fw_line.split(":", 1)[1].strip()

                            # Extract SW version
                            sw_start = full_response.find("GPS SW version:")
                            if sw_start != -1:
                                sw_line_start = full_response.rfind("\n", 0, sw_start) + 1
                                sw_line_end = full_response.find("\n", sw_start)
                                if sw_line_end == -1:
                                    sw_line_end = len(full_response)
                                sw_line = full_response[sw_line_start:sw_line_end].strip()
                                if ":" in sw_line:
                                    sw_version = sw_line.split(":", 1)[1].strip()

                            # Extract Protocol version
                            proto_start = full_response.find("GPS protocol version:")
                            if proto_start != -1:
                                proto_line_start = full_response.rfind("\n", 0, proto_start) + 1
                                proto_line_end = full_response.find("\n", proto_start)
                                if proto_line_end == -1:
                                    proto_line_end = len(full_response)
                                proto_line = full_response[proto_line_start:proto_line_end].strip()
                                if ":" in proto_line:
                                    proto_version = proto_line.split(":", 1)[1].strip()

                            # Extract Constellations
                            constellations_start = full_response.find("GPS constellations:")
                            if constellations_start != -1:
                                constellations_line_start = full_response.rfind("\n", 0, constellations_start) + 1
                                constellations_line_end = full_response.find("\n", constellations_start)
                                if constellations_line_end == -1:
                                    constellations_line_end = len(full_response)
                                constellations_line = full_response[
                                    constellations_line_start:constellations_line_end
                                ].strip()
                                if ":" in constellations_line:
                                    constellations = constellations_line.split(":", 1)[1].strip()

                            return hw_version, fw_version, sw_version, proto_version, constellations, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return (
                None,
                None,
                None,
                None,
                None,
                f"Timeout or no success message found. Response: {full_response[:200]}...",
            )

        except Exception as e:
            return None, None, None, None, None, f"Exception in get_ublox: {str(e)}"


# ---------------------------------------------------------------------------------
#                                                                   Class Singleton
# -------------------------------------------------------------------------------*/
mtib_servers: Sigma5RunnersController = Sigma5RunnersController()
