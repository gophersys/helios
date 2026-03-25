# Standard includes
import inspect
import os
import time
from typing import Iterator, List, Optional, Tuple

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
