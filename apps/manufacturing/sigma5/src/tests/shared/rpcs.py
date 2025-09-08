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
from typing import Iterator, Type

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
    # UartStreamRequest,
    # UartStreamResponse,
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
#                                                                   Device Commands
# -------------------------------------------------------------------------------*/
NUM_CRC_BYTES = 4
SYNC_BYTE1 = 0x12
SYNC_BYTE2 = 0xE4
RECEIVE_TIMEOUT_MS = 15000  # 15 seconds


class Sigma5DeviceCommand(Enum):
    CMD_NOP = 0x00
    CMD_ACK = 0x01
    CMD_CLEAR_PERSONALIZATION = 0x02
    CMD_PERSONALIZE_DEV_EUI = 0x11
    CMD_IMEI_ICCID_GET = 0x2B
    CMD_POST = 0x2C
    CMD_GET_SENSOR_VALS = 0x2D
    CMD_GET_MODEM_FW_VER = 0x2E
    CMD_DEV_EC_PUB_KEY = 0x2F


class CommandResponse:
    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)


@dataclass(frozen=True)
class CMD_ACK_Response(CommandResponse):
    ack: bool

    @classmethod
    def from_bytes(cls, data: bytes):
        ack = False
        if len(data) > 1 and data[1] == 1:  # Check if the second byte equals 1
            ack = True
        return cls(ack=ack)


@dataclass(frozen=True)
class CMD_CLEAR_PERSONALIZATION_Response(CommandResponse):
    ack: bool = None

    @classmethod
    def from_bytes(cls, data: bytes):
        ack = False
        if len(data) > 1 and data[1] == 1:  # Check if the second byte equals 1
            ack = True
        return cls(ack)


@dataclass(frozen=True)
class CMD_PERSONALIZE_DEV_EUI_Response(CommandResponse):
    flags: int = None
    read: bool = None
    device_id: int = None

    @classmethod
    def from_bytes(cls, data: bytes):
        data_length: int = 9
        data_format: str = ">BQ"

        if len(data) < data_length:
            raise ValueError(
                f"Data length is insufficient for CMD_PERSONALIZE_DEV_EUI_Response, expected {data_length}, got {len(data)}"
            )

        flags, device_id = struct.unpack(data_format, data)

        read = (flags & 0x80) >> 7  # bit 7

        return cls(flags=flags, read=read, device_id=device_id)

    @classmethod
    def to_bytes(cls, read: bool, device_id: int):
        data_length = 9
        data_format: str = ">BQ"

        flags = 0x80 if read else 0x00  # bit 7

        payload = struct.pack(data_format, flags, device_id)

        if len(payload) != data_length:
            raise ValueError(
                f"Data length is incorrect packing payload for CMD_PERSONALIZE_DEV_EUI_Response, expected {data_length}, got {len(payload)}"
            )

        return payload


@dataclass(frozen=True)
class CMD_IMEI_ICCID_Response(CommandResponse):
    imei: str
    iccids: List[str]

    @classmethod
    def from_bytes(cls, data: bytes):
        imei_iccid_str = data.decode("ascii").strip("\x00")
        imei_iccid_list = imei_iccid_str.split(",")
        imei = imei_iccid_list[0]
        iccids = imei_iccid_list[1:]

        return cls(imei=imei, iccids=iccids)


@dataclass(frozen=True)
class CMD_POST_Response(CommandResponse):
    # Supported by message spec
    accel_ic_id: int = None
    alt_ic_id: int = None
    external_flash_ic_id: str = None
    external_flash_test_pass: bool = None
    is_lora_connected: bool = None
    gps_ublox_version_info: str = None

    # Further decoding of gps_ublox_raw_version_info
    gps_ublox_sw_ver: str = None
    gps_ublox_hw_ver: str = None
    gps_ublox_fw_ver: str = None
    gps_ublox_proto_ver: str = None
    gps_ublox_supported_constellations: List[str] = None

    @classmethod
    def from_bytes(cls, data: bytes):

        data_length: int = 167
        packed_format: str = ">BB3sBB160s"

        # Check if the data length is sufficient
        if len(data) < data_length:
            raise ValueError("Data length is insufficient for CMD_POST_Response")

        # Unpack the data
        unpacked_data = struct.unpack(packed_format, data[:data_length])

        # Extract the data
        accelerometer_ic_id = unpacked_data[0]
        altimeter_ic_id = unpacked_data[1]
        external_flash_ic_id = unpacked_data[2].hex()
        external_flash_test_pass = True if unpacked_data[3] == 255 else False
        is_lora_connected = True if unpacked_data[4] == 255 else False
        gps_ublox_version_info = unpacked_data[5].decode("utf-8", errors="replace")

        # Further decode the GPS u-blox version info
        gps_ublox_null_term_split = unpacked_data[5].split(b"\x00")

        # Remove empty strings
        gps_ublox_null_term_split = [x for x in gps_ublox_null_term_split if x]

        gps_ublox_sw_ver = gps_ublox_null_term_split[0].decode("utf-8", errors="replace")
        gps_ublox_hw_ver = gps_ublox_null_term_split[1].decode("utf-8", errors="replace")
        gps_ublox_fw_ver = gps_ublox_null_term_split[2].decode("utf-8", errors="replace")
        gps_ublox_proto_ver = gps_ublox_null_term_split[3].decode("utf-8", errors="replace")
        gps_ublox_supported_constellations = gps_ublox_null_term_split[4:]
        gps_ublox_supported_constellations = b";".join(gps_ublox_supported_constellations)
        gps_ublox_supported_constellations = gps_ublox_supported_constellations.decode("utf-8", errors="replace")
        gps_ublox_supported_constellations = gps_ublox_supported_constellations.split(";")

        return cls(
            accel_ic_id=accelerometer_ic_id,
            alt_ic_id=altimeter_ic_id,
            external_flash_ic_id=external_flash_ic_id,
            external_flash_test_pass=external_flash_test_pass,
            is_lora_connected=is_lora_connected,
            gps_ublox_version_info=gps_ublox_version_info,
            gps_ublox_sw_ver=gps_ublox_sw_ver,
            gps_ublox_hw_ver=gps_ublox_hw_ver,
            gps_ublox_fw_ver=gps_ublox_fw_ver,
            gps_ublox_proto_ver=gps_ublox_proto_ver,
            gps_ublox_supported_constellations=gps_ublox_supported_constellations,
        )


@dataclass(frozen=True)
class CMD_GET_SENSOR_VALS_Response(CommandResponse):
    accelerometer_x_g: int = None
    accelerometer_y_g: int = None
    accelerometer_z_g: int = None
    altimeter_pressure_in_hg: int = None
    altimeter_temperature_c: int = None
    voltage_measurement: int = None

    @classmethod
    def from_bytes(cls, data: bytes):
        """Unpack response bytes and put into right fields based on the given payload definition"""
        data_length: int = 11
        packed_format: str = ">hhhHhB"

        if len(data) < data_length:
            raise ValueError("Data length is insufficient for CMD_GET_SENSOR_VALS_Response")

        unpacked_data = struct.unpack(packed_format, data)

        # Accelerometer measurements are 2-bytes, 1/256 G per LSB
        accelerometer_x_g = unpacked_data[0] / 256.0
        accelerometer_y_g = unpacked_data[1] / 256.0
        accelerometer_z_g = unpacked_data[2] / 256.0

        # Altimeter pressure measurements are 2-bytes (unsigned), 1/256 inHg per LSB
        altimeter_pressure_in_hg = unpacked_data[3] / 256.0

        # Altimeter temperature measurements are 2-bytes, 0 LSB = 25°C, sensitivity of 16 LSB / °C
        altimeter_temperature_c = 25.0 + unpacked_data[4] / 16.0

        # Voltage measurement is 1-byte (unsigned), with 25mV per bit
        voltage_measurement = unpacked_data[5] * 0.025

        return cls(
            accelerometer_x_g=accelerometer_x_g,
            accelerometer_y_g=accelerometer_y_g,
            accelerometer_z_g=accelerometer_z_g,
            altimeter_pressure_in_hg=altimeter_pressure_in_hg,
            altimeter_temperature_c=altimeter_temperature_c,
            voltage_measurement=voltage_measurement,
        )


@dataclass(frozen=True)
class CMD_GET_MODEM_FW_VER_Response:
    fw_version: str = None

    @classmethod
    def from_bytes(cls, data: bytes):
        fw_version = data.decode("ascii").strip("\x00")
        return cls(fw_version=fw_version)


@dataclass(frozen=True)
class CMD_DEV_EC_PUB_KEY_Response(CommandResponse):
    public_key: str = None

    @classmethod
    def from_bytes(cls, data: bytes):
        data_length = 65

        if len(data) < data_length:
            raise ValueError(
                f"Data length is insufficient for CMD_DEV_EC_PUB_KEY_Response, expected {data_length}, got {len(data)}"
            )

        # Convert the public key to a string
        public_key = "".join(f"{byte:02x}" for byte in data)

        return cls(public_key=public_key)


# ---------------------------------------------------------------------------------
#                                                                             Class
# -------------------------------------------------------------------------------*/


class Sigma5RunnersController:
    def __init__(self):
        self.runners: Dict[str, MtibV1Stub] = {}
        self.channels: Dict[str, grpc.Channel] = {}

        self.response_classes = {
            Sigma5DeviceCommand.CMD_NOP: CMD_ACK_Response,
            Sigma5DeviceCommand.CMD_ACK: CMD_ACK_Response,
            Sigma5DeviceCommand.CMD_CLEAR_PERSONALIZATION: CMD_CLEAR_PERSONALIZATION_Response,
            Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI: CMD_PERSONALIZE_DEV_EUI_Response,
            Sigma5DeviceCommand.CMD_IMEI_ICCID_GET: CMD_IMEI_ICCID_Response,
            Sigma5DeviceCommand.CMD_POST: CMD_POST_Response,
            Sigma5DeviceCommand.CMD_GET_SENSOR_VALS: CMD_GET_SENSOR_VALS_Response,
            Sigma5DeviceCommand.CMD_GET_MODEM_FW_VER: CMD_GET_MODEM_FW_VER_Response,
            Sigma5DeviceCommand.CMD_DEV_EC_PUB_KEY: CMD_DEV_EC_PUB_KEY_Response,
        }

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
    ) -> Tuple[Optional[int], Optional[str]]:
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

    # def _start_cmd_interpreter(self, host: str) -> str:
    #     if self.interpreter_running.get(host, False):
    #         return "Command interpreter is already running"

    #     self.interpreter_running[host] = True
    #     self.interpreter_threads[host] = threading.Thread(target=self._interpret_commands, args=(host,))
    #     self.interpreter_threads[host].start()
    #     return ""

    # def _interpret_commands(self, host: str):
    #     buffer = b""
    #     runner = self.runners.get(host)

    #     def request_iterator() -> Iterator[UartStreamRequest]:
    #         while self.interpreter_running[host]:
    #             try:
    #                 request = self.cmd_requests_queues[host].get(
    #                     timeout=1
    #                 )  # Use a timeout to regularly check the running flag
    #                 if request.data == b"STOP":
    #                     break  # Exit the iterator loop
    #                 yield request
    #             except queue.Empty:
    #                 continue

    #     try:
    #         self.uart_rpc_streams[host] = runner.nrf9160UartStream(request_iterator())
    #         for response in self.uart_rpc_streams[host]:
    #             if not self.interpreter_running[host]:
    #                 break

    #             data = response.data
    #             buffer += data

    #             while len(buffer) > 0:
    #                 sync_index = buffer.find(struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2))
    #                 if sync_index == -1:
    #                     buffer = b""  # Clear buffer if no sync bytes are found
    #                     break

    #                 buffer = buffer[sync_index:]

    #                 if len(buffer) < 5:
    #                     break

    #                 payload_length = struct.unpack(">H", buffer[3:5])[0]
    #                 total_length = 5 + payload_length  # 5 bytes before payload + payload length + CRC

    #                 if len(buffer) < total_length:
    #                     break

    #                 full_response = buffer[:total_length]
    #                 buffer = buffer[total_length:]

    #                 try:
    #                     unpack_format = f">BBBH{payload_length - NUM_CRC_BYTES}sI"
    #                     sync_byte1, sync_byte2, command_byte, length_field, payload, crc_received = struct.unpack(
    #                         unpack_format, full_response
    #                     )
    #                     # logging.debug(f"Unpacked data: {sync_byte1}, {sync_byte2}, {command_byte}, {length_field}, {payload}, {crc_received}")

    #                     # CRC should be calculated from command_byte to the end of the payload, excluding the CRC itself
    #                     crc_calculated = self._calculate_crc32(full_response[2:-NUM_CRC_BYTES])
    #                     if crc_received != crc_calculated:
    #                         logging.error(f"CRC mismatch: received {crc_received}, calculated {crc_calculated}")
    #                         continue

    #                     self.cmd_responses_queues[host].put(full_response)
    #                 except Exception as e:
    #                     logging.error(f"An exception ocurred whilst trying to unpack response: {e}")
    #                     break
    #     except grpc.RpcError as e:
    #         if e.code() != grpc.StatusCode.CANCELLED:
    #             logging.error(f"An exception occurred during command interpretation: {e}")

    # def _stop_cmd_interpreter(self, host: str) -> str:
    #     if not self.interpreter_running.get(host, False):
    #         return "Command interpreter is not running"

    #     # Set the running flag to False
    #     self.interpreter_running[host] = False

    #     # Insert a stop request to unblock the iterator
    #     self.cmd_requests_queues[host].put(UartStreamRequest(data=b"STOP"))

    #     # Cancel the gRPC call if it exists
    #     if self.uart_rpc_streams[host]:
    #         self.uart_rpc_streams[host].cancel()

    #     # Wait for the interpreter thread to terminate
    #     if self.interpreter_threads[host]:
    #         self.interpreter_threads[host].join(timeout=10)  # Wait for a maximum of 5 seconds
    #         if self.interpreter_threads[host].is_alive():
    #             logging.error(f"Failed to stop the command interpreter thread in time for {host}")
    #             return f"Failed to stop the command interpreter thread in time for {host}"
    #         self.interpreter_threads[host] = None

    #     return ""

    # def _send_command(
    #     self,
    #     host: str,
    #     command: Sigma5DeviceCommand,
    #     payload: bytes = b"",
    #     receive_timeout_ms=RECEIVE_TIMEOUT_MS,
    #     response_type: Sigma5DeviceCommand = None,
    # ) -> Tuple[str, Any]:
    #     runner = self.runners.get(host)
    #     if not runner:
    #         return f"No runner found for host: {host}", None

    #     try:
    #         # Start the interpreter handler
    #         error = self._start_cmd_interpreter(host)
    #         if error:
    #             return f"Could not start the command interpreter for {host}, {error}", None

    #         # Build the command
    #         sync_bytes = struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2)
    #         command_byte = struct.pack("B", command.value)
    #         message_length = struct.pack(">H", len(payload) + NUM_CRC_BYTES)

    #         crc_value = self._calculate_crc32(command_byte + message_length + payload)
    #         crc_bytes = struct.pack(">I", crc_value)

    #         message = sync_bytes + command_byte + message_length + payload + crc_bytes

    #         # Send the command to the device
    #         self.cmd_requests_queues[host].put(UartStreamRequest(data=message))
    #         try:
    #             # Await for responses in the queue
    #             response = self.cmd_responses_queues[host].get(timeout=receive_timeout_ms / 1000.0)

    #             # Decode the response into the right type
    #             if response_type is None:
    #                 parse_error, response = self._parse_response(command, response, self.response_classes[command])
    #             else:
    #                 parse_error, response = self._parse_response(
    #                     response_type, response, self.response_classes[response_type]
    #                 )
    #             if parse_error:
    #                 parse_error = f"Could not parse response for command {command.name} at {host}, {parse_error}"

    #             # Stop the interpreter
    #             error = self._stop_cmd_interpreter(host)
    #             if error:
    #                 return f"Could not stop the command interpreter for {host}, {error}", None

    #             return parse_error, response
    #         except queue.Empty:
    #             error = self._stop_cmd_interpreter(host)
    #             if error:
    #                 return f"Could not stop the command interpreter for {host}, {error}", None

    #             return f"Response timeout ocurred for command {command.name} at {host}", None

    #     except Exception as e:
    #         error = self._stop_cmd_interpreter(host)
    #         if error:
    #             return f"Could not stop the command interpreter for {host}, {error}", None

    #         return f"Error sending command {command.name} to runner at {host}. Error: {str(e)}", None

    # def _parse_response(
    #     self, command: Sigma5DeviceCommand, response: bytes, response_class: Type[CommandResponse]
    # ) -> Tuple[str, Any]:
    #     try:
    #         payload_length = struct.unpack(">H", response[3:5])[0]
    #         unpack_format = f">BBBH{payload_length - NUM_CRC_BYTES}sI"
    #         sync_byte1, sync_byte2, command_byte, length_field, payload, crc_received = struct.unpack(
    #             unpack_format, response
    #         )

    #         if command == Sigma5DeviceCommand.CMD_NOP:
    #             command = Sigma5DeviceCommand.CMD_ACK

    #         if command.value != command_byte:
    #             return f"Command mismatch. Expected {command.value}, got {command_byte}", None

    #         crc_calculated = self._calculate_crc32(response[2:-NUM_CRC_BYTES])
    #         if crc_received != crc_calculated:
    #             return f"CRC mismatch, expected {crc_calculated}, got {crc_received}", None

    #         response_object = response_class.from_bytes(payload)
    #         return "", response_object
    #     except Exception as e:
    #         return f"Failed to parse response: {str(e)}", None

    # def _calculate_sha256(self, file_path: str) -> str:
    #     sha256_hash = hashlib.sha256()
    #     with open(file_path, "rb") as f:
    #         for byte_block in iter(lambda: f.read(4096), b""):
    #             sha256_hash.update(byte_block)
    #     return sha256_hash.hexdigest()

    # def _calculate_crc32(self, data):
    #     return zlib.crc32(data) & 0xFFFFFFFF

    # def dut_command_send_nop(self, host: str) -> Tuple[str, CMD_ACK_Response]:
    #     return self._send_command(host, Sigma5DeviceCommand.CMD_NOP, response_type=Sigma5DeviceCommand.CMD_ACK)

    # def dut_command_get_sensor_value(self, host: str) -> Tuple[str, CMD_GET_SENSOR_VALS_Response]:
    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_GET_SENSOR_VALS,
    #     )

    # def dut_command_get_chip_id(self, host: str) -> Tuple[str, CMD_POST_Response]:
    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_POST,
    #     )

    # def dut_command_get_imei_iccid(self, host: str) -> Tuple[str, CMD_IMEI_ICCID_Response]:
    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_IMEI_ICCID_GET,
    #     )

    # def dut_command_get_modem_fw(self, host: str) -> Tuple[str, CMD_GET_MODEM_FW_VER_Response]:
    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_GET_MODEM_FW_VER,
    #     )

    # def dut_command_clear_personalization(self, host: str) -> tuple[str, CMD_CLEAR_PERSONALIZATION_Response]:
    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_CLEAR_PERSONALIZATION,
    #         response_type=Sigma5DeviceCommand.CMD_ACK,  # Use CMD_ACK as the response type
    #     )

    # def dut_command_set_device_eui(self, host: str, device_eui: int) -> Tuple[str, CMD_DEV_EC_PUB_KEY_Response]:

    #     # Create the payload
    #     payload = CMD_PERSONALIZE_DEV_EUI_Response.to_bytes(read=False, device_id=device_eui)

    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
    #         payload=payload,
    #         response_type=Sigma5DeviceCommand.CMD_DEV_EC_PUB_KEY,  # We expect a CMD_DEV_EC_PUB_KEY response
    #     )

    # def dut_command_get_device_eui(self, host: str) -> Tuple[str, CMD_PERSONALIZE_DEV_EUI_Response]:
    #     payload = CMD_PERSONALIZE_DEV_EUI_Response.to_bytes(read=True, device_id=0xDEADBEEFDEADBEEF)

    #     # Wake up the device
    #     self.dut_command_send_nop(host)
    #     sleep(1)

    #     # Send the command
    #     return runnners_controller._send_command(
    #         host,
    #         Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
    #         payload=payload,
    #         response_type=Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
    #     )


# ---------------------------------------------------------------------------------
#                                                                   Class Singleton
# -------------------------------------------------------------------------------*/
runnners_controller: Sigma5RunnersController = Sigma5RunnersController()
