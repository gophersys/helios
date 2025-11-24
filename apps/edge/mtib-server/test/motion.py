# Standard includes
import logging
import signal
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
    Test the motion system with both duration-based and distance-based motion.
    """
    logger.info("Testing motion system")

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

    try:
        start_time = time.time()

        # Get the status of the motion system
        status, err = client.GetMotionStatus()
        if err:
            logger.error(f"Error getting motion system status: {err}")
            sys.exit(1)

        logger.info(f"Motion system status: {MotionStatus(status)}")

        # Home the motion system
        logger.info("Homing motion system...")
        err = client.MotionHome()
        if err:
            logger.error(f"Error homing motion system: {err}")
            sys.exit(1)

        logger.info("Motion system homed successfully")

        # Test motion in a simple loop
        logger.info("Starting motion test loop...")

        test_cases = [
            # {
            #     "name": "Initial test - Small distance with default acceleration",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 0,
            #     "speed_mm_s": 10000,  # 1000 mm/s = 60000 mm/min
            #     "distance_mm": 3000,
            #     "accel_mm_s2": 300,  # Default from config
            # },
            # {
            #     "name": "Test with custom acceleration (800 mm/s²)",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 0,
            #     "speed_mm_s": 15000,  # 1500 mm/s
            #     "distance_mm": 2000,
            #     "accel_mm_s2": 400,  # Will require homing after this
            # },
            # {
            #     "name": "Back to default acceleration (600 mm/s²)",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 0,
            #     "speed_mm_s": 12000,
            #     "distance_mm": 1500,
            #     "accel_mm_s2": 300,  # Will require homing after this
            # },
            # {
            #     "name": "Low acceleration test (400 mm/s²)",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 1,
            #     "speed_mm_s": 800,
            #     "distance_mm": 2500,
            #     "accel_mm_s2": 100,  # Will require homing after this
            # },
            # {
            #     "name": "High speed test with dwell",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 2,
            #     "speed_mm_s": 20000,  # 2000 mm/s = 120000 mm/min
            #     "distance_mm": 3000,
            #     "accel_mm_s2": 300,
            # },
            # {
            #     "name": "Duration-based test (5 seconds)",
            #     "duration_seconds": 5,
            #     "dwell_seconds": 1,
            #     "speed_mm_s": 1000,
            #     "distance_mm": 0,  # Uses duration instead
            #     "accel_mm_s2": 300,
            # },
            # {
            #     "name": "Large distance bouncing (1000mm)",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 0,
            #     "speed_mm_s": 18000,  # 3000 mm/s (very fast)
            #     "distance_mm": 10000,  # Will bounce multiple times
            #     "accel_mm_s2": 500,
            # },
            # {
            #     "name": "Final test - Back to slow and low accel",
            #     "duration_seconds": 0,
            #     "dwell_seconds": 0,
            #     "speed_mm_s": 500,
            #     "distance_mm": 10000,
            #     "accel_mm_s2": 100,  # Will require homing after this
            # },
            {
                "name": "Test with same acceleration - should NOT re-home",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 500,
                "distance_mm": 2500,
                "accel_mm_s2": 300,  # Same as previous - should continue from where it is
            },
            {
                "name": "Uneven distance test - 3717mm",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 8000,
                "distance_mm": 3717,  # Uneven number
                "accel_mm_s2": 300,
            },
            {
                "name": "Another uneven distance - 4753mm",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 8000,
                "distance_mm": 4753,  # Uneven number
                "accel_mm_s2": 300,  # Same accel - should continue from position
            },
            {
                "name": "Small uneven distance - 1234mm",
                "duration_seconds": 0,
                "dwell_seconds": 1,
                "speed_mm_s": 5000,
                "distance_mm": 1234,  # Uneven number
                "accel_mm_s2": 300,  # Same accel - should continue
            },
            {
                "name": "Large uneven distance - 8765mm",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 10000,
                "distance_mm": 8765,  # Uneven number
                "accel_mm_s2": 300,  # Same accel - should continue
            },
            {
                "name": "Change acceleration - will re-home",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 6000,
                "distance_mm": 5000,
                "accel_mm_s2": 500,  # Different accel - should re-home
            },
            {
                "name": "Same acceleration again - should NOT re-home",
                "duration_seconds": 0,
                "dwell_seconds": 0,
                "speed_mm_s": 6000,
                "distance_mm": 3000,
                "accel_mm_s2": 500,  # Same as previous - should continue
            },
            {
                "name": "Prime number distance - 1237mm",
                "duration_seconds": 0,
                "dwell_seconds": 0.5,
                "speed_mm_s": 7000,
                "distance_mm": 1237,  # Prime number
                "accel_mm_s2": 300,
            },
            {
                "name": "Another prime - 1997mm",
                "duration_seconds": 0,
                "dwell_seconds": 0.5,
                "speed_mm_s": 7000,
                "distance_mm": 1997,  # Prime number
                "accel_mm_s2": 300,  # Same accel - should continue
            },
        ]

        last_accel = None  # Track the last acceleration used

        for i, test_case in enumerate(test_cases):
            logger.info(f"\n--- Test {i+1}/{len(test_cases)}: {test_case['name']} ---")

            # Calculate expected distance for logging
            if test_case["distance_mm"] > 0:
                expected_distance = test_case["distance_mm"]
                logger.info(f"Using direct distance: {expected_distance}mm")
            else:
                expected_distance = test_case["duration_seconds"] * test_case["speed_mm_s"]
                logger.info(
                    f"Calculated distance: {test_case['duration_seconds']}s × {test_case['speed_mm_s']}mm/s = {expected_distance}mm"
                )

            logger.info(f"Speed: {test_case['speed_mm_s']}mm/s ({test_case['speed_mm_s'] * 60:.0f}mm/min)")
            logger.info(f"Acceleration: {test_case['accel_mm_s2']}mm/s²")
            logger.info(f"Dwell: {test_case['dwell_seconds']}s")

            # Execute the motion
            start_time = time.time()
            last_status = None
            error_occurred = False

            # Stream the motion updates
            for response in client.MotionStart(
                duration_seconds=test_case["duration_seconds"],
                dwell_seconds=test_case["dwell_seconds"],
                speed_mm_s=test_case["speed_mm_s"],
                distance_mm=test_case["distance_mm"],
                accel_mm_s2=test_case["accel_mm_s2"],
            ):
                if not response.success:
                    logger.error(f"Motion failed: {response.message}")
                    error_occurred = True
                    break

                last_status = response.status

                # Log progress updates
                if hasattr(response, "status") and last_status == MotionStatus.MOVING:
                    progress_info = []
                    if hasattr(response, "time_elapsed_seconds") and response.time_elapsed_seconds:
                        progress_info.append(f"Time: {response.time_elapsed_seconds}s")
                    if hasattr(response, "distance_covered_mm") and response.distance_covered_mm:
                        progress_info.append(f"Distance: {response.distance_covered_mm:.2f}mm")
                    if hasattr(response, "distance_remaining_mm") and response.distance_remaining_mm:
                        progress_info.append(f"Remaining: {response.distance_remaining_mm:.2f}mm")
                    if hasattr(response, "time_remaining_seconds") and response.time_remaining_seconds:
                        progress_info.append(f"Time remaining: {response.time_remaining_seconds}s")

                    if progress_info:
                        logger.info(f"Motion progress: {', '.join(progress_info)}")

            end_time = time.time()

            if error_occurred:
                logger.error("Motion failed with errors")
                # Still update last_accel even on failure
                last_accel = test_case["accel_mm_s2"]
                continue

            actual_duration = end_time - start_time
            logger.info(f"Motion completed successfully in {actual_duration:.2f}s")

            # Update last acceleration
            last_accel = test_case["accel_mm_s2"]

            # Wait a bit between tests (except for the last one)
            if i < len(test_cases) - 1:
                logger.info("Waiting 2 seconds before next test...")
                time.sleep(2)

        logger.info(f"\n--- All motion tests completed successfully! in {time.time() - start_time:.2f}s ---")

    except Exception as e:
        logger.error(f"Error running motion sample: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_sample(sample, "motion")
