from dataclasses import dataclass, field


@dataclass
class NetConfig:
    """Network configuration for gRPC connection.

    Args:
        addr: Server address. Defaults to localhost.
        port: Server port. Defaults to 50052 (V2 default).
    """

    addr: str = "127.0.0.1"
    port: int = 50052


@dataclass
class ClientConfig:
    """Configuration for the MTIB V2 client.

    Args:
        net: Network configuration for gRPC connection.
        timeout_s: Default timeout for unary RPCs in seconds.
        max_retries: Maximum number of retries for failed calls.
    """

    net: NetConfig = field(default_factory=NetConfig)
    timeout_s: float = 10.0
    max_retries: int = 3
