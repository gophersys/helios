import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

import paho.mqtt.client as mqtt

# Corekinect includes
from corekinect.utils import Logger
from paho.mqtt.enums import MQTTErrorCode
from src.providers.mtib import *

LOG_MODULE = "data_logger"


@dataclass
class MetricsClientConfig:
    MQTT_BROKER_URL: str

    SERVER_PORT: int


class MetricsClient:
    def __init__(self, config: MetricsClientConfig, logger: Logger):
        # Setup the config
        self.config: MetricsClientConfig = config

        # Setup the logger for the server
        self.logger: Logger = logger
        if self.logger is None:
            self.logger = Logger(
                Logger.Config(
                    logger_name="data_logger",
                    log_directory="logs",
                    overall_log_level=logging.DEBUG,
                    console_log_level=logging.DEBUG,
                    file_log_level=logging.DEBUG,
                    enable_log_color=True,
                )
            )
        else:
            # Create a child logger from the parent
            self.logger = logger.from_parent(LOG_MODULE)

        # Objects we manage
        self.mqtt_client: mqtt.Client = None

        # Thread management
        self.adc_thread: Optional[threading.Thread] = None
        self.stop_event: threading.Event = threading.Event()
        self.adc_thread_running: bool = False

    def init(self, provider: MtibV1Provider) -> Optional[str]:
        start_time = time.time()
        self.logger.debug("Initializing with config: %s", self.config)

        # Setup the provider
        self.provider: MtibV1Provider = provider

        # Using the paho libaray, and parsing URLs that may come like this:"mqtt://10.4.45.7:1883",
        # attempt to connect to the broker, and return errors accordingly
        try:
            # Parse the URL
            host, port = self.config.MQTT_BROKER_URL.split("://")[1].split(":")

            self.logger.debug("Connecting to MQTT broker at %s:%s", host, port)
            client = mqtt.Client()
            result = client.connect(host, int(port))
            if result != MQTTErrorCode.MQTT_ERR_SUCCESS:
                return f"Failed to connect to MQTT broker: {result}"

            self.logger.info("Connected to MQTT broker at %s:%s", host, port)

            self.mqtt_client = client
        except Exception as e:
            return f"Failed to connect to MQTT broker: {e}"

        # Start the ADC reading thread
        self._start_adc_thread()

        self.logger.info("Data logger client initialized OK in %s ms", (time.time() - start_time) * 1000)
        return None

    def deinit(self) -> Optional[str]:
        # Stop the ADC thread gracefully
        self._stop_adc_thread()

        # Check if the MQTT client is connected
        if self.mqtt_client is not None:
            self.logger.debug("Disconnecting from MQTT broker")
            result = self.mqtt_client.disconnect()
            if result != MQTTErrorCode.MQTT_ERR_SUCCESS:
                return f"Failed to disconnect from MQTT broker: {result}"
            self.mqtt_client = None

        # Disconnect the client
        self.logger.debug("Deinitializing")

        return None

    def _start_adc_thread(self) -> None:
        """Start the ADC reading background thread."""
        if self.adc_thread_running:
            self.logger.warning("ADC thread is already running")
            return

        self.stop_event.clear()
        self.adc_thread_running = True
        self.adc_thread = threading.Thread(target=self._adc_thread_worker, daemon=True)
        self.adc_thread.start()
        self.logger.info("ADC reading thread started")

    def _stop_adc_thread(self) -> None:
        """Stop the ADC reading background thread gracefully."""
        if not self.adc_thread_running:
            return

        self.logger.debug("Stopping ADC reading thread...")
        self.stop_event.set()

        if self.adc_thread and self.adc_thread.is_alive():
            self.adc_thread.join(timeout=2.0)  # Wait up to 2 seconds for graceful shutdown
            if self.adc_thread.is_alive():
                self.logger.warning("ADC thread did not stop gracefully within timeout")

        self.adc_thread_running = False
        self.logger.info("ADC reading thread stopped")

    def _adc_thread_worker(self) -> None:
        """Background thread worker that reads ADC data at 100Hz and publishes to MQTT."""
        self.logger.debug("ADC thread worker started")

        # Target frequency: 100Hz = 10ms interval
        target_interval = 0.1

        while not self.stop_event.is_set():
            loop_start = time.time()

            try:
                # Read all ADC channels (0-7)
                response = self.provider._adc_handlers.read_all(Empty(), None)

                if not response.success:
                    self.logger.error("Failed to read ADC data: %s", response.message)
                elif response.voltages_v is not None:
                    # Publish each channel to its respective MQTT topic
                    for channel, voltage in enumerate(response.voltages_v):
                        if channel < 8:  # Ensure we don't exceed expected channels

                            # Get the hostname
                            hostname = socket.gethostname()
                            topic = f"{hostname}/adc/{channel}"
                            payload = voltage

                            try:
                                result = self.mqtt_client.publish(topic, payload)
                                if result.rc != MQTTErrorCode.MQTT_ERR_SUCCESS:
                                    self.logger.error("Failed to publish to topic %s: %s", topic, result.rc)
                            except Exception as e:
                                self.logger.error("Exception publishing to topic %s: %s", topic, e)
                else:
                    self.logger.warning("Received None voltages from AdcReadAll")

            except Exception as e:
                self.logger.error("Exception in ADC thread worker: %s", e)

            # Calculate sleep time to maintain 100Hz frequency
            loop_duration = time.time() - loop_start
            sleep_time = max(0, target_interval - loop_duration)

            if sleep_time > 0:
                self.stop_event.wait(sleep_time)
            else:
                # If we're taking longer than target interval, log a warning occasionally
                if loop_duration > target_interval * 1.1:  # 10% tolerance
                    self.logger.debug(
                        "ADC loop took %f ms (target: %f ms)", loop_duration * 1000, target_interval * 1000
                    )

        self.logger.debug("ADC thread worker finished")
