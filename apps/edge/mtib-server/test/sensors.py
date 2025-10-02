# Standard includes
import logging
import sys
import time
import traceback
from typing import Any, Callable, Optional

# Private includes
from corekinect.mtib_client.v1 import *

# Corekinect includes
from corekinect.utils import EnvConfig, Logger


# Environment variables for the Mtib client
class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


def run_sample(sample_func: Callable[[MtibV1Client, Logger], None], sample_name: str = "mtib_sample") -> None:
    """
    Run a sample function with standardized error handling, logging, and setup.

    Args:
        sample_func: Function that takes a MtibV1Client and Logger and performs the sample operations
        sample_name: Name of the sample (used for logging)
    """
    logger: Optional[Logger] = None
    client: Optional[MtibV1Client] = None

    try:
        env_config = MtibCliEnvConfig()

        # Setup logging
        log_config = Logger.Config(
            logger_name=sample_name,
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,  # Always log everything to file
            enable_log_color=True,
        )
        logger = Logger(log_config)

        # Initialize the client
        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.SERVER_HOST,
                    port=env_config.SERVER_PORT,
                )
            ),
            logger=logger,
        )

        # Connect to the server
        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            sys.exit(1)

        # Health check
        ready, errors, error = client.HealthCheck()
        if error:
            logger.error(f"Error checking health: {error}")
            sys.exit(1)

        if not ready:
            logger.error(f"Error checking health: {errors}")
            sys.exit(1)

        logger.info("Health check passed for server at %s:%d", env_config.SERVER_HOST, env_config.SERVER_PORT)

        # Run the actual sample function
        sample_func(client, logger)

    except Exception as e:
        if logger:
            # Print the entire traceback
            logger.error(f"Failed to run the sample: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"Failed to run the sample: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Ensure we disconnect even if there was an error
        if client:
            if err := client.disconnect():
                if logger:
                    logger.error(f"Error disconnecting from server: {err}")
                else:
                    print(f"Error disconnecting from server: {err}")


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Test the sensor functions on the MTIB board.
    """
    logger.info("Testing Sensors")

    # Test BME280 Altimeter
    logger.info("=" * 50)
    logger.info("Testing BME280 Altimeter")
    logger.info("=" * 50)

    for i in range(5):
        logger.info(f"--- Altimeter Reading {i+1} ---")
        start_time = time.time()

        temp_f, pressure_hg, altitude_ft, error = client.AltimeterRead()
        if error:
            logger.error(f"Error reading altimeter: {error}")
            continue

        end_time = time.time()
        logger.info(f"Time taken to read altimeter: {(end_time - start_time) * 1000:.2f}ms")
        logger.info(f"Temperature: {temp_f:.2f}°F")
        logger.info(f"Pressure: {pressure_hg:.2f} inHg")
        logger.info(f"Altitude: {altitude_ft:.2f} ft")
        logger.info(f"Message: {error}")

        time.sleep(1)  # Wait between readings

    # Test Accelerometer
    logger.info("=" * 50)
    logger.info("Testing Accelerometer")
    logger.info("=" * 50)

    for i in range(5):
        logger.info(f"--- Accelerometer Reading {i+1} ---")
        start_time = time.time()

        response, error = client.AccelRead()
        if error:
            logger.error(f"Error reading accelerometer: {error}")
            continue

        if not response.success:
            logger.error(f"Error reading accelerometer: {response.message}")
            continue

        end_time = time.time()
        logger.info(f"Time taken to read accelerometer: {(end_time - start_time) * 1000:.2f}ms")
        logger.info(f"X-axis: {response.x_g:.3f}g")
        logger.info(f"Y-axis: {response.y_g:.3f}g")
        logger.info(f"Z-axis: {response.z_g:.3f}g")
        logger.info(f"Message: {response.message}")

        time.sleep(1)  # Wait between readings

    # Test rapid readings
    logger.info("=" * 50)
    logger.info("Testing Rapid Sensor Readings")
    logger.info("=" * 50)

    logger.info("Rapid altimeter readings (10 readings):")
    altimeter_times = []
    for i in range(10):
        start_time = time.time()
        temp_f, pressure_hg, altitude_ft, error = client.AltimeterRead()
        if error:
            logger.error(f"Error reading altimeter: {error}")
            continue

        end_time = time.time()
        read_time = (end_time - start_time) * 1000
        altimeter_times.append(read_time)

        logger.info(
            f"Reading {i+1}: {read_time:.2f}ms - Temp: {temp_f:.1f}°F, "
            f"Pressure: {pressure_hg:.2f} inHg, Altitude: {altitude_ft:.1f} ft"
        )

    logger.info(
        f"Altimeter timing stats - Min: {min(altimeter_times):.2f}ms, "
        f"Max: {max(altimeter_times):.2f}ms, Avg: {sum(altimeter_times)/len(altimeter_times):.2f}ms"
    )

    logger.info("Rapid accelerometer readings (10 readings):")
    accel_times = []
    for i in range(10):
        start_time = time.time()
        response, error = client.AccelRead()
        end_time = time.time()
        read_time = (end_time - start_time) * 1000
        accel_times.append(read_time)

        if error:
            logger.error(f"Reading {i+1}: {read_time:.2f}ms - Error: {error}")
        elif response.success:
            logger.info(
                f"Reading {i+1}: {read_time:.2f}ms - X: {response.x_g:.3f}g, "
                f"Y: {response.y_g:.3f}g, Z: {response.z_g:.3f}g"
            )
        else:
            logger.error(f"Reading {i+1}: {read_time:.2f}ms - Error: {response.message}")

    logger.info(
        f"Accelerometer timing stats - Min: {min(accel_times):.2f}ms, "
        f"Max: {max(accel_times):.2f}ms, Avg: {sum(accel_times)/len(accel_times):.2f}ms"
    )

    logger.info("=" * 50)
    logger.info("Sensor testing completed!")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_sample(sample, "sensors")
