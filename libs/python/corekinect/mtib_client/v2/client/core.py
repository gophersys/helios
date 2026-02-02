"""MTIB V2 gRPC Client.

This module provides the MtibV2Client class for communicating with MTIB V2 servers.
"""

# Standard includes
import inspect
from typing import List, Optional, Tuple

# 3rd Party includes
import grpc
from grpc import insecure_channel

# Corekinect includes
from corekinect.utils import Logger

# Protocol includes
from protocols.mtib_v2.mtib_v2_pb2 import (
    Empty,
    HealthCheckRequest,
    HealthCheckResponse,
    SystemInfoRequest,
    SystemInfoResponse,
    # Power types
    PowerConfig,
    PowerChannel,
    PowerEnableRequest,
    PowerDisableRequest,
    PowerStatusRequest,
    PowerStatusResponse,
    # GPIO types
    GpioDirection,
    GpioPull,
    GpioConfigRequest,
    GpioWriteRequest,
    GpioReadRequest,
    GpioReadResponse,
    Response,
)
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub

from .config import NetConfig

# Global timeout constant for all gRPC calls (in seconds)
DEFAULT_GRPC_TIMEOUT_SECONDS = 10


class MtibV2Client:
    """gRPC client for communicating with MTIB V2 servers.

    This client provides a high-level interface for controlling and monitoring
    MTIB hardware including GPIO, ADC, power management, debug probes, sensors,
    motion control, and more.

    Attributes:
        config: Client configuration containing network settings
        logger: Logger instance for debugging and error reporting

    Example:
        ```python
        from corekinect.mtib_client.v2 import MtibV2Client, NetConfig

        config = MtibV2Client.Config(net=NetConfig(addr="192.168.1.100", port=50052))
        client = MtibV2Client(config)
        error = client.connect()
        if error:
            print(f"Connection failed: {error}")
        else:
            ready, errors, err = client.HealthCheck()
            if err:
                print(f"Health check failed: {err}")
            client.disconnect()
        ```
    """

    # -----------------------------------------------
    #                                          Config
    # -----------------------------------------------
    class Config:
        """Configuration for the MTIB V2 client.

        Attributes:
            net: Network configuration for gRPC connection
        """

        def __init__(
            self,
            net: NetConfig = NetConfig(),
        ):
            """Initialize client configuration.

            Args:
                net: Network configuration with address and port. Defaults to localhost:50052.
            """
            self.net: NetConfig = net

    # -----------------------------------------------
    #                                           Init
    # -----------------------------------------------
    def __init__(self, config: Config, logger: Logger = None):
        """Initialize the MTIB V2 client.

        Args:
            config: Client configuration containing network settings
            logger: Optional logger instance. If None, creates a new logger.
        """
        self.config: self.Config = config

        if logger is None:
            self.logger: Logger = Logger(
                config=Logger.Config(
                    logger_name="mtib_client_v2",
                )
            )
        else:
            self.logger: Logger = logger.from_parent("mtib_client_v2")

        # Internal gRPC objects
        self.channel: grpc.Channel = None
        self.stub: MtibV2Stub = None

    # -----------------------------------------------
    #                                        Helpers
    # -----------------------------------------------
    def _get_func_name(self) -> str:
        """Get the name of the calling function for error messages.

        Returns:
            Name of the calling function.
        """
        return inspect.currentframe().f_back.f_code.co_name

    # -----------------------------------------------
    #                                     Connection
    # -----------------------------------------------
    def connect(self) -> Optional[str]:
        """Connect to the MTIB V2 server.

        Returns:
            None on success, error string on failure.
        """
        try:
            target = f"{self.config.net.addr}:{self.config.net.port}"
            self.logger.info(f"Connecting to {target}")
            self.channel = insecure_channel(target)
            self.stub = MtibV2Stub(self.channel)
            return None
        except Exception as e:
            return f"Failed to connect: {e}"

    def disconnect(self) -> None:
        """Disconnect from the MTIB V2 server."""
        if self.channel is not None:
            self.channel.close()
            self.channel = None
            self.stub = None
            self.logger.info("Disconnected")

    # -----------------------------------------------
    #                                   Health/System
    # -----------------------------------------------
    def HealthCheck(
        self, timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS
    ) -> Tuple[bool, List[str], Optional[str]]:
        """Check server health status.

        Args:
            timeout: RPC timeout in seconds.

        Returns:
            Tuple of (ready, errors_list, error_message).
            - ready: True if server is ready
            - errors_list: List of error strings from server
            - error_message: None on success, error string on RPC failure
        """
        try:
            response: HealthCheckResponse = self.stub.HealthCheck(
                HealthCheckRequest(),
                timeout=timeout,
            )
            return response.ready, list(response.errors), None
        except grpc.RpcError as e:
            return False, [], f"HealthCheck RPC failed: {e.details()}"
        except Exception as e:
            return False, [], f"HealthCheck failed: {e}"

    def SystemInfo(
        self, timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS
    ) -> Tuple[Optional[SystemInfoResponse], Optional[str]]:
        """Get server system information.

        Args:
            timeout: RPC timeout in seconds.

        Returns:
            Tuple of (response, error_message).
            - response: SystemInfoResponse on success, None on failure
            - error_message: None on success, error string on failure
        """
        try:
            response: SystemInfoResponse = self.stub.SystemInfo(
                SystemInfoRequest(),
                timeout=timeout,
            )
            if response.success:
                return response, None
            return None, response.message
        except grpc.RpcError as e:
            return None, f"SystemInfo RPC failed: {e.details()}"
        except Exception as e:
            return None, f"SystemInfo failed: {e}"

    # -----------------------------------------------
    #                                           GPIO
    # -----------------------------------------------
    def GpioConfig(
        self,
        pin: int,
        direction: GpioDirection,
        pull: GpioPull = GpioPull.GPIO_PULL_NONE,
        open_drain: bool = False,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Configure a GPIO pin.

        Args:
            pin: Pin number to configure.
            direction: Pin direction (INPUT or OUTPUT).
            pull: Pull resistor configuration.
            open_drain: Enable open-drain mode.
            timeout: RPC timeout in seconds.

        Returns:
            None on success, error string on failure.
        """
        try:
            response: Response = self.stub.GpioConfig(
                GpioConfigRequest(
                    pin=pin,
                    direction=direction,
                    pull=pull,
                    open_drain=open_drain,
                ),
                timeout=timeout,
            )
            if response.success:
                return None
            return response.message
        except grpc.RpcError as e:
            return f"GpioConfig RPC failed: {e.details()}"
        except Exception as e:
            return f"GpioConfig failed: {e}"

    def GpioWrite(
        self,
        pin: int,
        value: bool,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Write to a GPIO pin.

        Args:
            pin: Pin number to write.
            value: Value to write (True=high, False=low).
            timeout: RPC timeout in seconds.

        Returns:
            None on success, error string on failure.
        """
        try:
            response: Response = self.stub.GpioWrite(
                GpioWriteRequest(pin=pin, value=value),
                timeout=timeout,
            )
            if response.success:
                return None
            return response.message
        except grpc.RpcError as e:
            return f"GpioWrite RPC failed: {e.details()}"
        except Exception as e:
            return f"GpioWrite failed: {e}"

    def GpioRead(
        self,
        pin: int,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Read a GPIO pin.

        Args:
            pin: Pin number to read.
            timeout: RPC timeout in seconds.

        Returns:
            Tuple of (value, error_message).
            - value: Pin value (True=high, False=low), None on failure
            - error_message: None on success, error string on failure
        """
        try:
            response: GpioReadResponse = self.stub.GpioRead(
                GpioReadRequest(pin=pin),
                timeout=timeout,
            )
            if response.success:
                return response.value, None
            return None, response.message
        except grpc.RpcError as e:
            return None, f"GpioRead RPC failed: {e.details()}"
        except Exception as e:
            return None, f"GpioRead failed: {e}"

    # -----------------------------------------------
    #                                           Power
    # -----------------------------------------------
    def PowerEnable(
        self,
        channel: PowerChannel = PowerChannel.POWER_MAIN,
        voltage_v: float = 3.3,
        current_limit_ma: float = 500.0,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Enable power to a channel.

        Args:
            channel: Power channel to enable.
            voltage_v: Target voltage in volts.
            current_limit_ma: Current limit in milliamps.
            timeout: RPC timeout in seconds.

        Returns:
            None on success, error string on failure.
        """
        try:
            response: Response = self.stub.PowerEnable(
                PowerEnableRequest(
                    config=PowerConfig(
                        channel=channel,
                        voltage_v=voltage_v,
                        current_limit_ma=current_limit_ma,
                    )
                ),
                timeout=timeout,
            )
            if response.success:
                return None
            return response.message
        except grpc.RpcError as e:
            return f"PowerEnable RPC failed: {e.details()}"
        except Exception as e:
            return f"PowerEnable failed: {e}"

    def PowerDisable(
        self,
        channel: PowerChannel = PowerChannel.POWER_MAIN,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Disable power to a channel.

        Args:
            channel: Power channel to disable.
            timeout: RPC timeout in seconds.

        Returns:
            None on success, error string on failure.
        """
        try:
            response: Response = self.stub.PowerDisable(
                PowerDisableRequest(channel=channel),
                timeout=timeout,
            )
            if response.success:
                return None
            return response.message
        except grpc.RpcError as e:
            return f"PowerDisable RPC failed: {e.details()}"
        except Exception as e:
            return f"PowerDisable failed: {e}"

    def PowerStatus(
        self,
        channel: PowerChannel = PowerChannel.POWER_MAIN,
        timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS,
    ) -> Tuple[Optional[PowerStatusResponse], Optional[str]]:
        """Get power status for a channel.

        Args:
            channel: Power channel to query.
            timeout: RPC timeout in seconds.

        Returns:
            Tuple of (response, error_message).
            - response: PowerStatusResponse on success, None on failure
            - error_message: None on success, error string on failure
        """
        try:
            response: PowerStatusResponse = self.stub.PowerStatus(
                PowerStatusRequest(channel=channel),
                timeout=timeout,
            )
            if response.success:
                return response, None
            return None, response.message
        except grpc.RpcError as e:
            return None, f"PowerStatus RPC failed: {e.details()}"
        except Exception as e:
            return None, f"PowerStatus failed: {e}"
