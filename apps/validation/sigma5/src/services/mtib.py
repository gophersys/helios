from typing import Optional
from corekinect.mtib_client.v1 import MtibV1Client, NetConfig

# Global MTIB client instance
appMtibClient: Optional[MtibV1Client] = None


def init_mtib_client(host: str, port: int) -> Optional[str]:
    """Initialize the global MTIB client instance"""
    global appMtibClient

    if appMtibClient is None:
        # Initialize the MTIB client
        appMtibClient = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=host,
                    port=port,
                )
            )
        )

        # Connect to the server
        if err := appMtibClient.connect():
            return f"Error connecting to server: {err}"

        # Health check
        ready, errors, error = appMtibClient.HealthCheck()
        if error:
            return f"Error checking health: {error}"

        if not ready:
            return f"Error checking health: {errors}"

        return None

    return f"MTIB client already initialized"


def get_mtib_client() -> MtibV1Client:
    """Get the global MTIB client instance"""
    return appMtibClient
