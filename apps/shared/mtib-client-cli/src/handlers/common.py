from typing import Any, Callable, Optional
import typer

from corekinect.mtib_client.v1 import MtibV1Client, NetConfig
from corekinect.utils import Logger


def run_with_client(handler_func: Callable, config: Any, logger: Logger, *args, **kwargs) -> None:
    """
    Common handler that manages client connection lifecycle

    Args:
        handler_func: The actual handler function to execute
        config: Application configuration
        logger: Application logger
        *args: Additional positional arguments for the handler
        **kwargs: Additional keyword arguments for the handler
    """
    # Create client configuration
    client_config = MtibV1Client.Config(net=NetConfig(addr=config.SERVER_HOST, port=config.SERVER_PORT))

    # Create client instance
    client = MtibV1Client(client_config, logger)

    try:
        # Connect to server
        err = client.connect()
        if err:
            logger.error(f"Failed to connect to server: {err}")
            raise typer.Exit(1)

        # Execute the handler
        handler_func(client, *args, **kwargs)

    except Exception as e:
        logger.error(f"Command failed: {str(e)}")
        raise typer.Exit(1)

    finally:
        # Always try to disconnect
        err = client.disconnect()
        if err:
            logger.error(f"Error disconnecting: {err}")
