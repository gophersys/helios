# Simple non-interactive UART monitor for debugging
import argparse
import logging
import queue
import sys
import threading
import time
import traceback
from typing import Optional

from corekinect.mtib_client.v1 import MtibV1Client, NetConfig
from corekinect.utils import EnvConfig, Logger
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest


class MtibCliEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_HOST: str
    SERVER_PORT: int


def parse_target(target_str: str) -> HostType:
    target_map = {
        "nrf52840": HostType.HOST_TYPE_NRF52840,
        "nrf9160": HostType.HOST_TYPE_NRF9160,
        "nrf5340": HostType.HOST_TYPE_NRF5340,
        "nrf9151": HostType.HOST_TYPE_NRF9151,
    }
    target_lower = target_str.lower()
    if target_lower not in target_map:
        raise ValueError(f"Invalid target '{target_str}'")
    return target_map[target_lower]


def monitor_uart(client: MtibV1Client, logger: Logger, target: HostType, duration: int = 120):
    """Monitor UART stream without sending any data (read-only)."""
    logger.info(f"Monitoring UART for target {target} for {duration} seconds...")

    running = True
    start_time = time.time()

    def request_iterator():
        while running and (time.time() - start_time) < duration:
            # Send empty requests to keep stream alive and receive data
            yield UartStreamRequest(target=target, data=b"")
            time.sleep(0.05)  # 50ms polling

    try:
        for response in client.UartStream(target, request_iterator()):
            if not response.success:
                logger.error(f"UART stream error: {response.message}")
                break

            if response.data:
                # Decode and print the received data
                text = response.data.decode("utf-8", errors="ignore")
                # Print with timestamp
                timestamp = time.strftime("%H:%M:%S")
                for line in text.split('\n'):
                    if line.strip():
                        print(f"[{timestamp}] [{target}] {repr(line)}")
                        sys.stdout.flush()

            if (time.time() - start_time) >= duration:
                break

    except KeyboardInterrupt:
        logger.info("Monitor interrupted")
    except Exception as e:
        logger.error(f"UART stream exception: {e}")
        traceback.print_exc()

    logger.info(f"UART monitoring ended for {target}")


def main():
    parser = argparse.ArgumentParser(description="UART Monitor for MTIB targets")
    parser.add_argument(
        "target",
        choices=["nrf52840", "nrf9160", "nrf5340", "nrf9151"],
        help="Target device to monitor"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=120,
        help="Duration to monitor in seconds (default: 120)"
    )
    args = parser.parse_args()

    logger: Optional[Logger] = None
    client: Optional[MtibV1Client] = None

    try:
        env_config = MtibCliEnvConfig()

        log_config = Logger.Config(
            logger_name="uart_monitor",
            log_directory=env_config.LOG_PATH,
            overall_log_level=env_config.LOG_LEVEL,
            console_log_level=env_config.LOG_LEVEL,
            file_log_level=logging.DEBUG,
            enable_log_color=True,
        )
        logger = Logger(log_config)

        client = MtibV1Client(
            config=MtibV1Client.Config(
                net=NetConfig(
                    addr=env_config.SERVER_HOST,
                    port=env_config.SERVER_PORT,
                )
            ),
            logger=logger,
        )

        if err := client.connect():
            logger.error(f"Error connecting to server: {err}")
            sys.exit(1)

        ready, errors, error = client.HealthCheck()
        if error or not ready:
            logger.error(f"Error checking health: {error}")
            sys.exit(1)

        logger.info(f"Connected to server at {env_config.SERVER_HOST}:{env_config.SERVER_PORT}")

        target = parse_target(args.target)
        monitor_uart(client, logger, target, args.duration)

    except Exception as e:
        if logger:
            logger.error(f"Failed: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"Failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        if client:
            if err := client.disconnect():
                if logger:
                    logger.error(f"Error disconnecting: {err}")


if __name__ == "__main__":
    main()
