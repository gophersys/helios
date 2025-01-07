# Corekinect includes
from corekinect.utils import Logger
from corekinect.mtib_runner.v1.client import MtibRunnerV1Client, NetConfig
from typing import Optional


if __name__ == "__main__":
    logger: Logger = Logger(
        config=Logger.Config(
            logger_name="runner_test",
        )
    )

    # Initialize the runner client
    runner_client = MtibRunnerV1Client(
        config=MtibRunnerV1Client.Config(net=NetConfig(port=50052)),
        logger=logger,
    )

    # Connect to the runner client
    err = runner_client.connect()
    if err:
        logger.error(err)
        exit(1)

    # Get runner information
    info, err = runner_client.get_runner_info()
    if err:
        logger.error(err)
        exit(1)

    logger.info(f"Runner Info: {vars(info)}")
    logger.info(f"Runner Features: {vars(info.features)}")

    # Home the device
    err = runner_client.motion_home()
    if err:
        logger.error(f"Error homing device: {err}")
    else:
        logger.info("Device homed successfully.")

    # Trigger motion for a specific number of cycles and cycle time
    err = runner_client.motion_trigger(num_cycles=10, cycle_time_seconds=5)
    if err:
        logger.error(f"Error triggering motion: {err}")
    else:
        logger.info("Motion triggered successfully.")

    # Start continuous motion for a duration in seconds
    err = runner_client.motion_continuous(duration_seconds=120)
    if err:
        logger.error(f"Error starting continuous motion: {err}")
    else:
        logger.info("Continuous motion started successfully for 120 seconds.")

    # Stop the motion
    err = runner_client.motion_stop()
    if err:
        logger.error(f"Error stopping motion: {err}")
    else:
        logger.info("Motion stopped successfully.")

    # Disconnect the client
    runner_client.disconnect()
    logger.info("Client disconnected successfully.")
