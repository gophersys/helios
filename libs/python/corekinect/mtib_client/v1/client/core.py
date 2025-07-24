# Standard includes
import inspect
import queue
import struct
import threading
import time
from enum import Enum
import zlib
from typing import Optional, Tuple, List, Iterator, Type, Any
from dataclasses import dataclass
import os

# 3rd Party includes
import grpc
from grpc import insecure_channel, RpcError

# Protocol includes
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub as MtibClientV1

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from .types import *
from .config import *

# Import actual protobuf types for UART streaming
from protocols.mtib.mtib_pb2 import UartStreamRequest, UartStreamResponse


# ---------------------------------------------------------------------------------
#                                                                    Test Constants
# -------------------------------------------------------------------------------*/
NUM_CRC_BYTES = 4
SYNC_BYTE1 = 0x12
SYNC_BYTE2 = 0xE4
RECEIVE_TIMEOUT_MS = 1000  # 1 second


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
class CMD_GET_MODEM_FW_VER_Response(CommandResponse):
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


class MtibV1Client:
    # -----------------------------------------------
    #                                          Config
    # ---------------------------------------------*/
    class Config:
        def __init__(
            self,
            net: NetConfig = NetConfig(),
        ):
            self.net: NetConfig = net

    # -----------------------------------------------
    #                                          Init
    # ---------------------------------------------*/
    def __init__(self, config: Config, logger: Logger = None):
        self.config: self.Config = config

        if logger is None:
            self.logger: Logger = Logger(
                config=Logger.Config(
                    logger_name="runner_client_v1",
                )
            )
        else:
            self.logger: Logger = logger.from_parent("mtib_client_v1")

        # Internal objects used by the channel
        self.channel: grpc.Channel = None
        self.client: MtibClientV1 = None
        
        # Command interpreter state
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
        
        # Command interpreter state per target
        self.cmd_responses_queues: Dict[HostType, queue.Queue] = {}
        self.cmd_requests_queues: Dict[HostType, queue.Queue] = {}
        self.interpreter_running: Dict[HostType, bool] = {}
        self.interpreter_threads: Dict[HostType, threading.Thread] = {}
        self.uart_rpc_streams: Dict[HostType, Any] = {}

    # -----------------------------------------------
    #                                         Helpers
    # ---------------------------------------------*/
    def _get_func_name(self) -> str:
        return inspect.currentframe().f_back.f_code.co_name

    def _grpc_call(self, func, request, *, return_value: bool = False):
        """Helper method to handle common gRPC call patterns using Go-like error handling.

        Args:
            func: The gRPC method to call
            request: The request object to send
            return_value: If True, returns (value1, value2, ..., error). If False, returns Optional[str] error.

        Returns:
            If return_value=False (action methods):
                - On success: None
                - On failure: Error string
            If return_value=True (value methods):
                - On success: (value1, value2, ..., None)  # All response fields except success/message, plus None for error
                - On failure: (None, None, ..., error_str) # Nones for all fields plus error string
        """
        try:
            response = func(request)
            if not response.success:
                error_msg = f"{self._get_func_name()} error: {response.message}"
                if return_value:
                    # Get all fields except success/message
                    response_data = {k: v for k, v in response.__dict__.items() if k not in ("success", "message")}
                    # Return Nones for all fields plus error
                    return tuple([None] * len(response_data)) + (error_msg,)
                return error_msg

            # Extract all fields except success and message
            response_data = {k: v for k, v in response.__dict__.items() if k not in ("success", "message")}

            if not response_data:  # If no data fields (like in Empty responses)
                if return_value:
                    return None, None  # Single None + error
                return None

            # Convert dict values to tuple, maintaining order
            values = tuple(response_data.values())
            if return_value:
                return values + (None,)  # Add None as the error value
            return None

        except grpc.RpcError as e:
            error_msg = f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
            if return_value:
                # For connection errors, we don't know the response type yet
                # So we'll return a single None + error
                return None, error_msg
            return error_msg
        except Exception as e:
            error_msg = f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"
            if return_value:
                # For unexpected errors, we don't know the response type yet
                # So we'll return a single None + error
                return None, error_msg
            return error_msg

    # -----------------------------------------------
    #                             Connection Handlers
    # ---------------------------------------------*/
    def connect(self) -> Optional[str]:
        try:
            # Create a gRPC channel
            self.channel = insecure_channel(f"{self.config.net.addr}:{self.config.net.port}")

            # Create a stub using the newly created channel
            self.client = MtibClientV1(self.channel)

            # Health check
            ready, errors, error = self.HealthCheck()
            if error:
                return error

            if not ready:
                return f"Error checking health: {errors}"

            if ready and errors:
                self.logger.error("Server is ready, but there are errors: %s", errors)
                for error in errors:
                    self.logger.error(error)

            self.logger.debug("Connected to MTIB at %s:%d", self.config.net.addr, self.config.net.port)
            return None

        except RpcError as e:
            return f"Failed to connect to MTIB at {self.config.net.addr}:{self.config.net.port}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error when connecting to MTIB at {self.config.net.addr}:{self.config.net.port}. Error: {str(e)}"

    def disconnect(self) -> Optional[str]:
        try:
            if self.channel:
                # Close the gRPC channel if it's open
                self.channel.close()
                return None
            else:
                self.logger.warning(f"No active connection to close for {self.config.net.addr}:{self.config.net.port}")
                return None
        except Exception as e:
            return f"Unexpected error when disconnecting from MTIB at {self.config.net.addr}:{self.config.net.port}. Error: {str(e)}"

    # -----------------------------------------------
    #                                          Health
    # ---------------------------------------------*/
    def HealthCheck(self) -> Tuple[Optional[bool], Optional[List[str]], Optional[str]]:
        """Check the health status of the MTIB device.

        Returns:
            Tuple of (ready status, list of errors if any, error string if failed)
            - On success: (ready, errors, None)
            - On failure: (None, None, error_string)
        """
        try:
            response = self.client.HealthCheck(Empty())
            return response.ready, response.errors, None
        except grpc.RpcError as e:
            return None, None, f"gRPC error for HealthCheck at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, f"Unexpected error in HealthCheck at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                            GPIO
    # ---------------------------------------------*/
    def GpioConfig(self, gpio: int, direction: GpioDirection, resistor: GpioResistorConfig) -> Optional[str]:
        """Configure a GPIO pin's direction and pull resistor.

        Args:
            gpio: Pin number to configure
            direction: Input or output mode
            resistor: Pull-up, pull-down, or no resistor configuration

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.GpioConfig(GpioConfigRequest(gpio=gpio, direction=direction, resistor=resistor))
            if not response.success:
                return f"GpioConfig error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for GpioConfig at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in GpioConfig at {self.config.net.addr}: {str(e)}"

    def GpioWrite(self, gpio: int, state: bool) -> Optional[str]:
        """Set a GPIO pin's output state.

        Args:
            gpio: Pin number to write to
            state: True for high, False for low

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.GpioWrite(GpioWriteRequest(gpio=gpio, state=state))
            if not response.success:
                return f"GpioWrite error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for GpioWrite at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in GpioWrite at {self.config.net.addr}: {str(e)}"

    def GpioRead(self, gpio: int) -> Tuple[Optional[bool], Optional[str]]:
        """Read the current state of a GPIO pin.

        Args:
            gpio: Pin number to read from

        Returns:
            Tuple of (pin state, error if any)
            - On success: (state, None)
            - On failure: (None, error_string)
        """
        try:
            response = self.client.GpioRead(GpioReadRequest(gpio=gpio))
            if not response.success:
                return None, f"GpioRead error: {response.message}"
            return response.state, None
        except grpc.RpcError as e:
            return None, f"gRPC error for GpioRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in GpioRead at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                             ADC
    # ---------------------------------------------*/
    def AdcRead(self, channel: int) -> Tuple[Optional[float], Optional[str]]:
        """Read voltage from a specific ADC channel.

        Args:
            channel: ADC channel number to read from

        Returns:
            Tuple of (voltage in volts, error if any)
        """
        return self._grpc_call(self.client.AdcRead, AdcReadRequest(channel=channel), return_value=True)

    def AdcReadAll(self) -> Tuple[Optional[List[float]], Optional[str]]:
        """Read voltage from all ADC channels.

        Returns:
            Tuple of (list of voltages in volts, error if any)
        """
        return self._grpc_call(self.client.AdcReadAll, Empty(), return_value=True)

    # -----------------------------------------------
    #                                           Power
    # ---------------------------------------------*/
    def DutPowerEnable(self, voltage_v: float) -> Optional[str]:
        """Enable power to the device under test (DUT).

        Args:
            voltage_v: Voltage to apply in volts

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.DutPowerEnable(DutPowerRequest(voltage_v=voltage_v))
            if not response.success:
                return f"DutPowerEnable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DutPowerEnable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DutPowerEnable at {self.config.net.addr}: {str(e)}"

    def DutPowerDisable(self) -> Optional[str]:
        """Disable power to the device under test (DUT).

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.DutPowerDisable(Empty())
            if not response.success:
                return f"DutPowerDisable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DutPowerDisable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DutPowerDisable at {self.config.net.addr}: {str(e)}"

    def DutChargePowerEnable(self) -> Optional[str]:
        """Enable charging power to the device under test (DUT).

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.DutChargePowerEnable(Empty())
            if not response.success:
                return f"DutChargePowerEnable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DutChargePowerEnable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DutChargePowerEnable at {self.config.net.addr}: {str(e)}"

    def DutChargePowerDisable(self) -> Optional[str]:
        """Disable charging power to the device under test (DUT).

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.DutChargePowerDisable(Empty())
            if not response.success:
                return f"DutChargePowerDisable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DutChargePowerDisable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DutChargePowerDisable at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                    Power Consumption
    # ---------------------------------------------*/
    def DutPowerRead(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read the power consumption of the device under test (DUT).

        Returns:
            Tuple of (current in amps, voltage in volts, power in watts, error if any)
        """
        try:
            response = self.client.DutPowerRead(Empty())
            if not response.success:
                return None, None, None, f"DutPowerRead error: {response.message}"
            return response.current_a, response.voltage_v, response.power_w, None
        except grpc.RpcError as e:
            return None, None, None, f"gRPC error for DutPowerRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, None, f"Unexpected error in DutChargePowerDisable at {self.config.net.addr}: {str(e)}"

    def DutChargePowerRead(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read the charging power consumption of the device under test (DUT).

        Returns:
            Tuple of (current in amps, voltage in volts, power in watts, error if any)
        """
        try:
            response = self.client.DutChargePowerRead(Empty())
            if not response.success:
                return None, None, None, f"DutChargePowerRead error: {response.message}"
            return response.current_a, response.voltage_v, response.power_w, None
        except grpc.RpcError as e:
            return None, None, None, f"gRPC error for DutChargePowerRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, None, f"Unexpected error in DutChargePowerRead at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                        Sensors
    # ---------------------------------------------*/
    def AltimeterRead(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read data from the altimeter sensor.

        Returns:
            Tuple of (temperature in °F, pressure in Hg, altitude in feet, error if any)
        """
        return self._grpc_call(self.client.AltimeterRead, Empty(), return_value=True)

    def AccelRead(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read data from the accelerometer sensor.

        Returns:
            Tuple of (x acceleration in g, y acceleration in g, z acceleration in g, error if any)
        """
        return self._grpc_call(self.client.AccelRead, Empty(), return_value=True)

    # -----------------------------------------------
    #                                    FluidNc Config
    # ---------------------------------------------*/
    def GetFluidNcConfig(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the current FluidNC configuration.

        Returns:
            Tuple of (YAML configuration string, error if any)
        """
        return self._grpc_call(self.client.GetFluidNcConfig, Empty(), return_value=True)

    def UpdateFluidNcConfig(self, config_yaml: str) -> Optional[str]:
        """Update the FluidNC configuration.

        Args:
            config_yaml: New configuration in YAML format

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.UpdateFluidNcConfig, UpdateFluidNcConfigRequest(config_yaml=config_yaml))

    # -----------------------------------------------
    #                                         Gcode
    # ---------------------------------------------*/
    def SendGcode(self, command: str) -> Tuple[Optional[str], Optional[str]]:
        """Send a G-code command to the device.

        Args:
            command: G-code command string to send

        Returns:
            Tuple of (device response, error if any)
        """
        return self._grpc_call(self.client.SendGcode, GcodeRequest(command=command), return_value=True)

    # -----------------------------------------------
    #                                  Motion Profiles
    # ---------------------------------------------*/
    def UploadMotionProfile(self, profile: MotionProfile) -> Optional[str]:
        """Upload a new motion profile to the device.

        Args:
            profile: Motion profile containing name, description, and G-code commands

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.UploadMotionProfile, MotionProfileRequest(profile=profile))

    def ListMotionProfiles(self) -> Tuple[Optional[List[MotionProfile]], Optional[str]]:
        """Get a list of all available motion profiles.

        Returns:
            Tuple of (list of motion profiles, error if any)
        """
        return self._grpc_call(self.client.ListMotionProfiles, Empty(), return_value=True)

    def ExecuteMotionProfile(self, profile_name: str) -> Optional[str]:
        """Execute a motion profile by name.

        Args:
            profile_name: Name of the profile to execute

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.ExecuteMotionProfile, ExecuteProfileRequest(profile_name=profile_name))

    def DeleteMotionProfile(self, profile_name: str) -> Optional[str]:
        """Delete a motion profile by name.

        Args:
            profile_name: Name of the profile to delete

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.DeleteMotionProfile, DeleteProfileRequest(profile_name=profile_name))

    def SetDefaultMotionProfile(self, profile_name: str) -> Optional[str]:
        """Set the default motion profile.

        Args:
            profile_name: Name of the profile to set as default

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(
            self.client.SetDefaultMotionProfile, SetDefaultProfileRequest(profile_name=profile_name)
        )

    # -----------------------------------------------
    #                                        Motion
    # ---------------------------------------------*/
    def GetMotionStatus(self) -> Tuple[Optional[MotionStatus], Optional[str]]:
        """Get the current status of the motion system.

        Returns:
            Tuple of (motion status enum, error if any)
        """
        return self._grpc_call(self.client.GetMotionStatus, GetMotionStatusRequest(), return_value=True)

    def MotionStart(self) -> Optional[str]:
        """Start the default motion profile. If no default profile is set, an error will be returned.

        Note: This will block until the motion is complete.

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.MotionStart, Empty())

    def MotionHome(self) -> Optional[str]:
        """Home the motion system to its reference position.

        Note: This will block until the motion is complete.
        Note: MotionStop() will be called automatically if the system is moving.

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.MotionHome, Empty())

    def MotionStop(self) -> Optional[str]:
        """Stop any ongoing motion.

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.MotionStop, Empty())

    # -----------------------------------------------
    #                                      Firmware
    # ---------------------------------------------*/
    def ListProgrammers(self) -> Tuple[Optional[List[Programmer]], Optional[str]]:
        """Get a list of available firmware programmers.

        Returns:
            Tuple of (list of programmer devices, error if any)
        """
        return self._grpc_call(self.client.ListProgrammers, Empty(), return_value=True)

    def ListFwFiles(self) -> Tuple[Optional[List[FwFileInfo]], Optional[str]]:
        """Get a list of available firmware files.

        Returns:
            Tuple of (list of firmware file info, error if any)
        """
        return self._grpc_call(self.client.ListFwFiles, Empty(), return_value=True)

    def UploadFwFile(self, file_path: str, target: HostType) -> Optional[str]:
        """Upload a firmware file to the device using streaming.

        Args:
            file_path: Path to the firmware file to upload
            target: Target host type for the firmware

        Returns:
            None on success, error string on failure
        """
        try:
            # Get file info first
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            # Read file in chunks to avoid loading entire file into memory
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks

            def request_iterator():
                # Stream the file content in chunks
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield UploadFwFileRequest(name=file_name, target=target, content=chunk)

            # Make the streaming call
            try:
                response = self.client.UploadFwFile(request_iterator())
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

    def DeleteFwFile(self, file_info: FwFileInfo) -> Optional[str]:
        """Delete a firmware file from the device.

        Args:
            file_info: Information about the file to delete

        Returns:
            None on success, error string on failure
        """
        return self._grpc_call(self.client.DeleteFwFile, DeleteFwFileRequest(file_info=file_info))

    def FlashFwFile(self, file_info: FwFileInfo) -> Tuple[Optional[int], Optional[str]]:
        """Flash a firmware file to the device.

        Args:
            file_info: Information about the firmware file to flash

        Returns:
            Tuple of (flash time in milliseconds, error if any)
        """
        return self._grpc_call(self.client.FlashFwFile, FlashFwFileRequest(file_info=file_info), return_value=True)

    # -----------------------------------------------
    #                                        Uart
    # ---------------------------------------------*/
    def UartStream(self, target: HostType, request_iterator: Iterator[UartStreamRequest]) -> Iterator[UartStreamResponse]:
        """Stream UART data to/from a target device using a custom request iterator.

        Args:
            target: Target host type (NRF9160, NRF52840, etc.)
            request_iterator: Iterator that yields UartStreamRequest objects

        Yields:
            UartStreamResponse objects containing received data or status
        """
        try:
            # Make the streaming call with the provided request iterator
            response_iterator = self.client.UartStream(request_iterator)
            
            for response in response_iterator:
                yield response
                
        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for UartStream at {self.config.net.addr}. Error: {str(e.details())}")
            yield UartStreamResponse(
                success=False,
                message=f"gRPC error: {str(e.details())}",
                target=target
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in UartStream at {self.config.net.addr}: {str(e)}")
            yield UartStreamResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                target=target
            )

    # -----------------------------------------------
    #                                    Command Interpreter
    # ---------------------------------------------*/
    def _start_cmd_interpreter(self, target: HostType) -> str:
        """Start the command interpreter for a specific target."""
        if self.interpreter_running.get(target, False):
            return "Command interpreter is already running"

        # Initialize queues for this target if not already done
        if target not in self.cmd_responses_queues:
            self.cmd_responses_queues[target] = queue.Queue()
        if target not in self.cmd_requests_queues:
            self.cmd_requests_queues[target] = queue.Queue()

        self.interpreter_running[target] = True
        self.interpreter_threads[target] = threading.Thread(target=self._interpret_commands, args=(target,))
        self.interpreter_threads[target].start()
        return ""

    def _interpret_commands(self, target: HostType):
        """Background thread to interpret commands from the UART stream."""
        buffer = b""

        def request_iterator() -> Iterator[UartStreamRequest]:
            while self.interpreter_running[target]:
                try:
                    request = self.cmd_requests_queues[target].get(
                        timeout=1
                    )  # Use a timeout to regularly check the running flag
                    if request.data == b"STOP":
                        break  # Exit the iterator loop
                    # Ensure the target is set correctly
                    request.target = target
                    yield request
                except queue.Empty:
                    continue

        try:
            self.uart_rpc_streams[target] = self.UartStream(target, request_iterator())
            for response in self.uart_rpc_streams[target]:
                if not self.interpreter_running[target]:
                    break

                data = response.data
                buffer += data

                while len(buffer) > 0:
                    sync_index = buffer.find(struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2))
                    if sync_index == -1:
                        buffer = b""  # Clear buffer if no sync bytes are found
                        break

                    buffer = buffer[sync_index:]

                    if len(buffer) < 5:
                        break

                    payload_length = struct.unpack(">H", buffer[3:5])[0]
                    total_length = 5 + payload_length  # 5 bytes before payload + payload length + CRC

                    if len(buffer) < total_length:
                        break

                    full_response = buffer[:total_length]
                    buffer = buffer[total_length:]

                    try:
                        unpack_format = f">BBBH{payload_length - NUM_CRC_BYTES}sI"
                        sync_byte1, sync_byte2, command_byte, length_field, payload, crc_received = struct.unpack(
                            unpack_format, full_response
                        )

                        # CRC should be calculated from command_byte to the end of the payload, excluding the CRC itself
                        crc_calculated = self._calculate_crc32(full_response[2:-NUM_CRC_BYTES])
                        if crc_received != crc_calculated:
                            self.logger.error(f"CRC mismatch: received {crc_received}, calculated {crc_calculated}")
                            continue

                        self.cmd_responses_queues[target].put(full_response)
                    except Exception as e:
                        self.logger.error(f"An exception occurred whilst trying to unpack response: {e}")
                        break
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.CANCELLED:
                self.logger.error(f"An exception occurred during command interpretation: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in command interpretation: {e}")

    def _stop_cmd_interpreter(self, target: HostType) -> str:
        """Stop the command interpreter for a specific target."""
        if not self.interpreter_running.get(target, False):
            return "Command interpreter is not running"

        # Set the running flag to False
        self.interpreter_running[target] = False

        # Insert a stop request to unblock the iterator
        try:
            stop_request = UartStreamRequest(target=target, data=b"STOP")
            self.cmd_requests_queues[target].put(stop_request)
        except:
            pass

        # Cancel the gRPC call if it exists
        if target in self.uart_rpc_streams and self.uart_rpc_streams[target]:
            try:
                self.uart_rpc_streams[target].cancel()
            except Exception as e:
                self.logger.error(f"Error cancelling UART stream for {target}: {e}")
            self.uart_rpc_streams[target] = None

        # Wait for the interpreter thread to terminate
        if target in self.interpreter_threads and self.interpreter_threads[target]:
            self.interpreter_threads[target].join(timeout=10)  # Wait for a maximum of 10 seconds
            if self.interpreter_threads[target].is_alive():
                self.logger.error(f"Failed to stop the command interpreter thread in time for {target}")
                return f"Failed to stop the command interpreter thread in time for {target}"
            self.interpreter_threads[target] = None

        return ""

    def _send_command(
        self,
        target: HostType,
        command: Sigma5DeviceCommand,
        payload: bytes = b"",
        receive_timeout_ms=RECEIVE_TIMEOUT_MS,
        response_type: Sigma5DeviceCommand = None,
    ) -> Tuple[str, Any]:
        """Send a command to the device and wait for response."""
        try:
            # Start the interpreter handler
            error = self._start_cmd_interpreter(target)
            if error:
                return f"Could not start the command interpreter for {target}, {error}", None

            # Build the command
            sync_bytes = struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2)
            command_byte = struct.pack("B", command.value)
            message_length = struct.pack(">H", len(payload) + NUM_CRC_BYTES)

            crc_value = self._calculate_crc32(command_byte + message_length + payload)
            crc_bytes = struct.pack(">I", crc_value)

            message = sync_bytes + command_byte + message_length + payload + crc_bytes

            # Send the command to the device
            request = UartStreamRequest(target=target, data=message)
            self.cmd_requests_queues[target].put(request)
            try:
                # Await for responses in the queue
                response = self.cmd_responses_queues[target].get(timeout=receive_timeout_ms / 1000.0)

                # Decode the response into the right type
                if response_type is None:
                    parse_error, response = self._parse_response(command, response, self.response_classes[command])
                else:
                    parse_error, response = self._parse_response(
                        response_type, response, self.response_classes[response_type]
                    )
                if parse_error:
                    parse_error = f"Could not parse response for command {command.name} at {target}, {parse_error}"

                # Stop the interpreter
                error = self._stop_cmd_interpreter(target)
                if error:
                    return f"Could not stop the command interpreter for {target}, {error}", None

                return parse_error, response
            except queue.Empty:
                error = self._stop_cmd_interpreter(target)
                if error:
                    return f"Could not stop the command interpreter for {target}, {error}", None

                return f"Response timeout occurred for command {command.name} at {target}", None

        except Exception as e:
            error = self._stop_cmd_interpreter(target)
            if error:
                return f"Could not stop the command interpreter for {target}, {error}", None

            return f"Error sending command {command.name} to target {target}. Error: {str(e)}", None

    def _parse_response(
        self, command: Sigma5DeviceCommand, response: bytes, response_class: Type[CommandResponse]
    ) -> Tuple[str, Any]:
        """Parse a response from the device."""
        try:
            payload_length = struct.unpack(">H", response[3:5])[0]
            unpack_format = f">BBBH{payload_length - NUM_CRC_BYTES}sI"
            sync_byte1, sync_byte2, command_byte, length_field, payload, crc_received = struct.unpack(
                unpack_format, response
            )

            if command == Sigma5DeviceCommand.CMD_NOP:
                command = Sigma5DeviceCommand.CMD_ACK

            if command.value != command_byte:
                return f"Command mismatch. Expected {command.value}, got {command_byte}", None

            crc_calculated = self._calculate_crc32(response[2:-NUM_CRC_BYTES])
            if crc_received != crc_calculated:
                return f"CRC mismatch, expected {crc_calculated}, got {crc_received}", None

            response_object = response_class.from_bytes(payload)
            return "", response_object
        except Exception as e:
            return f"Failed to parse response: {str(e)}", None

    def _calculate_crc32(self, data):
        """Calculate CRC32 for data."""
        return zlib.crc32(data) & 0xFFFFFFFF

    # -----------------------------------------------
    #                                    Device Commands
    # ---------------------------------------------*/
    def dut_command_send_nop(self, target: HostType) -> Tuple[str, CMD_ACK_Response]:
        """Send NOP command to wake up the device."""
        return self._send_command(target, Sigma5DeviceCommand.CMD_NOP, response_type=Sigma5DeviceCommand.CMD_ACK)

    def dut_command_get_sensor_value(self, target: HostType) -> Tuple[str, CMD_GET_SENSOR_VALS_Response]:
        """Get sensor values from the device."""
        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_GET_SENSOR_VALS,
        )

    def dut_command_get_chip_id(self, target: HostType) -> Tuple[str, CMD_POST_Response]:
        """Get chip ID information from the device."""
        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_POST,
        )

    def dut_command_get_imei_iccid(self, target: HostType) -> Tuple[str, CMD_IMEI_ICCID_Response]:
        """Get IMEI and ICCID from the device."""
        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_IMEI_ICCID_GET,
        )

    def dut_command_get_modem_fw(self, target: HostType) -> Tuple[str, CMD_GET_MODEM_FW_VER_Response]:
        """Get modem firmware version from the device."""
        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_GET_MODEM_FW_VER,
        )

    def dut_command_clear_personalization(self, target: HostType) -> Tuple[str, CMD_CLEAR_PERSONALIZATION_Response]:
        """Clear personalization data from the device."""
        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_CLEAR_PERSONALIZATION,
            response_type=Sigma5DeviceCommand.CMD_ACK,  # Use CMD_ACK as the response type
        )

    def dut_command_set_device_eui(self, target: HostType, device_eui: int) -> Tuple[str, CMD_DEV_EC_PUB_KEY_Response]:
        """Set device EUI on the device."""
        # Create the payload
        payload = CMD_PERSONALIZE_DEV_EUI_Response.to_bytes(read=False, device_id=device_eui)

        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
            payload=payload,
            response_type=Sigma5DeviceCommand.CMD_DEV_EC_PUB_KEY,  # We expect a CMD_DEV_EC_PUB_KEY response
        )

    def dut_command_get_device_eui(self, target: HostType) -> Tuple[str, CMD_PERSONALIZE_DEV_EUI_Response]:
        """Get device EUI from the device."""
        payload = CMD_PERSONALIZE_DEV_EUI_Response.to_bytes(read=True, device_id=0xDEADBEEFDEADBEEF)

        # Wake up the device
        self.dut_command_send_nop(target)
        time.sleep(1)

        # Send the command
        return self._send_command(
            target,
            Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
            payload=payload,
            response_type=Sigma5DeviceCommand.CMD_PERSONALIZE_DEV_EUI,
        )
