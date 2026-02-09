from typing import Optional

import grpc
from grpc import insecure_channel, RpcError

from corekinect.utils import Logger
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub

from .config import ClientConfig
from .system import SystemMixin
from .target import TargetMixin
from .debug import DebugMixin
from .flash import FlashMixin
from .rtt import RttMixin
from .swo import SwoMixin
from .uart import UartMixin
from .power import PowerMixin
from .logic import LogicMixin
from .gpio import GpioMixin
from .i2c import I2cMixin
from .spi import SpiMixin
from .can import CanMixin
from .ble import BleMixin
from .zephyr import ZephyrMixin
from .files import FilesMixin
from .observability import ObservabilityMixin


class MtibV2Client(
    SystemMixin,
    TargetMixin,
    DebugMixin,
    FlashMixin,
    RttMixin,
    SwoMixin,
    UartMixin,
    PowerMixin,
    LogicMixin,
    GpioMixin,
    I2cMixin,
    SpiMixin,
    CanMixin,
    BleMixin,
    ZephyrMixin,
    FilesMixin,
    ObservabilityMixin,
):
    """MTIB V2 gRPC client.

    Provides a clean, typed interface to all MTIB V2 hardware capabilities
    organized by domain (system, debug, flash, power, GPIO, etc.).

    All methods use Go-style error returns:
    - Action methods return Optional[str] (None = success, str = error message)
    - Value methods return (Optional[str], result) tuples

    Args:
        config: Client configuration with network settings and timeouts.
        logger: Optional logger instance. Creates a default if None.

    Example:
        ```python
        from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig

        config = ClientConfig(net=NetConfig(addr="192.168.1.100", port=50052))
        client = MtibV2Client(config)
        error = client.connect()
        if error:
            print(f"Connection failed: {error}")
        else:
            err, health = client.health_check()
            print(f"Version: {health.version}")
            client.disconnect()
        ```
    """

    def __init__(self, config: ClientConfig, logger: Logger = None):
        """Initialize the MTIB V2 client.

        Args:
            config: Client configuration.
            logger: Optional logger. Creates default if None.
        """
        self.config = config
        self._timeout = config.timeout_s

        if logger is None:
            self.logger = Logger(
                config=Logger.Config(logger_name="mtib_client_v2")
            )
        else:
            self.logger = logger.from_parent("mtib_client_v2")

        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[MtibV2Stub] = None

    def connect(self) -> Optional[str]:
        """Connect to the MTIB V2 server.

        Establishes a gRPC channel and verifies connectivity with a health check.

        Returns:
            Error message string, or None on success.
        """
        try:
            addr = f"{self.config.net.addr}:{self.config.net.port}"
            self._channel = insecure_channel(addr)
            self._stub = MtibV2Stub(self._channel)

            err, health = self.health_check()
            if err:
                return err
            if not health.ready:
                return f"Server not ready: {health.errors}"

            self.logger.debug(
                "Connected to MTIB V2 at %s (version: %s)",
                addr,
                health.version,
            )
            return None
        except RpcError as e:
            return (
                f"Failed to connect to MTIB V2 at "
                f"{self.config.net.addr}:{self.config.net.port}: {e.details()}"
            )
        except Exception as e:
            return (
                f"Unexpected error connecting to MTIB V2 at "
                f"{self.config.net.addr}:{self.config.net.port}: {e}"
            )

    def disconnect(self) -> Optional[str]:
        """Disconnect from the MTIB V2 server.

        Closes the gRPC channel. Safe to call even if not connected.

        Returns:
            Error message string, or None on success.
        """
        try:
            if self._channel:
                self._channel.close()
                self._channel = None
                self._stub = None
            return None
        except Exception as e:
            return f"Error disconnecting: {e}"
