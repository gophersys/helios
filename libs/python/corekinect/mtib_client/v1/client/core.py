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
                # For connection errors, we need to determine the expected return structure
                # by calling the function with a mock request to get the response type
                try:
                    # Try to get the response type by calling the function
                    mock_response = func(request)
                    response_data = {
                        k: v for k, v in mock_response.__dict__.items() if k not in ("success", "message")
                    }
                    return tuple([None] * len(response_data)) + (error_msg,)
                except:
                    # If we can't determine the structure, return a single None + error
                    return None, error_msg
            return error_msg
        except Exception as e:
            error_msg = f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"
            if return_value:
                # For unexpected errors, we need to determine the expected return structure
                try:
                    # Try to get the response type by calling the function
                    mock_response = func(request)
                    response_data = {
                        k: v for k, v in mock_response.__dict__.items() if k not in ("success", "message")
                    }
                    return tuple([None] * len(response_data)) + (error_msg,)
                except:
                    # If we can't determine the structure, return a single None + error
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
        try:
            response = self.client.AdcRead(AdcReadRequest(channel=channel))
            if not response.success:
                return None, f"AdcRead error: {response.message}"
            return response.voltage_v, None
        except grpc.RpcError as e:
            return None, f"gRPC error for AdcRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in AdcRead at {self.config.net.addr}: {str(e)}"

    def AdcReadAll(self) -> Tuple[Optional[List[float]], Optional[str]]:
        """Read voltage from all ADC channels.

        Returns:
            Tuple of (list of voltages in volts, error if any)
        """
        try:
            response = self.client.AdcReadAll(Empty())
            if not response.success:
                return None, f"AdcReadAll error: {response.message}"
            return response.voltages, None
        except grpc.RpcError as e:
            return None, f"gRPC error for AdcReadAll at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in AdcReadAll at {self.config.net.addr}: {str(e)}"

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
            return (
                None,
                None,
                None,
                f"gRPC error for DutPowerRead at {self.config.net.addr}. Error: {str(e.details())}",
            )
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
            return (
                None,
                None,
                None,
                f"gRPC error for DutChargePowerRead at {self.config.net.addr}. Error: {str(e.details())}",
            )
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
        try:
            response = self.client.AltimeterRead(Empty())
            if not response.success:
                return None, None, None, f"AltimeterRead error: {response.message}"
            return response.temperature_f, response.pressure_hg, response.altitude_ft, None
        except grpc.RpcError as e:
            return (
                None,
                None,
                None,
                f"gRPC error for AltimeterRead at {self.config.net.addr}. Error: {str(e.details())}",
            )
        except Exception as e:
            return None, None, None, f"Unexpected error in AltimeterRead at {self.config.net.addr}: {str(e)}"

    def AccelRead(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read data from the accelerometer sensor.

        Returns:
            Tuple of (x acceleration in g, y acceleration in g, z acceleration in g, error if any)
        """
        try:
            response = self.client.AccelRead(Empty())
            if not response.success:
                return None, None, None, f"AccelRead error: {response.message}"
            return response.x_g, response.y_g, response.z_g, None
        except grpc.RpcError as e:
            return None, None, None, f"gRPC error for AccelRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, None, f"Unexpected error in AccelRead at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                    FluidNc Config
    # ---------------------------------------------*/
    def GetFluidNcConfig(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the current FluidNC configuration.

        Returns:
            Tuple of (YAML configuration string, error if any)
        """
        try:
            response = self.client.GetFluidNcConfig(Empty())
            if not response.success:
                return None, f"GetFluidNcConfig error: {response.message}"
            return response.config_yaml, None
        except grpc.RpcError as e:
            return None, f"gRPC error for GetFluidNcConfig at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in GetFluidNcConfig at {self.config.net.addr}: {str(e)}"

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
        try:
            response = self.client.SendGcode(GcodeRequest(command=command))
            if not response.success:
                return None, f"SendGcode error: {response.message}"
            return response.response, None
        except grpc.RpcError as e:
            return None, f"gRPC error for SendGcode at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in SendGcode at {self.config.net.addr}: {str(e)}"

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
        try:
            response = self.client.UploadMotionProfile(MotionProfileRequest(profile=profile))
            if not response.success:
                return f"UploadMotionProfile error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for UploadMotionProfile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in UploadMotionProfile at {self.config.net.addr}: {str(e)}"

    def ListMotionProfiles(self) -> Tuple[Optional[List[MotionProfile]], Optional[str]]:
        """Get a list of all available motion profiles.

        Returns:
            Tuple of (list of motion profiles, error if any)
        """
        try:
            response = self.client.ListMotionProfiles(Empty())
            if not response.success:
                return None, f"ListMotionProfiles error: {response.message}"
            return response.profiles, None
        except grpc.RpcError as e:
            return None, f"gRPC error for ListMotionProfiles at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in ListMotionProfiles at {self.config.net.addr}: {str(e)}"

    def ExecuteMotionProfile(self, profile_name: str) -> Optional[str]:
        """Execute a motion profile by name.

        Args:
            profile_name: Name of the profile to execute

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.ExecuteMotionProfile(ExecuteProfileRequest(profile_name=profile_name))
            if not response.success:
                return f"ExecuteMotionProfile error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for ExecuteMotionProfile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in ExecuteMotionProfile at {self.config.net.addr}: {str(e)}"

    def DeleteMotionProfile(self, profile_name: str) -> Optional[str]:
        """Delete a motion profile by name.

        Args:
            profile_name: Name of the profile to delete

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.DeleteMotionProfile(DeleteProfileRequest(profile_name=profile_name))
            if not response.success:
                return f"DeleteMotionProfile error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DeleteMotionProfile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DeleteMotionProfile at {self.config.net.addr}: {str(e)}"

    def SetDefaultMotionProfile(self, profile_name: str) -> Optional[str]:
        """Set the default motion profile.

        Args:
            profile_name: Name of the profile to set as default

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.SetDefaultMotionProfile(SetDefaultProfileRequest(profile_name=profile_name))
            if not response.success:
                return f"SetDefaultMotionProfile error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for SetDefaultMotionProfile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in SetDefaultMotionProfile at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                        Motion
    # ---------------------------------------------*/
    def GetMotionStatus(self) -> Tuple[Optional[MotionStatus], Optional[str]]:
        """Get the current status of the motion system.

        Returns:
            Tuple of (motion status enum, error if any)
        """
        try:
            response = self.client.GetMotionStatus(GetMotionStatusRequest())
            if not response.success:
                return None, f"GetMotionStatus error: {response.message}"
            return response.status, None
        except grpc.RpcError as e:
            return None, f"gRPC error for GetMotionStatus at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in GetMotionStatus at {self.config.net.addr}: {str(e)}"

    def MotionStart(self) -> Optional[str]:
        """Start the default motion profile. If no default profile is set, an error will be returned.

        Note: This will block until the motion is complete.

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.MotionStart(Empty())
            if not response.success:
                return f"MotionStart error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for MotionStart at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in MotionStart at {self.config.net.addr}: {str(e)}"

    def MotionHome(self) -> Optional[str]:
        """Home the motion system to its reference position.

        Note: This will block until the motion is complete.
        Note: MotionStop() will be called automatically if the system is moving.

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.MotionHome(Empty())
            if not response.success:
                return f"MotionHome error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for MotionHome at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in MotionHome at {self.config.net.addr}: {str(e)}"

    def MotionStop(self) -> Optional[str]:
        """Stop any ongoing motion.

        Returns:
            None on success, error string on failure
        """
        try:
            response = self.client.MotionStop(Empty())
            if not response.success:
                return f"MotionStop error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for MotionStop at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in MotionStop at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                      Firmware
    # ---------------------------------------------*/
    def ListProgrammers(self) -> Tuple[Optional[List[Programmer]], Optional[str]]:
        """Get a list of available firmware programmers.

        Returns:
            Tuple of (list of programmer devices, error if any)
        """
        try:
            response = self.client.ListProgrammers(Empty())
            if not response.success:
                return None, f"ListProgrammers error: {response.message}"
            return response.programmers, None
        except grpc.RpcError as e:
            return None, f"gRPC error for ListProgrammers at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in ListProgrammers at {self.config.net.addr}: {str(e)}"

    def ListFwFiles(self) -> Tuple[Optional[List[FwFileInfo]], Optional[str]]:
        """Get a list of available firmware files.

        Returns:
            Tuple of (list of firmware file info, error if any)
        """
        try:
            response = self.client.ListFwFiles(Empty())
            if not response.success:
                return None, f"ListFwFiles error: {response.message}"
            return response.files, None
        except grpc.RpcError as e:
            return None, f"gRPC error for ListFwFiles at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in ListFwFiles at {self.config.net.addr}: {str(e)}"

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
                    first_chunk = True
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        if first_chunk:
                            # First request contains name, target, and first chunk
                            request = UploadFwFileRequest()
                            request.name = file_name
                            request.target = target
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
        try:
            response = self.client.DeleteFwFile(DeleteFwFileRequest(file_info=file_info))
            if not response.success:
                return f"DeleteFwFile error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for DeleteFwFile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in DeleteFwFile at {self.config.net.addr}: {str(e)}"

    def FlashFwFile(
        self, file_info: FwFileInfo, sector_erase: bool = False, recover: bool = False
    ) -> Tuple[Optional[int], Optional[str]]:
        """Flash a firmware file to the device.

        Args:
            file_info: Information about the firmware file to flash
            sector_erase: Whether to perform sector erase before flashing
            recover: Whether to recover the device before flashing

        Returns:
            Tuple of (flash time in milliseconds, error if any)
        """
        try:
            response = self.client.FlashFwFile(
                FlashFwFileRequest(file_info=file_info, sector_erase=sector_erase, recover=recover)
            )
            if not response.success:
                return None, f"FlashFwFile error: {response.message}"
            return response.time_ms, None
        except grpc.RpcError as e:
            return None, f"gRPC error for FlashFwFile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in FlashFwFile at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                        Uart
    # ---------------------------------------------*/
    def UartStream(
        self, target: HostType, request_iterator: Iterator[UartStreamRequest]
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
            response_iterator = self.client.UartStream(request_iterator)

            for response in response_iterator:
                yield response

        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for UartStream at {self.config.net.addr}. Error: {str(e.details())}")
            yield UartStreamResponse(success=False, message=f"gRPC error: {str(e.details())}", target=target)
        except Exception as e:
            self.logger.error(f"Unexpected error in UartStream at {self.config.net.addr}: {str(e)}")
            yield UartStreamResponse(success=False, message=f"Unexpected error: {str(e)}", target=target)

    def alpha_cmd_personalize(
        self, device_id: str, target: HostType
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Send a UART command to personalize the device using the given device_id.
        Opens a new UART stream, hits ENTER to get prompt, then sends the personalize command,
        and parses the response to extract the public key data.

        Returns:
            Tuple of (hex_public_key, base64_public_key, error_string)
        """
        from protocols.mtib.mtib_pb2 import UartStreamRequest
        import time
        import queue

        # Use queues like the working terminal
        input_queue = queue.Queue()
        output_queue = queue.Queue()

        # Add commands to input queue
        input_queue.put(b"\r")  # Hit ENTER to get prompt
        time.sleep(0.2)
        input_queue.put(f"personalize {device_id}\r".encode("utf-8"))  # Send command

        def request_iterator():
            while True:
                try:
                    # Get input from queue (non-blocking)
                    data = input_queue.get_nowait()
                    yield UartStreamRequest(target=target, data=data)
                except queue.Empty:
                    # No input, send empty request to keep stream alive
                    yield UartStreamRequest(target=target, data=b"")
                    time.sleep(0.1)

        # Collect response like the working terminal
        response_lines = []
        start_time = time.time()
        timeout = 10  # 10 second timeout

        for resp in self.UartStream(target, request_iterator()):
            if resp.data:
                line = resp.data.decode("utf-8", errors="ignore")
                response_lines.append(line)

                # Check if we got the public keys (wait for actual data)
                full_response = "".join(response_lines)
                if "Public key (hex)" in full_response and "Public key (base64)" in full_response:
                    # Look for the actual hex key data
                    hex_pos = full_response.find("Public key (hex)")
                    if hex_pos != -1:
                        hex_colon_pos = full_response.find(":", hex_pos)
                        if hex_colon_pos != -1:
                            hex_data_start = hex_colon_pos + 1
                            hex_data_end = full_response.find("\n", hex_data_start)
                            if hex_data_end != -1:
                                hex_data = full_response[hex_data_start:hex_data_end].strip()
                                # Only break if we have actual hex data (not empty)
                                if hex_data and hex_data != "" and len(hex_data) > 10:
                                    break

            if not resp.success:
                break

            # Timeout check
            if time.time() - start_time > timeout:
                break

        # Parse the response for public keys
        hex_key = None
        base64_key = None

        full_response = "".join(response_lines)

        # Look for hex public key (handle variable spacing)
        hex_start = full_response.find("Public key (hex)")
        if hex_start != -1:
            # Find the colon after "Public key (hex)"
            colon_pos = full_response.find(":", hex_start)
            if colon_pos != -1:
                hex_start = colon_pos + 1
                hex_end = full_response.find("\n", hex_start)
                if hex_end != -1:
                    hex_key = full_response[hex_start:hex_end].strip()

        # Look for base64 public key (handle variable spacing)
        base64_start = full_response.find("Public key (base64)")
        if base64_start != -1:
            # Find the colon after "Public key (base64)"
            colon_pos = full_response.find(":", base64_start)
            if colon_pos != -1:
                base64_start = colon_pos + 1
                base64_end = full_response.find("\n", base64_start)
                if base64_end != -1:
                    base64_key = full_response[base64_start:base64_end].strip()

        if hex_key and base64_key:
            return hex_key, base64_key, None
        else:
            return None, None, f"Failed to parse public keys from response: {full_response}"

    def alpha_cmd_get_imei_iccids(
        self, device_id: str, target: HostType
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Send a UART command to get the device IMEI and ICCIDs.
        Opens a new UART stream, hits ENTER to get prompt, then sends the imei_ccid command,
        and parses the response to extract the IMEI and ICCIDs.

        Returns:
            Tuple of (imei, iccids, error_string)
        """
        from protocols.mtib.mtib_pb2 import UartStreamRequest
        import time
        import queue

        # Use queues like the working terminal
        input_queue = queue.Queue()
        output_queue = queue.Queue()

        # Add commands to input queue
        input_queue.put(b"\r")  # Hit ENTER to get prompt
        time.sleep(0.2)
        input_queue.put(b"imei_ccid\r")  # Send command

        def request_iterator():
            while True:
                try:
                    # Get input from queue (non-blocking)
                    data = input_queue.get_nowait()
                    yield UartStreamRequest(target=target, data=data)
                except queue.Empty:
                    # No input, send empty request to keep stream alive
                    yield UartStreamRequest(target=target, data=b"")
                    time.sleep(0.1)

        # Collect response like the working terminal
        response_lines = []
        start_time = time.time()
        timeout = 10  # 10 second timeout

        for resp in self.UartStream(target, request_iterator()):
            if resp.data:
                line = resp.data.decode("utf-8", errors="ignore")
                response_lines.append(line)

                # Check if we got the IMEI/ICCID response (wait for actual data)
                full_response = "".join(response_lines)
                if "IMEI,ICCID" in full_response:
                    # Look for the actual data after the colon
                    imei_pos = full_response.find("IMEI,ICCID")
                    if imei_pos != -1:
                        colon_pos = full_response.find(":", imei_pos)
                        if colon_pos != -1:
                            data_start = colon_pos + 1
                            data_end = full_response.find("\n", data_start)
                            if data_end != -1:
                                data_line = full_response[data_start:data_end].strip()
                                # Only break if we have actual data
                                if data_line and data_line != "" and "," in data_line:
                                    break

            if not resp.success:
                break

            # Timeout check
            if time.time() - start_time > timeout:
                break

        # Parse the response for IMEI and ICCIDs
        imei = None
        iccids = None

        full_response = "".join(response_lines)

        # Look for IMEI,ICCID line (handle both direct response and modem log response)
        imei_start = full_response.find("IMEI,ICCID")
        if imei_start != -1:
            # Find the colon after "IMEI,ICCID"
            colon_pos = full_response.find(":", imei_start)
            if colon_pos != -1:
                data_start = colon_pos + 1
                data_end = full_response.find("\n", data_start)
                if data_end != -1:
                    data_line = full_response[data_start:data_end].strip()
                    # Only process if we have actual data (not empty)
                    if data_line and data_line != "":
                        # Split by comma to get IMEI and ICCIDs
                        parts = data_line.split(",")
                        if len(parts) >= 1:  # Allow at least 1 value (could be just ICCID)
                            if len(parts) >= 2:
                                # We have IMEI and ICCID(s)
                                imei = parts[0].strip()
                                # Join the rest as ICCIDs (there might be 1 or 2 ICCIDs)
                                iccids = ",".join(parts[1:]).strip()
                            else:
                                # We only have one value, treat it as ICCID
                                imei = "unknown"  # or could be None
                                iccids = parts[0].strip()

        if imei and iccids:
            return imei, iccids, None
        else:
            return None, None, f"Failed to parse IMEI/ICCIDs from response: {full_response}"
