# Standard includes
import argparse
import logging
import os
import queue
import select
import sys
import termios
import threading
import time
import traceback
import tty
from typing import Callable, Optional

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client, NetConfig

# Corekinect includes
from corekinect.utils import EnvConfig, Logger

# Import types directly from the protocol
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest


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


class UartTerminal:
    """Interactive UART terminal like minicom."""

    def __init__(self, client: MtibV1Client, logger: Logger, target: HostType):
        self.client = client
        self.logger = logger
        self.target = target
        self.running = False
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.old_settings = None

    def start(self):
        """Start the interactive UART terminal."""
        self.running = True
        self.logger.info(f"Starting UART terminal for {self.target}")
        self.logger.info("Type your commands. All keystrokes are sent immediately. Ctrl+C to exit.")

        # Save terminal settings and set raw mode
        self._setup_terminal()

        # Start input thread
        input_thread = threading.Thread(target=self._input_loop, daemon=True)
        input_thread.start()

        # Start output thread
        output_thread = threading.Thread(target=self._output_loop, daemon=True)
        output_thread.start()

        try:
            # Main loop - handle UART stream
            self._uart_loop()
        except KeyboardInterrupt:
            # This should not happen in raw mode, but just in case
            self._restore_terminal()
            print("\n")  # Add a clean newline
            self.logger.info("Terminal interrupted by user")
        finally:
            self.stop()

    def _setup_terminal(self):
        """Set up terminal for raw input mode."""
        try:
            # Save current terminal settings
            self.old_settings = termios.tcgetattr(sys.stdin)

            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno())

            # Set non-blocking mode
            fd = sys.stdin.fileno()
            try:
                old_flags = os.get_blocking(fd)
                os.set_blocking(fd, False)
            except AttributeError:
                # get_blocking/set_blocking not available on all systems
                pass

        except Exception as e:
            self.logger.warning(f"Could not set terminal to raw mode: {e}")
            self.old_settings = None

    def _restore_terminal(self):
        """Restore terminal to original settings."""
        try:
            if self.old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        except Exception as e:
            self.logger.warning(f"Could not restore terminal settings: {e}")

    def _input_loop(self):
        """Background thread to read user input."""
        while self.running:
            try:
                # Read individual characters in raw mode
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)
                    if char:
                        # Check for Ctrl+C (ASCII 3)
                        if ord(char) == 3:
                            # Restore terminal immediately for clean output
                            self._restore_terminal()
                            print("\n")  # Add a clean newline
                            self.logger.info("Received Ctrl+C, stopping terminal...")
                            self.running = False
                            break

                        # Encode and send the character
                        data = char.encode("utf-8")
                        self.input_queue.put(data)
            except Exception as e:
                self.logger.error(f"Input loop error: {e}")
                break

    def _output_loop(self):
        """Background thread to write output to console."""
        while self.running:
            try:
                data = self.output_queue.get(timeout=0.1)
                if data:
                    # Write to stdout without newline (raw output)
                    sys.stdout.write(data.decode("utf-8", errors="ignore"))
                    sys.stdout.flush()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Output loop error: {e}")
                break

    def _uart_loop(self):
        """Main UART communication loop."""

        def request_iterator():
            while self.running:
                try:
                    # Get input from queue (non-blocking)
                    data = self.input_queue.get_nowait()
                    yield UartStreamRequest(target=self.target, data=data)
                except queue.Empty:
                    # No input, send empty request to keep stream alive
                    # Use longer sleep like the working example
                    time.sleep(0.001)
                    yield UartStreamRequest(target=self.target, data=b"")

        # Start UART stream
        try:
            for response in self.client.UartStream(self.target, request_iterator()):
                if not self.running:
                    break

                if not response.success:
                    self.logger.error(f"UART stream error: {response.message}")
                    break

                if response.data:
                    # Put received data in output queue
                    self.output_queue.put(response.data)

        except Exception as e:
            self.logger.error(f"UART stream exception: {e}")
            if self.running:
                self.logger.info("Attempting to reconnect...")
                time.sleep(1)
                # Try to restart the stream
                self._uart_loop()

    def stop(self):
        """Stop the terminal."""
        self.running = False
        # Terminal is already restored in Ctrl+C handler, but restore again just in case
        self._restore_terminal()
        self.logger.info("UART terminal stopped")


def parse_target(target_str: str) -> HostType:
    """Parse target string to HostType enum."""
    target_map = {
        "nrf52840": HostType.HOST_TYPE_NRF52840,
        "nrf9160": HostType.HOST_TYPE_NRF9160,
        "nrf5340": HostType.HOST_TYPE_NRF5340,
        "nrf9151": HostType.HOST_TYPE_NRF9151,
    }

    target_lower = target_str.lower()
    if target_lower not in target_map:
        raise ValueError(f"Invalid target '{target_str}'. Valid targets: {', '.join(target_map.keys())}")

    return target_map[target_lower]


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Interactive UART terminal like minicom.
    """
    logger.info("Interactive UART Terminal")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Interactive UART terminal for MTIB targets")
    parser.add_argument(
        "target", choices=["nrf52840", "nrf9160", "nrf5340", "nrf9151"], help="Target device to connect to"
    )
    args = parser.parse_args()

    # Parse target
    try:
        target = parse_target(args.target)
    except ValueError as e:
        logger.error(f"Invalid target: {e}")
        return

    logger.info(f"Opening UART terminal for target: {target}")

    # Create and start terminal
    terminal = UartTerminal(client, logger, target)
    terminal.start()


if __name__ == "__main__":
    run_sample(sample, "uart_simple")
