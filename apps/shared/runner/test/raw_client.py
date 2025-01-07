# Standard includes
import sys

# Corekinect includes
from corekinect.utils.log import Logger
from corekinect.mtib_runner_client.v1.client import MtibRunnerV1Client

ADDR = "127.0.0.1"
PORT = 50051

if __name__ == "__main__":
    # Instantiate a logger
    logger: Logger = Logger(
        config=Logger.Config(
            logger_name="runner_client",
        )
    )

    # Instantiate a client
    client = MtibRunnerV1Client(
        config=MtibRunnerV1Client.Config(
            addr=ADDR,
            port=PORT,
        )
    )

    # Connect
    error = client.connect()
    if error is not None:
        logger.error(f"Could not connect to runner at {ADDR}:{PORT}")
        sys.exit(1)

    logger.info(f"Client succesfully connected to {ADDR}:{PORT}")
