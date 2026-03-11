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

# Import actual protobuf types for streaming RPCs
from protocols.mtib.mtib_pb2 import (
    MotionStartRequest,
    MotionStartResponse,
    UartStreamRequest,
    UartStreamResponse,
    # V2 streaming types
    PowerStreamResponse,
    GpioWatchEvent,
    AdcStreamResponse,
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

    def _validate_gpio(self, gpio: int) -> Optional[str]:
        """Validate GPIO pin number is within valid range.

        Args:
            gpio: GPIO pin number to validate.

        Returns:
            None if valid, error message string if invalid.
        """
        if not 0 <= gpio <= 7:
            return f"GPIO pin {gpio} out of valid range (0-7)"
        return None

    def _validate_adc_channel(self, channel: int) -> Optional[str]:
        """Validate ADC channel number is within valid range.

        Args:
            channel: ADC channel number to validate.

        Returns:
            None if valid, error message string if invalid.
        """
        if not 0 <= channel <= 7:
            return f"ADC channel {channel} out of valid range (0-7)"
        return None

    def _validate_power_channel(self, channel: int) -> Optional[str]:
        """Validate power channel number is within valid range.

        Args:
            channel: Power channel number to validate (0=DUT, 1=CHARGER).

        Returns:
            None if valid, error message string if invalid.
        """
        if not 0 <= channel <= 1:
            return f"Power channel {channel} out of valid range (0-1)"
        return None

    def _validate_voltage(self, voltage_v: float) -> Optional[str]:
        """Validate voltage is within safe operating range.

        Args:
            voltage_v: Voltage in volts to validate.

        Returns:
            None if valid, error message string if invalid.
        """
        if not 0.0 <= voltage_v <= 6.0:
            return f"Voltage {voltage_v}V out of safe range (0.0-6.0V)"
        return None

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
        # Validate GPIO pin number
        if err := self._validate_gpio(gpio):
            return err
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
        # Validate GPIO pin number
        if err := self._validate_gpio(gpio):
            return err
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
        # Validate GPIO pin number
        if err := self._validate_gpio(gpio):
            return None, err
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
        # Validate ADC channel number
        if err := self._validate_adc_channel(channel):
            return None, err
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
    def PowerEnable(self, channel: "int | PowerChannel" = 0, voltage_v: float = 0.0) -> Optional[str]:
        """Enable power on a channel.

        Args:
            channel: Power channel (0=DUT, 1=CHARGER). Use PowerChannel enum.
            voltage_v: Voltage to set (only meaningful for DUT channel).

        Returns:
            Optional[str]: None on success, error message string on failure
        """
        # Validate power channel
        channel_int = int(channel)
        if err := self._validate_power_channel(channel_int):
            return err
        # Validate voltage
        if err := self._validate_voltage(voltage_v):
            return err
        try:
            response = self.client.PowerEnable(
                PowerEnableRequest(channel=channel, voltage_v=voltage_v),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
            if not response.success:
                return f"PowerEnable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for PowerEnable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in PowerEnable at {self.config.net.addr}: {str(e)}"

    def PowerDisable(self, channel: "int | PowerChannel" = 0) -> Optional[str]:
        """Disable power on a channel.

        Args:
            channel: Power channel (0=DUT, 1=CHARGER). Use PowerChannel enum.

        Returns:
            Optional[str]: None on success, error message string on failure
        """
        # Validate power channel
        channel_int = int(channel)
        if err := self._validate_power_channel(channel_int):
            return err
        try:
            response = self.client.PowerDisable(
                PowerDisableRequest(channel=channel),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
            if not response.success:
                return f"PowerDisable error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for PowerDisable at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in PowerDisable at {self.config.net.addr}: {str(e)}"

    def PowerRead(self, channel: "int | PowerChannel" = 0) -> Tuple[Optional[PowerReadResult], Optional[str]]:
        """Read power status for a channel.

        Args:
            channel: Power channel (0=DUT, 1=CHARGER). Use PowerChannel enum.

        Returns:
            Tuple of (PowerReadResult, error). Result is None on error.
        """
        # Validate power channel
        channel_int = int(channel)
        if err := self._validate_power_channel(channel_int):
            return None, err
        try:
            response = self.client.PowerRead(
                PowerReadRequest(channel=channel),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
            if not response.success:
                return None, f"PowerRead error: {response.message}"
            return PowerReadResult(
                enabled=response.enabled,
                voltage_v=response.voltage_v,
                current_ma=response.current_ma,
                power_mw=response.power_mw,
            ), None
        except grpc.RpcError as e:
            return None, f"gRPC error for PowerRead at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in PowerRead at {self.config.net.addr}: {str(e)}"

    def PowerMeasure(self, channel: "int | PowerChannel" = 0, duration_s: float = 1.0) -> Tuple[Optional[PowerMeasureResult], Optional[str]]:
        """Measure power over a duration and compute statistics.

        Args:
            channel: Power channel (0=DUT, 1=CHARGER). Use PowerChannel enum.
            duration_s: Measurement duration in seconds.

        Returns:
            Tuple of (PowerMeasureResult, error). Result is None on error.
        """
        try:
            response = self.client.PowerMeasure(
                PowerMeasureRequest(channel=channel, duration_s=duration_s),
                timeout=max(DEFAULT_GRPC_TIMEOUT_SECONDS, duration_s + 5),
            )
            if not response.success:
                return None, f"PowerMeasure error: {response.message}"
            return PowerMeasureResult(
                duration_s=response.duration_s,
                average_ma=response.average_ma,
                min_ma=response.min_ma,
                max_ma=response.max_ma,
                average_mv=response.average_mv,
                sample_count=response.sample_count,
            ), None
        except grpc.RpcError as e:
            return None, f"gRPC error for PowerMeasure at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in PowerMeasure at {self.config.net.addr}: {str(e)}"

    def PowerStream(self, channel: "int | PowerChannel" = 0) -> Iterator[PowerStreamResponse]:
        """Stream power samples until cancelled.

        Args:
            channel: Power channel (0=DUT, 1=CHARGER). Use PowerChannel enum.

        Yields:
            PowerStreamResponse containing samples with timestamp_ms, voltage_mv, current_ma.
        """
        try:
            response_iterator = self.client.PowerStream(PowerStreamRequest(channel=channel))
            for response in response_iterator:
                yield response
        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for PowerStream at {self.config.net.addr}. Error: {str(e.details())}")
        except Exception as e:
            self.logger.error(f"Unexpected error in PowerStream at {self.config.net.addr}: {str(e)}")

    # -----------------------------------------------
    #                            V2 GPIO Watch
    # ---------------------------------------------*/
    def GpioWatch(self, gpio: int, edge: int = 2) -> Iterator[GpioWatchEvent]:
        """Stream GPIO edge events until cancelled.

        Args:
            gpio: GPIO pin number to watch.
            edge: Edge type (0=RISING, 1=FALLING, 2=BOTH). Use GpioEdge enum.

        Yields:
            GpioWatchEvent containing gpio, state, timestamp_ms.
        """
        try:
            response_iterator = self.client.GpioWatch(GpioWatchRequest(gpio=gpio, edge=edge))
            for event in response_iterator:
                yield event
        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for GpioWatch at {self.config.net.addr}. Error: {str(e.details())}")
        except Exception as e:
            self.logger.error(f"Unexpected error in GpioWatch at {self.config.net.addr}: {str(e)}")

    # -----------------------------------------------
    #                            V2 ADC Stream
    # ---------------------------------------------*/
    def AdcStream(self, channels: List[int] = None, interval_ms: int = 100) -> Iterator[AdcStreamResponse]:
        """Stream ADC samples at specified interval until cancelled.

        Args:
            channels: List of channel numbers to read. None = all 8.
            interval_ms: Sample interval in milliseconds. Default 100 (10 Hz).

        Yields:
            AdcStreamResponse containing samples with timestamp_ms, channel, voltage_v.
        """
        try:
            request = AdcStreamRequest(
                channels=channels if channels else [],
                interval_ms=interval_ms,
            )
            response_iterator = self.client.AdcStream(request)
            for response in response_iterator:
                yield response
        except grpc.RpcError as e:
            self.logger.error(f"gRPC error for AdcStream at {self.config.net.addr}. Error: {str(e.details())}")
        except Exception as e:
            self.logger.error(f"Unexpected error in AdcStream at {self.config.net.addr}: {str(e)}")

    # -----------------------------------------------
    #                        V2 Observability
    # ---------------------------------------------*/
    def HealthCheckExtended(
        self, timeout: int = DEFAULT_GRPC_TIMEOUT_SECONDS
    ) -> Tuple[Optional[HealthCheckExtendedResponse], Optional[str]]:
        """Extended health check returning hw_revision and capabilities.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Tuple of (HealthCheckExtendedResponse, error). Result is None on error.
        """
        try:
            response = self.client.HealthCheck(Empty(), timeout=timeout)
            return HealthCheckExtendedResponse(
                ready=response.ready,
                errors=list(response.errors),
                hw_revision=response.hw_revision,
                capabilities=list(response.capabilities),
            ), None
        except grpc.RpcError as e:
            return None, f"gRPC error for HealthCheckExtended at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in HealthCheckExtended at {self.config.net.addr}: {str(e)}"

    def GetSnapshot(self) -> Tuple[Optional[SnapshotResult], Optional[str]]:
        """Get a one-shot system state snapshot.

        Returns:
            Tuple of (SnapshotResult, error). Result is None on error.
        """
        try:
            response = self.client.GetSnapshot(Empty(), timeout=DEFAULT_GRPC_TIMEOUT_SECONDS)
            if not response.success:
                return None, f"GetSnapshot error: {response.message}"
            return SnapshotResult(
                timestamp_ms=response.timestamp_ms,
                hw_revision=response.hw_revision,
                power=list(response.power),
                gpio=list(response.gpio),
                adc=list(response.adc),
            ), None
        except grpc.RpcError as e:
            return None, f"gRPC error for GetSnapshot at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in GetSnapshot at {self.config.net.addr}: {str(e)}"

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
    #                                           NFC
    # ---------------------------------------------*/
    def NfcPoll(self, timeout_ms: int = 1000) -> Tuple[Optional[bool], Optional[bytes], Optional[str]]:
        """Poll for an NFC tag on the reader.

        Args:
            timeout_ms: How long to poll for a tag (default: 1000ms).

        Returns:
            Tuple of (tag_present, uid_bytes, error).
        """
        try:
            from protocols.mtib.mtib_pb2 import NfcPollRequest
            response = self.client.NfcPoll(
                NfcPollRequest(timeout_ms=timeout_ms),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
            if not response.success:
                return None, None, f"NfcPoll error: {response.message}"
            return response.tag_present, bytes(response.uid) if response.uid else b"", None
        except grpc.RpcError as e:
            return None, None, f"gRPC error for NfcPoll at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, None, f"Unexpected error in NfcPoll at {self.config.net.addr}: {str(e)}"

    def NfcReadNdef(self, timeout_ms: int = 1000) -> Tuple[Optional[list], Optional[str]]:
        """Read NDEF records from an NFC tag.

        Args:
            timeout_ms: How long to wait for a tag (default: 1000ms).

        Returns:
            Tuple of (records, error). records is a list of NdefRecord proto objects.
        """
        try:
            from protocols.mtib.mtib_pb2 import NfcReadNdefRequest
            response = self.client.NfcReadNdef(
                NfcReadNdefRequest(timeout_ms=timeout_ms),
                timeout=DEFAULT_GRPC_TIMEOUT_SECONDS,
            )
            if not response.success:
                return None, f"NfcReadNdef error: {response.message}"
            return list(response.records), None
        except grpc.RpcError as e:
            return None, f"gRPC error for NfcReadNdef at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in NfcReadNdef at {self.config.net.addr}: {str(e)}"

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
        self, device_id: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send a UART command to personalize the device using the given device_id.

        Uses the standard UART helper to send the personalize command and parse
        the response to extract the public key data.

        Args:
            device_id: Device ID to use for personalization
            target: Target host type (default: NRF9151 comms processor)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - hex_public_key (Optional[str]): Public key in hexadecimal format, None on error
                - base64_public_key (Optional[str]): Public key in base64 format, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            hex_key, b64_key, error = client.alpha_cmd_personalize(device_id="device123")
            if error:
                print(f"Personalize failed: {error}")
            ```
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"personalize {device_id}",
            success_patterns=["Public key (base64)"],
            timeout_s=60,  # Key generation takes ~5s, plus byte-by-byte UART delivery is SLOW
        )
        if err:
            return None, None, err

        # Strip ANSI escape codes before parsing
        full_response = re.sub(r"\x1b\[[0-9;]*m", "", response or "")

        hex_match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]{100,})", full_response)
        b64_match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]{40,})", full_response)

        if hex_match and b64_match:
            return hex_match.group(1), b64_match.group(1), None
        else:
            return None, None, f"Failed to parse public keys from response: {full_response[:300]}"

    def alpha_cmd_get_imei_iccids(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send a UART command to get the device IMEI and ICCIDs.

        Uses the standard UART helper to send the imei_iccid command and parse
        the response to extract the IMEI and ICCIDs.

        Args:
            target: Target host type (default: NRF9151 comms processor)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - imei (Optional[str]): IMEI number, None on error
                - iccids (Optional[str]): Comma-separated ICCID numbers, None on error
                - error (Optional[str]): Error message string if operation failed, None on success

        Example:
            ```python
            imei, iccids, error = client.alpha_cmd_get_imei_iccids()
            if error:
                print(f"Get IMEI/ICCIDs failed: {error}")
            ```
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="imei_iccid",
            success_patterns=["IMEI"],
            timeout_s=30,
        )
        if err:
            return None, None, err

        # Parse the response for IMEI and ICCIDs
        imei = None
        iccids = None
        full_response = response or ""

        # Look for IMEI,ICCID line (handle both direct response and modem log response)
        imei_start = full_response.find("IMEI,ICCID")
        if imei_start != -1:
            colon_pos = full_response.find(":", imei_start)
            if colon_pos != -1:
                data_start = colon_pos + 1
                data_end = full_response.find("\n", data_start)
                if data_end == -1:
                    data_end = len(full_response)
                data_line = full_response[data_start:data_end].strip()
                if data_line and "," in data_line:
                    parts = data_line.split(",")
                    if len(parts) >= 2:
                        imei = parts[0].strip()
                        iccids = ",".join(parts[1:]).strip()
                    else:
                        imei = "unknown"
                        iccids = parts[0].strip()

        if imei and iccids:
            return imei, iccids, None
        else:
            return None, None, f"Failed to parse IMEI/ICCIDs from response: {full_response[:300]}"

    # -----------------------------------------------
    #                           Comms Coproc Commands
    # ---------------------------------------------*/
    def cmd_comms_coproc_lock_shell(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode for the communications co-processor device.

        Sends a UART command to lock the shell mode. Uses the standard UART helper.

        Returns:
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - success (Optional[bool]): True if shell was locked successfully, False on timeout, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="lock_shell",
            success_patterns=["Locking shell mode ON"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Locking shell mode ON" in (response or ""), None

    def cmd_comms_coproc_debug_uart_disable(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART for the communications co-processor device.

        Sends a UART command to disable debug UART. Uses the standard UART helper.

        Returns:
            Tuple[Optional[bool], Optional[str]]: A tuple containing:
                - success (Optional[bool]): True if debug UART was disabled, False on timeout, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="debug_enable 0",
            success_patterns=["Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Debug is not enabled" in (response or ""), None

    def cmd_comms_coproc_get_chip_ids(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the communications co-processor device.

        Returns the LoRa hardware availability status and external flash chip ID.

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - lora_available (Optional[str]): LoRa hardware availability status, None if not present
                - ext_flash_id (Optional[str]): External flash chip ID, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_chip_ids",
            success_patterns=["Ext flash chip ID:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        lora_status = None
        ext_flash_id = None
        full_response = response or ""

        # Extract LoRa status (optional)
        match = re.search(r"LoRa hardware available:\s*(\w+)", full_response)
        if match:
            lora_status = match.group(1).strip()

        # Extract Ext flash chip ID
        match = re.search(r"Ext flash chip ID:\s*(.+)", full_response)
        if match:
            ext_flash_id = match.group(1).strip()

        if ext_flash_id:
            return lora_status, ext_flash_id, None
        return None, None, f"Failed to parse chip IDs from: {full_response[:200]}"

    # -----------------------------------------------
    #                    Alpha App Processor Commands
    # -----------------------------------------------
    def _alpha_send_uart_cmd(
        self,
        target: HostType,
        command: str,
        success_patterns: Optional[List[str]] = None,
        timeout_s: float = 60,
        drain_first: bool = True,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Helper to send UART command and collect response.

        Args:
            target: HostType for UART target processor.
            command: Shell command string to send.
            success_patterns: List of patterns that indicate command completed.
            timeout_s: Timeout in seconds.
            drain_first: Drain UART buffer before sending (prevents bleeding).

        Returns:
            Tuple of (full_response, error).

        Note:
            Due to byte-by-byte MTIB UART delivery, responses arrive slowly.
            This method waits for the command echo, then collects until a
            success pattern + shell prompt is seen.
        """
        try:
            # Drain any pending data first to prevent response bleeding
            if drain_first:
                self.alpha_drain_uart(target, duration_s=1.0)

            input_queue = queue.Queue()

            # Add commands to input queue
            input_queue.put(b"\r")  # Hit ENTER to get prompt
            time.sleep(0.3)  # Slightly longer delay
            input_queue.put(f"{command}\r".encode("utf-8"))

            def request_iterator():
                while True:
                    try:
                        data = input_queue.get_nowait()
                        yield UartStreamRequest(target=target, data=data)
                    except queue.Empty:
                        yield UartStreamRequest(target=target, data=b"")
                        time.sleep(0.05)  # Faster polling (20Hz)

            response_lines = []
            start_time = time.time()
            command_echoed = False
            success_pattern_time = None

            for resp in self.UartStream(target, request_iterator()):
                if not resp.success:
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)

                    # Wait for command echo before treating response as valid
                    # Note: Shell sometimes truncates the last char of echo, so check for partial match
                    echo_to_check = command[:-1] if len(command) > 3 else command
                    if not command_echoed and echo_to_check in full_response:
                        command_echoed = True

                    # Check if any success pattern is present (only after echo)
                    if command_echoed and success_patterns and not success_pattern_time:
                        for pattern in success_patterns:
                            if pattern in full_response:
                                success_pattern_time = time.time()
                                break

                    # Once pattern found, wait for prompt OR additional time
                    if success_pattern_time:
                        elapsed_since_pattern = time.time() - success_pattern_time
                        if "Mfg shell:" in full_response or "Comms Mfg:" in full_response:
                            return full_response, None
                        # Give 5 seconds after pattern for prompt to arrive
                        if elapsed_since_pattern > 5.0:
                            return full_response, None

                if time.time() - start_time > timeout_s:
                    break

            full_response = "".join(response_lines)
            # Check one more time after collecting all data
            if success_patterns:
                for pattern in success_patterns:
                    if pattern in full_response:
                        return full_response, None

            return None, f"Timeout waiting for response. Got: {full_response[:500]}..."

        except Exception as e:
            return None, f"Exception: {str(e)}"

    def alpha_drain_uart(
        self, target: HostType, duration_s: float = 3.0
    ) -> None:
        """Drain any pending UART data from the buffer.

        Call this between commands to prevent response bleeding, especially
        when debug output is enabled and flooding the UART.

        Args:
            target: HostType for UART target.
            duration_s: How long to drain (default 3s).
        """
        def request_iterator():
            start = time.time()
            while time.time() - start < duration_s:
                yield UartStreamRequest(target=target, data=b"")
                time.sleep(0.05)

        try:
            for _ in self.UartStream(target, request_iterator()):
                pass  # Just drain
        except Exception:
            pass

    def alpha_spam_lock_shell(
        self, target: HostType, duration_s: float = 5.0
    ) -> Tuple[bool, str]:
        """Spam lock_shell command to catch the shell activation window.

        IMPORTANT: This is the ONLY way to lock the manufacturing shell reliably.
        The shell activation window is ~2 seconds after boot, then it auto-deactivates.
        This method spams lock_shell commands for the specified duration to ensure
        we catch the window.

        Call this immediately after PowerEnable, BEFORE sending any other commands.

        Args:
            target: HostType for UART target (HOST_TYPE_NRF52840 or HOST_TYPE_NRF9151).
            duration_s: How long to spam lock_shell (default 5s, should cover boot).

        Returns:
            Tuple of (success, full_output).
            success is True if "Locking shell mode ON" or "Mfg shell:" seen.
        """
        output_lines = []

        def request_iterator():
            start = time.time()
            while time.time() - start < duration_s:
                yield UartStreamRequest(target=target, data=b"\rlock_shell\r")
                time.sleep(0.1)

        try:
            for resp in self.UartStream(target, request_iterator()):
                if resp.data:
                    output_lines.append(resp.data.decode("utf-8", errors="ignore"))
        except Exception:
            pass

        full_output = "".join(output_lines)
        success = "mode ON" in full_output or "Mfg shell:" in full_output
        return success, full_output

    def alpha_cmd_lock_shell_app(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode on the Alpha app processor (NRF52840).

        WARNING: This method sends ONE lock_shell command and waits for response.
        It WILL NOT work during boot because the shell activation window is only ~2s.
        Use alpha_spam_lock_shell() instead which spams the command during boot.

        This method is only useful if the shell was already locked and you want
        to re-confirm the lock status.

        Returns:
            Tuple of (success, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="lock_shell",
            success_patterns=["Locking shell mode ON", "mode ON"],
            timeout_s=30,  # Manufacturing uses 30s for app shell
        )
        if err:
            return None, err
        return "mode ON" in (response or ""), None

    def alpha_cmd_debug_disable_app(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART output on the Alpha app processor.

        Returns:
            Tuple of (success, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="debug_enable 0",
            success_patterns=["Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Debug is not enabled" in (response or ""), None

    def alpha_cmd_get_chip_ids_app(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Alpha app processor (NRF52840).

        Returns:
            Tuple of (ext_flash_id, ble_mac, error).
            ext_flash_id: External flash JEDEC ID (e.g., "0xc2 0x28 0x17")
            ble_mac: BLE MAC address string
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        ext_flash_id = None
        ble_mac = None

        # Parse ext flash ID
        if "Ext flash chip ID:" in response:
            match = re.search(r"Ext flash chip ID:\s*(.+)", response)
            if match:
                ext_flash_id = match.group(1).strip()

        # Parse BLE MAC
        if "BLE MAC:" in response:
            match = re.search(r"BLE MAC:\s*(\S+)", response)
            if match:
                ble_mac = match.group(1).strip()

        if ext_flash_id or ble_mac:
            return ext_flash_id, ble_mac, None
        return None, None, f"Failed to parse chip IDs from: {response[:200]}"

    @dataclass
    class BmsTestResult:
        """Result from test_bms command."""
        connected: bool
        chip_id: Optional[str] = None
        charge_percent: Optional[int] = None
        capacity_mah: Optional[int] = None
        temperature_c: Optional[int] = None

    def alpha_cmd_test_bms(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional["MtibV1Client.BmsTestResult"], Optional[str]]:
        """Test BMS (gas gauge) chip on the Alpha app processor.

        Returns:
            Tuple of (BmsTestResult, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="test_bms",
            success_patterns=["BMS connected:", "Temperature:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = MtibV1Client.BmsTestResult(connected=False)

        # Parse BMS connected
        if "BMS connected: yes" in response:
            result.connected = True
        elif "BMS connected: no" in response:
            result.connected = False

        # Parse chip ID
        match = re.search(r"BMS chip ID:\s*(0x[0-9a-fA-F]+)", response)
        if match:
            result.chip_id = match.group(1)

        # Parse charge percent
        match = re.search(r"Charge:\s*(\d+)%", response)
        if match:
            result.charge_percent = int(match.group(1))

        # Parse capacity
        match = re.search(r"Capacity:\s*(\d+)\s*mAh", response)
        if match:
            result.capacity_mah = int(match.group(1))

        # Parse temperature
        match = re.search(r"Temperature:\s*(-?\d+)\s*C", response)
        if match:
            result.temperature_c = int(match.group(1))

        return result, None

    @dataclass
    class ChargerTestResult:
        """Result from test_charger command."""
        chip_id: Optional[str] = None
        chip_id_error: Optional[int] = None
        on_charger: bool = False
        charging: bool = False
        charge_done: bool = False
        battery_voltage_mv: Optional[int] = None

    def alpha_cmd_test_charger(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional["MtibV1Client.ChargerTestResult"], Optional[str]]:
        """Test battery charger chip on the Alpha app processor.

        Returns:
            Tuple of (ChargerTestResult, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="test_charger",
            success_patterns=["Battery voltage:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = MtibV1Client.ChargerTestResult()

        # Parse chip ID
        match = re.search(r"Charger chip ID:\s*(0x[0-9a-fA-F]+)\s*\(err:\s*(-?\d+)\)", response)
        if match:
            result.chip_id = match.group(1)
            result.chip_id_error = int(match.group(2))

        # Parse on charger
        result.on_charger = "On charger: yes" in response

        # Parse charging
        result.charging = "Charging: yes" in response

        # Parse charge done
        result.charge_done = "Charge done: yes" in response

        # Parse battery voltage
        match = re.search(r"Battery voltage:\s*(\d+)\s*mV", response)
        if match:
            result.battery_voltage_mv = int(match.group(1))

        return result, None

    @dataclass
    class GpsTestResult:
        """Result from test_gps command."""
        in_shutdown: bool = True
        tracking: bool = False
        comms_ok: bool = False

    def alpha_cmd_test_gps(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional["MtibV1Client.GpsTestResult"], Optional[str]]:
        """Test GPS (GNSS) module on the Alpha app processor.

        Returns:
            Tuple of (GpsTestResult, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="test_gps",
            success_patterns=["GPS comms:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = MtibV1Client.GpsTestResult()

        # Parse shutdown state
        result.in_shutdown = "GPS shutdown: yes" in response

        # Parse tracking
        result.tracking = "GPS tracking: yes" in response

        # Parse comms status
        result.comms_ok = "GPS comms: OK" in response

        return result, None

    # -----------------------------------------------
    #                 Alpha Comms Processor Commands
    # -----------------------------------------------
    def alpha_cmd_get_modem_fw(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version from the Alpha comms processor.

        Returns:
            Tuple of (modem_fw_version, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_modem_fw",
            success_patterns=["Modem FW:"],
            timeout_s=15,
        )
        if err:
            return None, err

        match = re.search(r"Modem FW:\s*(.+)", response)
        if match:
            return match.group(1).strip(), None
        return None, f"Failed to parse modem FW from: {response[:200]}"

    def alpha_cmd_rekey_ipc(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Trigger IPC rekey on the Alpha comms processor.

        Generates a new IPC encryption key and synchronizes it with the app processor.
        Takes ~2 seconds for the IPC handshake.

        Returns:
            Tuple of (success, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="rekey_ipc",
            success_patterns=["IPC rekey completed successfully", "IPC rekey failed"],
            timeout_s=15,
        )
        if err:
            return None, err

        if "IPC rekey completed successfully" in (response or ""):
            return True, None
        elif "IPC rekey failed" in (response or ""):
            return False, "IPC rekey failed (reported by device)"
        return None, f"Unexpected response: {response[:200]}"

    def alpha_cmd_get_pub_key(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get the device public key from the Alpha comms processor.

        Returns:
            Tuple of (hex_pub_key, base64_pub_key, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_pub_key",
            success_patterns=["Public key (base64):"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        hex_key = None
        b64_key = None

        # Parse hex key
        match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]+)", response)
        if match:
            hex_key = match.group(1)

        # Parse base64 key
        match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]+)", response)
        if match:
            b64_key = match.group(1)

        if hex_key and b64_key:
            return hex_key, b64_key, None
        return None, None, f"Failed to parse public keys from: {response[:200]}"

    def alpha_cmd_lock_shell_comms(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode on the Alpha comms processor (NRF9151).

        Sends lock_shell command to keep the manufacturing shell active.
        Must be called within ~2 seconds of boot.

        Returns:
            Tuple of (success, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="lock_shell",
            success_patterns=["Locking shell mode ON"],
            timeout_s=120,  # Manufacturing uses 120s to drain UART backlog
        )
        if err:
            return None, err
        return "Locking shell mode ON" in (response or ""), None

    def alpha_cmd_debug_disable_comms(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART output on the Alpha comms processor.

        Returns:
            Tuple of (success, error).
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="debug_enable 0",
            success_patterns=["Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Debug is not enabled" in (response or ""), None

    def alpha_cmd_get_chip_ids_comms(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Alpha comms processor (NRF9151).

        Returns:
            Tuple of (ext_flash_id, lora_available, error).
            ext_flash_id: External flash JEDEC ID (e.g., "0xef 0x40 0x17")
            lora_available: LoRa hardware availability string
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_chip_ids",
            success_patterns=["Ext flash chip ID:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        ext_flash_id = None
        lora_available = None

        # Parse ext flash ID
        if "Ext flash chip ID:" in response:
            match = re.search(r"Ext flash chip ID:\s*(.+)", response)
            if match:
                ext_flash_id = match.group(1).strip()

        # Parse LoRa availability
        if "LoRa hardware available:" in response:
            match = re.search(r"LoRa hardware available:\s*(\w+)", response)
            if match:
                lora_available = match.group(1).strip()

        if ext_flash_id:
            return ext_flash_id, lora_available, None
        return None, None, f"Failed to parse chip IDs from: {response[:200]}"

    @dataclass
    class ExtFlashTestResult:
        """Result from external flash read/write test."""
        write_ok: bool = False
        read_ok: bool = False
        data_match: bool = False

    def alpha_cmd_test_ext_flash(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional["MtibV1Client.ExtFlashTestResult"], Optional[str]]:
        """Test external flash on the specified processor.

        Writes a test pattern to flash, reads it back, and verifies match.
        Works for both app (NRF52840) and comms (NRF9151) processors.

        Returns:
            Tuple of (ExtFlashTestResult, error).
        """
        import base64
        result = MtibV1Client.ExtFlashTestResult()

        # Test pattern: "POST_TEST" encoded as base64
        test_data = base64.b64encode(b"POST_TEST").decode("ascii")
        test_addr = "0x100000"  # Safe test address

        # Write test pattern
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"write_ext_flash {test_addr} {test_data}",
            success_patterns=["Writing", "Mfg shell:"],
            timeout_s=15,
        )
        if err:
            return result, err

        if "Writing" in (response or "") or "Mfg shell:" in (response or ""):
            result.write_ok = True
        else:
            return result, f"Write failed: {response[:200]}"

        # Read back 9 bytes ("POST_TEST")
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"read_ext_flash {test_addr} 9",
            success_patterns=["Reading", "Mfg shell:"],
            timeout_s=15,
        )
        if err:
            return result, err

        if "Reading" in (response or "") or response:
            result.read_ok = True
            # Check for expected hex values (POST_TEST = 504F53545F54455354)
            if "504F53545F54455354" in response.upper().replace(" ", ""):
                result.data_match = True
            elif "POST_TEST" in response:
                result.data_match = True

        return result, None

    def cmd_comms_coproc_get_modem_fw_version(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version from the communications co-processor device.

        Returns:
            Tuple of (fw_version, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="get_modem_fw",
            success_patterns=["Modem FW:"],
            timeout_s=15,
        )
        if err:
            return None, err

        match = re.search(r"Modem FW:\s*(.+)", response or "")
        if match:
            return match.group(1).strip(), None
        return None, f"Failed to parse modem FW from: {(response or '')[:200]}"

    def cmd_comms_coproc_get_imei_iccid(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Get IMEI and ICCID from the communications co-processor device.

        Returns:
            Tuple of (imei, iccid_list, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="imei_iccid",
            success_patterns=["IMEI,ICCID"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = response or ""
        imei = None
        iccid_list = []

        # Parse format: "IMEI,ICCID0[,ICCID1]: 358447171854988,89148000009808536124,89457300000035352429"
        match = re.search(r"IMEI,ICCID[01,]*:\s*(.+)", full_response)
        if match:
            parts = [part.strip() for part in match.group(1).split(",")]
            if len(parts) >= 2:
                imei = parts[0]
                iccid_list = parts[1:]

        if imei and iccid_list:
            return imei, iccid_list, None
        return None, None, f"Failed to parse IMEI/ICCIDs from: {full_response[:200]}"

    def cmd_comms_coproc_personalize(
        self, device_id: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Personalize the communications co-processor device.

        Args:
            device_id: The device ID to personalize
        Returns:
            Tuple of (hex_public_key, base64_public_key, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"personalize {device_id}",
            success_patterns=["Public key (base64)"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = re.sub(r"\x1b\[[0-9;]*m", "", response or "")

        hex_match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]{100,})", full_response)
        b64_match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]{40,})", full_response)

        if hex_match and b64_match:
            return hex_match.group(1), b64_match.group(1), None
        return None, None, f"Failed to parse public keys from: {full_response[:300]}"

    def cmd_comms_coproc_read_ext_flash(
        self, address: str, num_bytes: int, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash.

        Args:
            address: The address to read from
            num_bytes: The number of bytes to read
        Returns:
            Tuple of (hex_data, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"read_ext_flash {address} {num_bytes}",
            success_patterns=["Reading", "Mfg shell:", "Comms Mfg:"],
            timeout_s=15,
        )
        if err:
            return None, err

        full_response = response or ""
        # Extract the hex data from hex dump lines (format: "00000000: xx xx xx | ...")
        hex_data = ""
        for line in full_response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")

        if hex_data:
            return hex_data, None
        return None, f"Failed to parse hex data from: {full_response[:200]}"

    def cmd_comms_coproc_erase_ext_flash(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Erase entire external flash.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="erase_ext_flash",
            success_patterns=["Erasing flash", "pages"],
            timeout_s=15,  # Erase can take longer
        )
        if err:
            return None, err
        return "Erasing flash" in (response or ""), None

    def cmd_comms_coproc_write_ext_flash(
        self, address: str, flash_data: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to external flash (data should be base64 encoded).

        Args:
            address: The address to write to
            flash_data: The data to write (base64 encoded)
        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command=f"write_ext_flash {address} {flash_data}",
            success_patterns=["Writing", "bytes to address:"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Writing" in (response or ""), None

    def cmd_comms_coproc_rekey_ipc(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Rekey IPC.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=target,
            command="rekey_ipc",
            success_patterns=["IPC rekey completed successfully", "IPC rekey failed"],
            timeout_s=15,
        )
        if err:
            return None, err

        if "IPC rekey completed successfully" in (response or ""):
            return True, None
        elif "IPC rekey failed" in (response or ""):
            return False, "IPC rekey failed"
        return None, f"Unexpected response: {(response or '')[:200]}"

    # -----------------------------------------------
    #                                 Sigma5 Commands
    # ---------------------------------------------*/
    def cmd_sigma5_app_lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell mode for the Sigma5 app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="lock_shell",
            success_patterns=["Locking shell mode ON"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Locking shell mode ON" in (response or ""), None

    def cmd_sigma5_app_debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART for the Sigma5 app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="debug_enable 0",
            success_patterns=["Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Debug is not enabled" in (response or ""), None

    def cmd_sigma5_app_get_chip_ids(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Sigma5 app processor.

        Returns:
            Tuple of (accel_id, altimeter_id, ext_flash_id, gps_hw_version, ble_mac, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, None, err

        full_response = response or ""

        # Parse each field with regex
        accel_match = re.search(r"Accel chip ID:\s*(.+)", full_response)
        alt_match = re.search(r"Altimeter chip ID:\s*(.+)", full_response)
        flash_match = re.search(r"Ext flash chip ID:\s*(.+)", full_response)
        gps_match = re.search(r"GPS HW version:\s*(.+)", full_response)
        ble_match = re.search(r"BLE MAC:\s*(\S+)", full_response)

        return (
            accel_match.group(1).strip() if accel_match else None,
            alt_match.group(1).strip() if alt_match else None,
            flash_match.group(1).strip() if flash_match else None,
            gps_match.group(1).strip() if gps_match else None,
            ble_match.group(1).strip() if ble_match else None,
            None,
        )

    def cmd_sigma5_app_get_ublox_version_info(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Get ublox version info from the Sigma5 app processor.

        Returns:
            Tuple of (hw_version, fw_version, sw_version, proto_version, constellations, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="get_ublox",
            success_patterns=["GPS constellations:"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, None, err

        full_response = response or ""

        hw_match = re.search(r"GPS HW version:\s*(.+)", full_response)
        fw_match = re.search(r"GPS FW version:\s*(.+)", full_response)
        sw_match = re.search(r"GPS SW version:\s*(.+)", full_response)
        proto_match = re.search(r"GPS protocol version:\s*(.+)", full_response)
        const_match = re.search(r"GPS constellations:\s*(.+)", full_response)

        return (
            hw_match.group(1).strip() if hw_match else None,
            fw_match.group(1).strip() if fw_match else None,
            sw_match.group(1).strip() if sw_match else None,
            proto_match.group(1).strip() if proto_match else None,
            const_match.group(1).strip() if const_match else None,
            None,
        )

    def cmd_sigma5_app_read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Get accelerometer values from the Sigma5 app processor.

        Returns:
            Tuple of (x_raw, y_raw, z_raw, temp, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="read_accel",
            success_patterns=["Accelerometer values"],
            timeout_s=15,
        )
        if err:
            return None, None, None, None, err

        full_response = response or ""
        # Parse format: "Accelerometer values: (x, y, z, temp): 0.890625, -0.015625, 0.437500, 31.000000"
        match = re.search(r"Accelerometer values.*?:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4)), None
            except ValueError:
                pass
        return None, None, None, None, f"Failed to parse accel from: {full_response[:200]}"

    def cmd_sigma5_app_read_altimeter(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Get altimeter values from the Sigma5 app processor.

        Returns:
            Tuple of (pressure_hg, temperature_c, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="read_alt",
            success_patterns=["Altimeter values"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = response or ""
        # Parse format: "Altimeter values (pressure, temp): 28.722524, 25.412672"
        match = re.search(r"Altimeter values.*?:\s*([-\d.]+),\s*([-\d.]+)", full_response)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), None
            except ValueError:
                pass
        return None, None, f"Failed to parse altimeter from: {full_response[:200]}"

    # ===============================================
    #         THETA APP PROCESSOR COMMANDS
    # ===============================================
    #
    # Commands specific to Theta manufacturing firmware
    # App Processor: nRF52840 (HOST_TYPE_NRF52840) with "Mfg shell: " prompt
    #
    # ===============================================

    def cmd_theta_app_lock_shell(self) -> Tuple[Optional[bool], Optional[str]]:
        """Lock shell on theta app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="lock_shell",
            success_patterns=["Shell locked", "Locking shell mode ON"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Shell locked" in (response or "") or "Locking shell mode" in (response or ""), None

    def cmd_theta_app_debug_uart_disable(self) -> Tuple[Optional[bool], Optional[str]]:
        """Disable debug UART on theta app processor.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
            target=HostType.HOST_TYPE_NRF52840,
            command="debug_enable 0",
            success_patterns=["Debug disabled", "Debug output disabled", "Debug is not enabled"],
            timeout_s=15,
        )
        if err:
            return None, err
        return any(p in (response or "") for p in ["Debug disabled", "Debug output disabled", "Debug is not enabled"]), None

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
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_read_accel(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Read accelerometer from theta app processor.

        Returns:
            Tuple of (x_g, y_g, z_g, temp_c, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_read_alt(self) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Read altimeter from theta app processor.

        Returns:
            Tuple of (pressure_hg, temperature_c, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_drone_test(
        self, timeout_ms: int = 10000
    ) -> Tuple[Optional[bool], Optional[int], Optional[int], Optional[str]]:
        """Run drone detection test on theta app processor.

        Args:
            timeout_ms: Test timeout in milliseconds

        Returns:
            Tuple of (success, detected_freq_hz, amplitude_mg, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_meas_bat_voltage(self) -> Tuple[Optional[float], Optional[str]]:
        """Measure battery voltage on theta app processor.

        Returns:
            Tuple of (voltage_v, error_string)
        """
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_membrane_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Run complete membrane board test on theta app processor.

        Returns:
            Tuple of (results_dict, error_string)
            results_dict contains test results for: bme280, gpio_expander, leds, vibration
        """
        response, err = self._alpha_send_uart_cmd(
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

    def cmd_theta_app_env_test(self) -> Tuple[Optional[dict], Optional[str]]:
        """Read BME280 environmental sensors on theta app processor.

        Returns:
            Tuple of (readings_dict, error_string)
            readings_dict contains: temperature_c, humidity_pct, pressure_pa
        """
        response, err = self._alpha_send_uart_cmd(
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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
            timeout = 30

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
