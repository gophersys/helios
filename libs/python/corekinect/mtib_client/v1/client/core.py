# Standard includes
import inspect
import os
import queue
import re
import struct
import threading
import time
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, List, Optional, Tuple, Type

# 3rd Party includes
import grpc

# Corekinect includes
from corekinect.utils import Logger
from grpc import RpcError, insecure_channel

# Import actual protobuf types for UART streaming and motion streaming
from protocols.mtib.mtib_pb2 import (
    MotionStartRequest,
    MotionStartResponse,
    UartStreamRequest,
    UartStreamResponse,
)

# Protocol includes
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub as MtibClientV1

from .config import *

# Private includes
from .types import *

# Global timeout constant for all gRPC calls (in seconds)
# This prevents functions from hanging forever if the server dies or disconnects
DEFAULT_GRPC_TIMEOUT_SECONDS = 10


class MtibV1Client:
    """gRPC client for communicating with MTIB (Motion Test Interface Board) devices.

    This client provides a high-level interface for controlling and monitoring
    MTIB hardware including GPIO, ADC, power management, sensors, motion control,
    firmware operations, and UART communication.

    Attributes:
        config: Client configuration containing network settings
        logger: Logger instance for debugging and error reporting

    Example:
        ```python
        from corekinect.mtib_client.v1 import MtibV1Client, NetConfig

        config = MtibV1Client.Config(net=NetConfig(addr="192.168.1.100", port=50051))
        client = MtibV1Client(config)
        error = client.connect()
        if error:
            print(f"Connection failed: {error}")
        else:
            # Use client methods...
            client.disconnect()
        ```
    """

    # -----------------------------------------------
    #                                          Config
    # ---------------------------------------------*/
    class Config:
        """Configuration for the MTIB client.

        Attributes:
            net: Network configuration for gRPC connection
        """

        def __init__(
            self,
            net: NetConfig = NetConfig(),
        ):
            """Initialize client configuration.

            Args:
                net: Network configuration with address and port. Defaults to localhost:50051.
            """
            self.net: NetConfig = net

    # -----------------------------------------------
    #                                          Init
    # ---------------------------------------------*/
    def __init__(self, config: Config, logger: Logger = None):
        """Initialize the MTIB client.

        Args:
            config: Client configuration containing network settings
            logger: Optional logger instance. If None, creates a new logger with name "mtib_client_v1"
        """
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
        """Get the name of the calling function for error messages.

        Returns:
            str: Name of the calling function
        """
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
        """Establish a connection to the MTIB device.

        Creates a gRPC channel and performs a health check to verify connectivity.
        The connection must be established before calling any other methods.

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.connect()
            if error:
                print(f"Failed to connect: {error}")
            ```
        """
        try:
            # Create a gRPC channel
            self.channel = insecure_channel(f"{self.config.net.addr}:{self.config.net.port}")

            # Create a stub using the newly created channel
            self.client = MtibClientV1(self.channel)

            # Health check
            ready, errors, error = self.HealthCheck(DEFAULT_GRPC_TIMEOUT_SECONDS)
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
        """Close the connection to the MTIB device.

        Closes the gRPC channel. Safe to call even if not connected.

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.disconnect()
            if error:
                print(f"Error disconnecting: {error}")
            ```
        """
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
    def HealthCheck(
        self, timeout: int = DEFAULT_GRPC_TIMEOUT_SECONDS
    ) -> Tuple[Optional[bool], Optional[List[str]], Optional[str]]:
        """Check the health status of the MTIB device.

        Args:
            timeout: Timeout in seconds for the health check. Defaults to DEFAULT_GRPC_TIMEOUT_SECONDS.

        Returns:
            Tuple[Optional[bool], Optional[List[str]], Optional[str]]: A tuple containing:
                - ready (Optional[bool]): True if device is ready, False if not ready, None on error
                - errors (Optional[List[str]]): List of error messages if device reports issues, None on error
                - error (Optional[str]): Error message string if the check failed, None on success

        Example:
            ```python
            ready, errors, error = client.HealthCheck(timeout=5)
            if error:
                print(f"Health check failed: {error}")
            elif not ready:
                print(f"Device not ready. Errors: {errors}")
            else:
                print("Device is healthy")
            ```
        """
        try:
            response = self.client.HealthCheck(Empty(), timeout=timeout)
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
            direction: Input or output mode (GpioDirection.GPIO_DIRECTION_INPUT or GpioDirection.GPIO_DIRECTION_OUTPUT)
            resistor: Pull-up, pull-down, or no resistor configuration
                (GpioResistorConfig.GPIO_RESISTOR_PULL_UP, GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN, or GpioResistorConfig.GPIO_RESISTOR_NONE)

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            from corekinect.mtib_client.v1 import GpioDirection, GpioResistorConfig

            error = client.GpioConfig(
                gpio=5,
                direction=GpioDirection.GPIO_DIRECTION_OUTPUT,
                resistor=GpioResistorConfig.GPIO_RESISTOR_NONE
            )
            if error:
                print(f"GPIO config failed: {error}")
            ```
        """
        try:
            response = self.client.GpioConfig(
                GpioConfigRequest(gpio=gpio, direction=direction, resistor=resistor),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
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
            state: True for high (logic 1), False for low (logic 0)

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.GpioWrite(gpio=5, state=True)
            if error:
                print(f"GPIO write failed: {error}")
            ```
        """
        try:
            response = self.client.GpioWrite(
                GpioWriteRequest(gpio=gpio, state=state), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS
            )
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
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - state (Optional[bool]): True if pin is high, False if low, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            state, error = client.GpioRead(gpio=5)
            if error:
                print(f"GPIO read failed: {error}")
            else:
                print(f"GPIO pin 5 state: {state}")
            ```
        """
        try:
            response = self.client.GpioRead(GpioReadRequest(gpio=gpio), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[float], Optional[str]]: A tuple containing:
                - voltage_v (Optional[float]): Voltage reading in volts, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            voltage, error = client.AdcRead(channel=0)
            if error:
                print(f"ADC read failed: {error}")
            else:
                print(f"Channel 0 voltage: {voltage}V")
            ```
        """
        try:
            response = self.client.AdcRead(AdcReadRequest(channel=channel), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[List[float]], Optional[str]]: A tuple containing:
                - voltages_v (Optional[List[float]]): List of voltage readings in volts (one per channel), None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            voltages, error = client.AdcReadAll()
            if error:
                print(f"ADC read all failed: {error}")
            else:
                for i, voltage in enumerate(voltages):
                    print(f"Channel {i}: {voltage}V")
            ```
        """
        try:
            response = self.client.AdcReadAll(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return None, f"AdcReadAll error: {response.message}"
            return response.voltages_v, None
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
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.DutPowerEnable(voltage_v=3.3)
            if error:
                print(f"Power enable failed: {error}")
            ```
        """
        try:
            response = self.client.DutPowerEnable(
                DutPowerRequest(voltage_v=voltage_v), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS
            )
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
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.DutPowerDisable()
            if error:
                print(f"Power disable failed: {error}")
            ```
        """
        try:
            response = self.client.DutPowerDisable(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.DutChargePowerEnable()
            if error:
                print(f"Charge power enable failed: {error}")
            ```
        """
        try:
            response = self.client.DutChargePowerEnable(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.DutChargePowerDisable()
            if error:
                print(f"Charge power disable failed: {error}")
            ```
        """
        try:
            response = self.client.DutChargePowerDisable(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]: A tuple containing:
                - current_a (Optional[float]): Current consumption in amps, None on error
                - voltage_v (Optional[float]): Voltage in volts, None on error
                - power_w (Optional[float]): Power consumption in watts, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            current, voltage, power, error = client.DutPowerRead()
            if error:
                print(f"Power read failed: {error}")
            else:
                print(f"Current: {current}A, Voltage: {voltage}V, Power: {power}W")
            ```
        """
        try:
            response = self.client.DutPowerRead(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]: A tuple containing:
                - current_a (Optional[float]): Charging current in amps, None on error
                - voltage_v (Optional[float]): Charging voltage in volts, None on error
                - power_w (Optional[float]): Charging power in watts, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            current, voltage, power, error = client.DutChargePowerRead()
            if error:
                print(f"Charge power read failed: {error}")
            else:
                print(f"Charge Current: {current}A, Voltage: {voltage}V, Power: {power}W")
            ```
        """
        try:
            response = self.client.DutChargePowerRead(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]: A tuple containing:
                - temperature_f (Optional[float]): Temperature in Fahrenheit, None on error
                - pressure_hg (Optional[float]): Pressure in inches of mercury (Hg), None on error
                - altitude_ft (Optional[float]): Altitude in feet, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            temp, pressure, altitude, error = client.AltimeterRead()
            if error:
                print(f"Altimeter read failed: {error}")
            else:
                print(f"Temp: {temp}°F, Pressure: {pressure}Hg, Altitude: {altitude}ft")
            ```
        """
        try:
            response = self.client.AltimeterRead(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]: A tuple containing:
                - x_g (Optional[float]): X-axis acceleration in g-force, None on error
                - y_g (Optional[float]): Y-axis acceleration in g-force, None on error
                - z_g (Optional[float]): Z-axis acceleration in g-force, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            x, y, z, error = client.AccelRead()
            if error:
                print(f"Accelerometer read failed: {error}")
            else:
                print(f"Acceleration: X={x}g, Y={y}g, Z={z}g")
            ```
        """
        try:
            response = self.client.AccelRead(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return None, None, None, f"AccelRead error: {response.message}"
            return response.x_g, response.y_g, response.z_g, None
        except grpc.RpcError as e:
            return None, None, None, f"gRPC error for AccelRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, None, f"Unexpected error in AccelRead at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                        Motion
    # ---------------------------------------------*/
    def GetMotionStatus(self) -> Tuple[Optional[MotionStatus], Optional[str]]:
        """Get the current status of the motion system.

        Returns:
            Tuple[Optional[MotionStatus], Optional[str]]: A tuple containing:
                - status (Optional[MotionStatus]): Current motion status (IDLE, MOVING, ERRORED), None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            from corekinect.mtib_client.v1.client.types import MotionStatus

            status, error = client.GetMotionStatus()
            if error:
                print(f"Get motion status failed: {error}")
            elif status == MotionStatus.MOVING:
                print("Motion system is currently moving")
            ```
        """
        try:
            response = self.client.GetMotionStatus(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return None, f"GetMotionStatus error: {response.message}"
            return response.status, None
        except grpc.RpcError as e:
            return None, f"gRPC error for GetMotionStatus at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in GetMotionStatus at {self.config.net.addr}: {str(e)}"

    def MotionStart(
        self,
        duration_seconds: int,
        dwell_seconds: int,
        speed_mm_s: int,
        distance_mm: float = 0.0,
        accel_mm_s2: int = 600,
    ) -> Iterator[MotionStartResponse]:
        """Start the motion system with streaming progress updates.

        This method returns an iterator that yields progress updates during motion.
        The first message contains success status, and subsequent messages contain
        progress information while the motion is running.

        Args:
            duration_seconds: Duration of motion in seconds (ignored if distance_mm > 0)
            dwell_seconds: Dwell time in seconds (pause time at end of motion)
            speed_mm_s: Speed in millimeters per second
            distance_mm: Optional distance override in mm. If > 0, overrides duration-based calculation
            accel_mm_s2: Acceleration in mm/s². Defaults to 600

        Yields:
            Iterator[MotionStartResponse]: Iterator of MotionStartResponse objects containing:
                - success (bool): True if motion started successfully
                - message (str): Status or error message
                - progress information (if available in response)

        Example:
            ```python
            for response in client.MotionStart(
                duration_seconds=10,
                dwell_seconds=2,
                speed_mm_s=100,
                accel_mm_s2=600
            ):
                if not response.success:
                    print(f"Motion error: {response.message}")
                    break
                print(f"Motion progress: {response.message}")
            ```
        """
        try:
            # Make the streaming call
            # Handle oneof: if distance_mm > 0, use distance-based, otherwise use duration-based
            if distance_mm > 0:
                request = MotionStartRequest(
                    dwell_seconds=dwell_seconds,
                    speed_mm_s=speed_mm_s,
                    distance_mm=int(distance_mm),
                    accel_mm_s2=accel_mm_s2,
                )
            else:
                request = MotionStartRequest(
                    duration_seconds=int(duration_seconds),
                    dwell_seconds=dwell_seconds,
                    speed_mm_s=speed_mm_s,
                    accel_mm_s2=accel_mm_s2,
                )

            response_iterator = self.client.MotionStart(request)

            for response in response_iterator:
                yield response

        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for MotionStart at {self.config.net.addr}. Error: {str(e.details())}")
            yield MotionStartResponse(success=False, message=f"gRPC error: {str(e.details())}")
        except Exception as e:
            self.logger.error(f"Unexpected error in MotionStart at {self.config.net.addr}: {str(e)}")
            yield MotionStartResponse(success=False, message=f"Unexpected error: {str(e)}")

    def MotionHome(self) -> Optional[str]:
        """Home the motion system to its reference position.

        This method blocks until the motion is complete. If the system is already
        moving, MotionStop() will be called automatically before homing.

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.MotionHome()
            if error:
                print(f"Motion home failed: {error}")
            else:
                print("Motion system homed successfully")
            ```
        """
        try:
            response = self.client.MotionHome(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return f"MotionHome error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for MotionHome at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in MotionHome at {self.config.net.addr}: {str(e)}"

    def MotionStop(self) -> Optional[str]:
        """Stop any ongoing motion immediately.

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            error = client.MotionStop()
            if error:
                print(f"Motion stop failed: {error}")
            ```
        """
        try:
            response = self.client.MotionStop(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[List[Programmer]], Optional[str]]: A tuple containing:
                - programmers (Optional[List[Programmer]]): List of available programmer devices, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            programmers, error = client.ListProgrammers()
            if error:
                print(f"List programmers failed: {error}")
            else:
                for prog in programmers:
                    print(f"Programmer: {prog.type}, Host: {prog.host}")
            ```
        """
        try:
            response = self.client.ListProgrammers(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
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
            Tuple[Optional[List[FwFileInfo]], Optional[str]]: A tuple containing:
                - files (Optional[List[FwFileInfo]]): List of firmware file information, None on error
                - error (Optional[str]): Error message string if read failed, None on success

        Example:
            ```python
            files, error = client.ListFwFiles()
            if error:
                print(f"List firmware files failed: {error}")
            else:
                for fw_file in files:
                    print(f"Firmware: {fw_file.name}, Size: {fw_file.size}")
            ```
        """
        try:
            response = self.client.ListFwFiles(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return None, f"ListFwFiles error: {response.message}"
            return response.files, None
        except grpc.RpcError as e:
            return None, f"gRPC error for ListFwFiles at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in ListFwFiles at {self.config.net.addr}: {str(e)}"

    def UploadFwFile(self, file_path: str, target: HostType) -> Optional[str]:
        """Upload a firmware file to the device using streaming.

        The file is uploaded in chunks to avoid loading the entire file into memory.
        This method uses gRPC streaming for efficient file transfer.

        Args:
            file_path: Path to the firmware file to upload
            target: Target host type for the firmware (e.g., HostType.HOST_TYPE_NRF9160)

        Returns:
            Optional[str]: None on success, error message string on failure

        Raises:
            FileNotFoundError: If the file does not exist (caught and returned as error string)
            PermissionError: If file cannot be read (caught and returned as error string)

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import HostType

            error = client.UploadFwFile(
                file_path="/path/to/firmware.hex",
                target=HostType.HOST_TYPE_NRF9160
            )
            if error:
                print(f"Upload failed: {error}")
            ```
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
            file_info: Information about the file to delete (obtained from ListFwFiles)

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            files, error = client.ListFwFiles()
            if not error and files:
                error = client.DeleteFwFile(files[0])
                if error:
                    print(f"Delete failed: {error}")
            ```
        """
        try:
            response = self.client.DeleteFwFile(
                DeleteFwFileRequest(file_info=file_info), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS
            )
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
            file_info: Information about the firmware file to flash (obtained from ListFwFiles)
            sector_erase: Whether to perform sector erase before flashing. Defaults to False
            recover: Whether to recover the device before flashing. Defaults to False

        Returns:
            Tuple[Optional[int], Optional[str]]: A tuple containing:
                - time_ms (Optional[int]): Flash operation time in milliseconds, None on error
                - error (Optional[str]): Error message string if flash failed, None on success

        Example:
            ```python
            files, error = client.ListFwFiles()
            if not error and files:
                time_ms, error = client.FlashFwFile(files[0], sector_erase=True)
                if error:
                    print(f"Flash failed: {error}")
                else:
                    print(f"Flash completed in {time_ms}ms")
            ```
        """
        try:
            response = self.client.FlashFwFile(
                FlashFwFileRequest(file_info=file_info, sector_erase=sector_erase, recover=recover),
            )
            if not response.success:
                return None, f"FlashFwFile error: {response.message}"
            return response.time_ms, None
        except grpc.RpcError as e:
            return None, f"gRPC error for FlashFwFile at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in FlashFwFile at {self.config.net.addr}: {str(e)}"

    def EraseFlash(self, target: HostType, recover: bool = False) -> Optional[str]:
        """Erase the flash memory on a target device.

        Args:
            target: Target host type (e.g., HostType.HOST_TYPE_NRF9160)
            recover: If True, uses --recover which erases all user flash memory, UICR,
                    and readback protection mechanism. If False, uses --chiperase which
                    erases all available non-volatile memory and UICR. Defaults to False

        Returns:
            Optional[str]: None on success, error message string on failure

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import HostType

            error = client.EraseFlash(target=HostType.HOST_TYPE_NRF9160, recover=False)
            if error:
                print(f"Erase flash failed: {error}")
            ```
        """
        try:
            response = self.client.EraseFlash(EraseFlashRequest(target=target, recover=recover))
            if not response.success:
                return f"EraseFlash error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for EraseFlash at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in EraseFlash at {self.config.net.addr}: {str(e)}"

    def EnableAppProtect(self, target: HostType) -> Tuple[Optional[bool], Optional[str]]:
        """Enable App Protect on a target device.

        Args:
            target: Target host type (e.g., HostType.HOST_TYPE_NRF9160)

        Returns:
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - success (Optional[bool]): True if App Protect was enabled, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import HostType

            success, error = client.EnableAppProtect(target=HostType.HOST_TYPE_NRF9160)
            if error:
                print(f"Enable App Protect failed: {error}")
            ```
        """
        try:
            response = self.client.EnableAppProtect(EnableAppProtectRequest(target=target))
            if not response.success:
                return None, f"EnableAppProtect error: {response.message}"
            return response.success, None
        except grpc.RpcError as e:
            return None, f"gRPC error for EnableAppProtect at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in EnableAppProtect at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------
    #                                        Uart
    # ---------------------------------------------*/
    def UartStream(
        self, target: HostType, request_iterator: Iterator[UartStreamRequest]
    ) -> Iterator[UartStreamResponse]:
        """Stream UART data to/from a target device using a custom request iterator.

        This is a low-level method for bidirectional UART communication. For higher-level
        command methods, see the cmd_* methods in this class.

        Args:
            target: Target host type (e.g., HostType.HOST_TYPE_NRF9160, HostType.HOST_TYPE_NRF52840)
            request_iterator: Iterator that yields UartStreamRequest objects containing data to send

        Yields:
            Iterator[UartStreamResponse]: Iterator of UartStreamResponse objects containing:
                - success (bool): True if operation succeeded
                - message (str): Status or error message
                - data (bytes): Received UART data
                - target (HostType): Target device type

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import UartStreamRequest, HostType

            def request_gen():
                yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9160, data=b"AT\\r\\n")

            for response in client.UartStream(HostType.HOST_TYPE_NRF9160, request_gen()):
                if response.data:
                    print(f"Received: {response.data.decode()}")
                if not response.success:
                    break
            ```
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

    # -----------------------------------------------
    #                              Old Alpha Commands
    # ---------------------------------------------*/
    def alpha_cmd_personalize(
        self, device_id: str, target: HostType
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send a UART command to personalize the device using the given device_id.

        Opens a new UART stream, hits ENTER to get prompt, then sends the personalize command,
        and parses the response to extract the public key data.

        Args:
            device_id: Device ID to use for personalization
            target: Target host type (e.g., HostType.HOST_TYPE_NRF9160)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - hex_public_key (Optional[str]): Public key in hexadecimal format, None on error
                - base64_public_key (Optional[str]): Public key in base64 format, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import HostType

            hex_key, b64_key, error = client.alpha_cmd_personalize(
                device_id="device123",
                target=HostType.HOST_TYPE_NRF9160
            )
            if error:
                print(f"Personalize failed: {error}")
            ```
        """
        import queue
        import time

        from protocols.mtib.mtib_pb2 import UartStreamRequest

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
        """Send a UART command to get the device IMEI and ICCIDs.

        Opens a new UART stream, hits ENTER to get prompt, then sends the imei_ccid command,
        and parses the response to extract the IMEI and ICCIDs.

        Args:
            device_id: Device ID (unused, kept for compatibility)
            target: Target host type (e.g., HostType.HOST_TYPE_NRF9160)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - imei (Optional[str]): IMEI number, None on error
                - iccids (Optional[str]): Comma-separated ICCID numbers, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            from protocols.mtib.mtib_pb2 import HostType

            imei, iccids, error = client.alpha_cmd_get_imei_iccids(
                device_id="",
                target=HostType.HOST_TYPE_NRF9160
            )
            if error:
                print(f"Get IMEI/ICCIDs failed: {error}")
            ```
        """
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

    # -----------------------------------------------
    #                           Comms Coproc Commands
    # ---------------------------------------------*/
    def cmd_comms_coproc_lock_shell(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode for the communications co-processor device.

        Sends a UART command to lock the shell mode on the NRF9160 device.

        Returns:
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - success (Optional[bool]): True if shell was locked successfully, False on timeout, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            success, error = client.cmd_comms_coproc_lock_shell()
            if error:
                print(f"Lock shell failed: {error}")
            elif success:
                print("Shell locked successfully")
            ```
        """
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"lock_shell\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Locking shell mode ON" in full_response:
                        # Wait for the command to complete - look for the prompt after the lock_shell command
                        lines = full_response.split("\n")
                        lock_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "lock_shell" in line:
                                lock_command_found = True
                            elif lock_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def cmd_comms_coproc_debug_uart_disable(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART for the communications co-processor device.

        Sends a UART command to disable debug UART on the NRF9160 device.

        Returns:
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - success (Optional[bool]): True if debug UART was disabled, False on timeout, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            success, error = client.cmd_comms_coproc_debug_uart_disable()
            if error:
                print(f"Disable debug UART failed: {error}")
            ```
        """
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"debug_enable 0\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Debug is not enabled" in full_response:
                        # Wait for the command to complete - look for the prompt after the debug_enable command
                        lines = full_response.split("\n")
                        debug_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "debug_enable" in line:
                                debug_command_found = True
                            elif debug_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in debug_uart_disable: {str(e)}"

    def cmd_comms_coproc_get_chip_ids(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the communications co-processor device.

        Returns the LoRa hardware availability status and external flash chip ID from the NRF9160 device.

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - lora_available (Optional[str]): LoRa hardware availability status, None if not present
                - ext_flash_id (Optional[str]): External flash chip ID, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            lora_available, ext_flash_id, error = client.cmd_comms_coproc_get_chip_ids()
            if error:
                print(f"Get chip IDs failed: {error}")
            else:
                print(f"LoRa available: {lora_available}, Ext flash chip ID: {ext_flash_id}")
            ```
        """
        # target parameter is used
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_chip_ids\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    # Ext flash chip ID should always be present, LoRa hardware available is optional
                    full_response = "".join(response_lines)
                    if "Ext flash chip ID:" in full_response:
                        # Wait for the command to complete - look for the prompt after the get_chip_ids command
                        lines = full_response.split("\n")
                        chip_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "get_chip_ids" in line:
                                chip_command_found = True
                            elif chip_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response
                            lora_status = None
                            ext_flash_id = None

                            # Extract LoRa status (optional - may not be present depending on app configuration)
                            lora_start = full_response.find("LoRa hardware available:")
                            if lora_start != -1:
                                lora_line_start = full_response.rfind("\n", 0, lora_start) + 1
                                lora_line_end = full_response.find("\n", lora_start)
                                if lora_line_end == -1:
                                    lora_line_end = len(full_response)
                                lora_line = full_response[lora_line_start:lora_line_end].strip()
                                if ":" in lora_line:
                                    lora_status = lora_line.split(":", 1)[1].strip()

                            # Extract Ext flash chip ID (should always be present)
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

    def cmd_comms_coproc_get_modem_fw_version(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version from the communications co-processor device

        Args:
            None
        Returns:
            Tuple of (fw_version, error_string)
        """
        try:
            # Use queues for UART communication
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_modem_fw\r".encode("utf-8"))  # Send command

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

            # Collect response from UART stream
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Modem FW:" in full_response:
                        # Wait for the command to complete - look for the prompt after the get_modem_fw command
                        lines = full_response.split("\n")
                        modem_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "get_modem_fw" in line:
                                modem_command_found = True
                            elif modem_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response
                            fw_version = None

                            # Extract Modem FW version - use a more robust approach
                            modem_start = full_response.find("Modem FW:")
                            if modem_start != -1:
                                # Find the end of the line containing "Modem FW:"
                                line_end = full_response.find("\n", modem_start)
                                if line_end == -1:
                                    line_end = len(full_response)

                                # Extract the complete line
                                modem_line = full_response[modem_start:line_end].strip()

                                # Extract version after the colon
                                if ":" in modem_line:
                                    fw_version = modem_line.split(":", 1)[1].strip()

                            return fw_version, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in get_modem_fw_version: {str(e)}"

    def cmd_comms_coproc_get_imei_iccid(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Get IMEI and ICCID from the communications co-processor device

        Args:
            None
        Returns:
            Tuple of (imei, iccid_list, error_string)
        """
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"imei_iccid\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "IMEI,ICCID0" in full_response:
                        # Wait for the command to complete - look for the prompt after the imei_iccid command
                        lines = full_response.split("\n")
                        imei_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "imei_iccid" in line:
                                imei_command_found = True
                            elif imei_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response
                            imei = None
                            iccid_list = []

                            # Extract IMEI and ICCID data
                            imei_start = full_response.find("IMEI,ICCID0")
                            if imei_start != -1:
                                imei_line_start = full_response.rfind("\n", 0, imei_start) + 1
                                imei_line_end = full_response.find("\n", imei_start)
                                if imei_line_end == -1:
                                    imei_line_end = len(full_response)
                                imei_line = full_response[imei_line_start:imei_line_end].strip()

                                # Parse format: "IMEI,ICCID0[,ICCID1]: 358447171854988,89148000009808536124,89457300000035352429"
                                if ":" in imei_line:
                                    data_part = imei_line.split(":", 1)[1].strip()
                                    # Split by comma to get IMEI and ICCIDs
                                    parts = [part.strip() for part in data_part.split(",")]
                                    if len(parts) >= 2:
                                        imei = parts[0]  # First part is IMEI
                                        iccid_list = parts[1:]  # Rest are ICCIDs

                            return imei, iccid_list, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception in get_imei_iccid: {str(e)}"

    def cmd_comms_coproc_personalize(
        self, device_id: str, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Personalize the communications co-processor device

        Args:
            device_id: The device ID to personalize
        Returns:
            Tuple of (hex_public_key, base64_public_key, error_string)
        """
        try:
            # Use queues for UART communication
            input_queue = queue.Queue()

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

            # Collect response from UART stream
            response_lines = []
            start_time = time.time()
            timeout = 10  # 10 second timeout

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Public key (hex)" in full_response and "Public key (base64)" in full_response:
                        # Wait for the command to complete - look for the prompt after the personalize command
                        lines = full_response.split("\n")
                        command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "personalize" in line:
                                command_found = True
                            elif command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response to extract both hex and base64 keys
                            hex_key = None
                            base64_key = None

                            # Extract hex key
                            hex_start = full_response.find("Public key (hex)")
                            if hex_start != -1:
                                hex_line_end = full_response.find("\n", hex_start)
                                if hex_line_end == -1:
                                    hex_line_end = len(full_response)
                                hex_line = full_response[hex_start:hex_line_end].strip()
                                if ":" in hex_line:
                                    hex_key = hex_line.split(":", 1)[1].strip()

                            # Extract base64 key
                            base64_start = full_response.find("Public key (base64)")
                            if base64_start != -1:
                                base64_line_end = full_response.find("\n", base64_start)
                                if base64_line_end == -1:
                                    base64_line_end = len(full_response)
                                base64_line = full_response[base64_start:base64_line_end].strip()
                                if ":" in base64_line:
                                    base64_key = base64_line.split(":", 1)[1].strip()

                            return hex_key, base64_key, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception in personalize: {str(e)}"

    def cmd_comms_coproc_read_ext_flash(
        self, address: str, num_bytes: int, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash

        Args:
            address: The address to read from
            num_bytes: The number of bytes to read
        Returns:
            Tuple of (hex_data, error_string)
        """
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"read_ext_flash {address} {num_bytes}\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Reading" in full_response and "bytes from address:" in full_response:
                        # Wait for the command to complete - look for the prompt after the read command
                        # Find where the read command output ends and look for prompt after that
                        lines = full_response.split("\n")
                        read_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "read_ext_flash" in line:
                                read_command_found = True
                            elif read_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Extract the hex data from the response
                            hex_data = ""
                            lines = full_response.split("\n")
                            for line in lines:
                                if ":" in line and "|" in line:
                                    # This is a hex dump line, extract the hex part
                                    hex_part = line.split("|")[0].strip()
                                    # Remove the address prefix (e.g., "00000000: ")
                                    if ":" in hex_part:
                                        hex_values = hex_part.split(":", 1)[1].strip()
                                        hex_data += hex_values.replace(" ", "")

                            return hex_data, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in read_ext_flash: {str(e)}"

    def cmd_comms_coproc_erase_ext_flash(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Erase entire external flash

        Args:
            None
        Returns:
            Tuple of (success, error_string)
        """
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"erase_ext_flash\r".encode("utf-8"))  # Send command

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
            timeout = 30  # 30 second timeout (erase can take longer)

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Erasing flash" in full_response and "pages" in full_response:
                        # Wait for the command to complete - look for the prompt after the erase command
                        # Find where the erase command output ends and look for prompt after that
                        lines = full_response.split("\n")
                        erase_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "erase_ext_flash" in line:
                                erase_command_found = True
                            elif erase_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in erase_ext_flash: {str(e)}"

    def cmd_comms_coproc_write_ext_flash(
        self, address: str, data: str, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to external flash (data should be base64 encoded)

        Args:
            address: The address to write to
            data: The data to write (base64 encoded)
        Returns:
            Tuple of (success, error_string)
        """
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"write_ext_flash {address} {data}\r".encode("utf-8"))  # Send command

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

            # target parameter is used
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Writing" in full_response and "bytes to address:" in full_response:
                        # Wait for the command to complete - look for the prompt after the write command
                        # Find where the write command output ends and look for prompt after that
                        lines = full_response.split("\n")
                        write_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "write_ext_flash" in line:
                                write_command_found = True
                            elif write_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in write_ext_flash: {str(e)}"

    def cmd_comms_coproc_rekey_ipc(
        self, target: HostType = HostType.HOST_TYPE_NRF9160
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Rekey IPC

        Args:
            None
        Returns:
            Tuple of (success, error_string)
        """
        try:
            # Use queues like the working terminal
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"rekey_ipc\r".encode("utf-8"))  # Send command

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

            # target parameter is used

            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "IPC rekey completed successfully" in full_response:
                        return True, None
                    elif "IPC rekey failed" in full_response:
                        return False, "IPC rekey failed"

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success or failure message
            full_response = "".join(response_lines)
            return None, f"Timeout or no response found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in rekey_ipc: {str(e)}"  # type: ignore

    # -----------------------------------------------
    #                                 Sigma5 Commands
    # ---------------------------------------------*/
    def cmd_sigma5_app_lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode for the app processor device

        Args:
            None
        Returns:
            Tuple of (success, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

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
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Locking shell mode ON" in full_response:
                        # Wait for the command to complete - look for the prompt after the lock_shell command
                        lines = full_response.split("\n")
                        lock_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "lock_shell" in line:
                                lock_command_found = True
                            elif lock_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in lock_shell: {str(e)}"

    def cmd_sigma5_app_debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART for the app processor device

        Args:
            None
        Returns:
            Tuple of (success, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

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
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Debug is not enabled" in full_response:
                        # Wait for the command to complete - look for the prompt after the debug_enable command
                        lines = full_response.split("\n")
                        debug_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "debug_enable" in line:
                                debug_command_found = True
                            elif debug_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            return True, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return False, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception in debug_uart_disable: {str(e)}"

    def cmd_sigma5_app_get_chip_ids(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the app processor device

        Args:
            None
        Returns:
            Tuple of (accel_id, altimeter_id, ext_flash_id, gps_hw_version, ble_mac, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

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
            for resp in self.UartStream(target, request_iterator()):
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
                        # Wait for the command to complete - look for the prompt after the get_chip_ids command
                        lines = full_response.split("\n")
                        chip_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "get_chip_ids" in line:
                                chip_command_found = True
                            elif chip_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
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

    def cmd_sigma5_app_get_ublox_version_info(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get ublox version info from the app processor device

        Args:
            None
        Returns:
            Tuple of (hw_version, fw_version, sw_version, proto_version, constellations, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"get_ublox\r".encode("utf-8"))  # Send command

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
            for resp in self.UartStream(target, request_iterator()):
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
                        # Wait for the command to complete - look for the prompt after the get_ublox command
                        lines = full_response.split("\n")
                        ublox_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "get_ublox" in line:
                                ublox_command_found = True
                            elif ublox_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
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

    def cmd_sigma5_app_read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Get accelerometer values from the app processor device

        Args:
            None
        Returns:
            Tuple of (x_raw, y_raw, z_raw, temp, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"read_accel\r".encode("utf-8"))  # Send command

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
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, None, None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Accelerometer values:" in full_response:
                        # Wait for the command to complete - look for the prompt after the read_accel command
                        lines = full_response.split("\n")
                        accel_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "read_accel" in line:
                                accel_command_found = True
                            elif accel_command_found and (
                                "Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()
                            ):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response
                            x_value = None
                            y_value = None
                            z_value = None
                            temp_value = None

                            # Extract accelerometer values
                            accel_start = full_response.find("Accelerometer values:")
                            if accel_start != -1:
                                accel_line_start = full_response.rfind("\n", 0, accel_start) + 1
                                accel_line_end = full_response.find("\n", accel_start)
                                if accel_line_end == -1:
                                    accel_line_end = len(full_response)
                                accel_line = full_response[accel_line_start:accel_line_end].strip()

                                # Parse the format: "Accelerometer values: (x, y, z, temp): 0.890625, -0.015625, 0.437500, 31.000000"
                                if ":" in accel_line:
                                    values_part = accel_line.split(":", 1)[1].strip()
                                    # Remove the "(x, y, z, temp):" part and get just the values
                                    if ":" in values_part:
                                        values_str = values_part.split(":", 1)[1].strip()
                                        try:
                                            # Split by comma and convert to float
                                            values = [float(v.strip()) for v in values_str.split(",")]
                                            if len(values) >= 4:
                                                x_value = values[0]
                                                y_value = values[1]
                                                z_value = values[2]
                                                temp_value = values[3]
                                        except ValueError:
                                            pass

                            return x_value, y_value, z_value, temp_value, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, None, None, None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, None, None, f"Exception in read_accel: {str(e)}"

    def cmd_sigma5_app_read_altimeter(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Get altimeter values from the app processor device

        Args:
            None
        Returns:
            Tuple of (pressure_hg, temperature_c, error_string)
        """
        target = HostType.HOST_TYPE_NRF52840
        try:
            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.2)
            input_queue.put(f"read_alt\r".encode("utf-8"))  # Send command

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
            timeout = 5  # 5 second timeout (reduced from 10)

            target = HostType.HOST_TYPE_NRF52840
            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    # Check if we got the complete response
                    full_response = "".join(response_lines)
                    if "Altimeter values" in full_response:
                        # Wait for the command to complete - look for the prompt after the read_alt command
                        lines = full_response.split("\n")
                        alt_command_found = False
                        prompt_found = False

                        for i, line in enumerate(lines):
                            if "read_alt" in line:
                                alt_command_found = True
                            elif alt_command_found and ("Mfg shell:" in line.strip() or "Comms Mfg:" in line.strip()):
                                prompt_found = True
                                break

                        if prompt_found:
                            # Parse the response
                            pressure_value = None
                            temp_value = None

                            # Extract altimeter values
                            alt_start = full_response.find("Altimeter values")
                            if alt_start != -1:
                                alt_line_start = full_response.rfind("\n", 0, alt_start) + 1
                                alt_line_end = full_response.find("\n", alt_start)
                                if alt_line_end == -1:
                                    alt_line_end = len(full_response)
                                alt_line = full_response[alt_line_start:alt_line_end].strip()

                                # Parse the format: "Altimeter values (pressure, temp): 28.722524, 25.412672"
                                if ":" in alt_line:
                                    values_part = alt_line.split(":", 1)[1].strip()
                                    try:
                                        # Split by comma and convert to float
                                        values = [float(v.strip()) for v in values_part.split(",")]
                                        if len(values) >= 2:
                                            pressure_value = values[0]
                                            temp_value = values[1]
                                    except ValueError:
                                        pass

                            return pressure_value, temp_value, None

                # Timeout check
                if time.time() - start_time > timeout:
                    break

            # If we get here, we didn't find the success message
            full_response = "".join(response_lines)
            return None, None, f"Timeout or no success message found. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception in read_altimeter: {str(e)}"

    # ===============================================
    #         THETA APP PROCESSOR COMMANDS
    # ===============================================
    #
    # Commands specific to Theta manufacturing firmware
    # App Processor: nRF52840 (HOST_TYPE_NRF52840) with "Mfg shell: " prompt
    #
    # ===============================================

    def cmd_theta_app_lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell on theta app processor

        Retries sending the lock_shell command periodically until success or timeout.

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            last_send_time = 0
            retry_interval = 2.0  # Retry every 2 seconds

            def request_iterator():
                nonlocal last_send_time
                while True:
                    current_time = time.time()
                    # Send command initially and retry every retry_interval seconds
                    if current_time - last_send_time >= retry_interval:
                        input_queue.put(b"\r")
                        input_queue.put(b"lock_shell\r")
                        last_send_time = current_time

                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=HostType.HOST_TYPE_NRF52840, data=b"")
                        time.sleep(0.1)

            response_lines = []
            start_time = time.time()
            timeout = 30

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Shell locked" in full_response or "Locking shell mode" in full_response:
                        if (
                            "Mfg shell:"
                            in full_response.split(
                                "Shell locked" if "Shell locked" in full_response else "Locking shell mode"
                            )[-1]
                        ):
                            return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def cmd_theta_app_debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART on theta app processor

        Returns:
            Tuple of (success, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"debug_enable 0\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "Debug disabled" in full_response
                        or "Debug output disabled" in full_response
                        or "Debug is not enabled" in full_response
                    ) and "Mfg shell:" in full_response:
                        return True, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def cmd_theta_app_get_chip_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from theta app processor.

        Supports two firmware response formats:
        - Legacy (Theta): Returns accelerometer and altimeter chip IDs
        - Alpha: Returns external flash chip ID and BLE MAC address

        Returns:
            Tuple of (id_1, id_2, error_string) where:
                - Legacy: (accel_id, alt_id, error)
                - Alpha: (ext_flash_id, ble_mac, error)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"get_chip_ids\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

                    if not prompt_found:
                        if time.time() - start_time > timeout:
                            break
                        continue

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

                    # Prompt found but no recognized chip ID fields
                    return None, None, f"Unrecognized response format: {full_response[:200]}..."

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception: {str(e)}"

    def cmd_theta_app_read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read accelerometer from theta app processor

        Returns:
            Tuple of (x_g, y_g, z_g, temp_c, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"read_accel\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, None, None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "Accelerometer values" in full_response
                        and "Mfg shell:" in full_response.split("Accelerometer values")[-1]
                    ):
                        # Parse format: "Accelerometer values: (x, y, z, temp): 0.890625, -0.015625, 0.437500, 31.000000"
                        for line in full_response.split("\n"):
                            if "Accelerometer values" in line and ":" in line:
                                try:
                                    values_part = line.split(":", 2)[-1].strip()
                                    values = [float(v.strip()) for v in values_part.split(",")]
                                    if len(values) >= 4:
                                        return values[0], values[1], values[2], values[3], None
                                except (ValueError, IndexError):
                                    pass

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, None, None, None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, None, None, f"Exception: {str(e)}"

    def cmd_theta_app_read_alt(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Read altimeter from theta app processor

        Returns:
            Tuple of (pressure_hg, temperature_c, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"read_alt\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "Altimeter values" in full_response
                        and "Mfg shell:" in full_response.split("Altimeter values")[-1]
                    ):
                        # Parse format: "Altimeter values (pressure, temp): 28.722524, 25.412672"
                        for line in full_response.split("\n"):
                            if "Altimeter values" in line and ":" in line:
                                try:
                                    values_part = line.split(":", 1)[-1].strip()
                                    values = [float(v.strip()) for v in values_part.split(",")]
                                    if len(values) >= 2:
                                        return values[0], values[1], None
                                except (ValueError, IndexError):
                                    pass

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, f"Exception: {str(e)}"

    def cmd_theta_app_drone_test(
        self, timeout_ms: int = 10000
    ) -> Tuple[Optional[bool], Optional[int], Optional[int], Optional[str]]:
        """Run drone detection test on theta app processor

        Args:
            timeout_ms: Test timeout in milliseconds

        Returns:
            Tuple of (success, detected_freq_hz, amplitude_mg, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(f"drone_test {timeout_ms}\r".encode("utf-8"))

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
            timeout = (timeout_ms / 1000) + 5

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, None, None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if (
                        "Drone test" in full_response or "Drone detection" in full_response
                    ) and "Mfg shell:" in full_response:
                        success = "PASS" in full_response or "detected" in full_response.lower()
                        detected_freq = None
                        amplitude = None

                        for line in full_response.split("\n"):
                            if "Frequency" in line or "frequency" in line:
                                try:
                                    freq_match = re.search(r"(\d+\.?\d*)\s*Hz", line)
                                    if freq_match:
                                        detected_freq = int(float(freq_match.group(1)))
                                except (ValueError, AttributeError):
                                    pass
                            if "Amplitude" in line or "amplitude" in line:
                                try:
                                    amp_match = re.search(r"(\d+\.?\d*)\s*mg", line)
                                    if amp_match:
                                        amplitude = int(float(amp_match.group(1)))
                                except (ValueError, AttributeError):
                                    pass

                        return success, detected_freq, amplitude, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, None, None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, None, None, f"Exception: {str(e)}"

    def cmd_theta_app_meas_bat_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Measure battery voltage on theta app processor

        Returns:
            Tuple of (voltage_v, error_string)
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"meas_bat_voltage\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Battery voltage" in full_response or "Voltage" in full_response:
                        if "Mfg shell:" in full_response:
                            for line in full_response.split("\n"):
                                if ("Battery voltage" in line or "Voltage" in line) and ":" in line:
                                    try:
                                        voltage_str = line.split(":", 1)[1].strip().rstrip("V").strip()
                                        return float(voltage_str), None
                                    except (ValueError, IndexError):
                                        pass

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def cmd_theta_app_membrane_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Run complete membrane board test on theta app processor

        Returns:
            Tuple of (results_dict, error_string)
            results_dict contains test results for: bme280, gpio_expander, leds, vibration
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"membrane_test\r")

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
            timeout = 15

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Membrane test" in full_response and "Mfg shell:" in full_response.split("Membrane test")[-1]:
                        results = {}
                        for line in full_response.split("\n"):
                            line_lower = line.lower()
                            if "bme280" in line_lower:
                                results["bme280"] = "pass" in line_lower or "ok" in line_lower
                            if "gpio" in line_lower or "pca9536" in line_lower:
                                results["gpio_expander"] = "pass" in line_lower or "ok" in line_lower
                            if "led" in line_lower:
                                results["leds"] = "pass" in line_lower or "ok" in line_lower
                            if "vibration" in line_lower or "motor" in line_lower:
                                results["vibration"] = "pass" in line_lower or "ok" in line_lower
                        return results, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def cmd_theta_app_env_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read BME280 environmental sensors on theta app processor

        Returns:
            Tuple of (readings_dict, error_string)
            readings_dict contains: temperature_c, humidity_pct, pressure_pa
        """
        try:
            input_queue = queue.Queue()
            input_queue.put(b"\r")
            time.sleep(0.2)
            input_queue.put(b"env_test\r")

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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    if "Temperature" in full_response and "Humidity" in full_response and "Pressure" in full_response:
                        if "Mfg shell:" in full_response:
                            readings = {}

                            for line in full_response.split("\n"):
                                if "Temperature" in line and ":" in line:
                                    try:
                                        temp_str = line.split(":", 1)[1].strip()
                                        temp_str = re.sub(r"[^0-9.-]", "", temp_str)
                                        readings["temperature_c"] = float(temp_str)
                                    except (ValueError, IndexError):
                                        pass
                                if "Humidity" in line and ":" in line:
                                    try:
                                        humidity_str = line.split(":", 1)[1].strip()
                                        humidity_str = re.sub(r"[^0-9.-]", "", humidity_str)
                                        readings["humidity_pct"] = float(humidity_str)
                                    except (ValueError, IndexError):
                                        pass
                                if "Pressure" in line and ":" in line:
                                    try:
                                        pressure_str = line.split(":", 1)[1].strip()
                                        pressure_str = re.sub(r"[^0-9.-]", "", pressure_str)
                                        readings["pressure_pa"] = float(pressure_str)
                                    except (ValueError, IndexError):
                                        pass

                            return readings, None

                if time.time() - start_time > timeout:
                    break

            full_response = "".join(response_lines)
            return None, f"Timeout. Response: {full_response[:200]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def cmd_theta_app_vib_test(self, duration_ms: int = 200) -> Tuple[Optional[bool], Optional[str]]:
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

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_gps_status(self) -> Tuple[Optional[dict], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_gps_start(self) -> Tuple[Optional[bool], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_gps_stop(self) -> Tuple[Optional[bool], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_get_ublox(self) -> Tuple[Optional[dict], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_set_gps_power(self, enable: bool) -> Tuple[Optional[bool], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_test_ble(self) -> Tuple[Optional[bool], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_test_bms(self) -> Tuple[Optional[dict], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_test_charger(self) -> Tuple[Optional[dict], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_test_gps(self) -> Tuple[Optional[dict], Optional[str]]:
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_read_ext_flash(
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_write_ext_flash(
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
            timeout = 10

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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

    def cmd_theta_app_erase_ext_flash(self) -> Tuple[Optional[bool], Optional[str]]:
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

            for resp in self.UartStream(HostType.HOST_TYPE_NRF52840, request_iterator()):
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
