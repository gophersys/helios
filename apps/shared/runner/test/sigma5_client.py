# Standard includes
import sys

# Corekinect includes
from corekinect.utils.log import Logger
from corekinect.manufacturing.sigma5.mtib_runner_client import Sigma5MtibRunnerClient, MtibRunnerV1Client

ADDR = "127.0.0.1"
PORT = 50051

if __name__ == "__main__":
    # Instantiate a logger
    logger: Logger = Logger(
        config=Logger.Config(
            logger_name="sigma5_client",
        )
    )

    # Instantiate a client
    client = Sigma5MtibRunnerClient(
        config=MtibRunnerV1Client.Config(
            addr=ADDR,
            port=PORT,
        )
    )

    # Connect
    error = client.connect()
    if error is not None:
        logger.error(f"Could not connect to Sigma5 runner at {ADDR}:{PORT}")
        sys.exit(1)

    logger.info(f"Sigma5 client succesfully connected to {ADDR}:{PORT}")
