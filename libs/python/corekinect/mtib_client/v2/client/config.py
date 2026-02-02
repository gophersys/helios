"""Configuration classes for MTIB V2 client."""


class NetConfig:
    """Network configuration for gRPC connection.

    Attributes:
        addr: Server address (hostname or IP)
        port: Server port number
    """

    def __init__(
        self,
        addr: str = "127.0.0.1",
        port: int = 50052,
    ):
        """Initialize network configuration.

        Args:
            addr: Server address. Defaults to localhost.
            port: Server port. Defaults to 50052 (V2 port).
        """
        self.addr: str = addr
        self.port: int = port
