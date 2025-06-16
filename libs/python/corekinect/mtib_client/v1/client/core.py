# Standard includes
import inspect
from typing import Optional, Tuple, List, Iterator
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
    # TODO: Implement UartStream
