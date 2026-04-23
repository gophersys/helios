"""MQTT metrics worker for periodic ADC/GPIO publishing."""

# Standard library
import socket
import threading
import time
from typing import Dict, Optional

# Third party
import paho.mqtt.client as mqtt

# Corekinect
from corekinect.utils import Logger

# Drivers
from src.drivers.gpio import Gpio


class MetricsWorker:
    """Publishes ADC and GPIO metrics to MQTT at 10Hz."""

    def __init__(self, logger: Logger, broker_url: str, gpios: Dict[int, Gpio], adc_handler):
        self._logger = logger
        self._gpios = gpios
        self._adc_handler = adc_handler  # AdcHandler instance (for _read_raw, _calculate_real_voltage)
        self._client: Optional[mqtt.Client] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._hostname = socket.gethostname()

        # Parse and connect
        self._connect(broker_url)

    def _connect(self, broker_url: str):
        """Parse broker URL and connect MQTT client."""
        try:
            self._client = mqtt.Client()
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect

            if broker_url.startswith("mqtts://"):
                broker_host = broker_url[8:]
                default_port = 8883
                self._client.tls_set()
            elif broker_url.startswith("mqtt://"):
                broker_host = broker_url[7:]
                default_port = 1883
            else:
                broker_host = broker_url
                default_port = 1883

            if ":" in broker_host:
                host, port = broker_host.split(":", 1)
                port = int(port)
            else:
                host = broker_host
                port = default_port

            self._client.connect(host, port, 60)
            self._running = True
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
            self._logger.info("Metrics worker started")
        except Exception as e:
            self._logger.error(f"Failed to initialize metrics: {e}")
            raise

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._logger.info("Connected to MQTT broker")
        else:
            self._logger.error(f"MQTT connect failed: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self._logger.warning(f"Unexpected MQTT disconnect: {rc}")

    def _worker(self):
        """10Hz publish loop."""
        while self._running:
            try:
                self._publish_adc()
                self._publish_gpio()
                time.sleep(0.1)
            except Exception as e:
                self._logger.error(f"Metrics worker error: {e}")
                time.sleep(1)

    def _publish_adc(self):
        if not self._client or not self._adc_handler:
            return
        try:
            for channel in range(8):
                err, raw_value = self._adc_handler._read_raw(channel)
                if not err:
                    voltage = self._adc_handler._calculate_real_voltage(raw_value, channel)
                    self._client.publish(f"{self._hostname}/metrics/adc/{channel}", voltage, qos=0)
        except Exception as e:
            self._logger.error(f"ADC metrics error: {e}")

    def _publish_gpio(self):
        if not self._client or not self._gpios:
            return
        try:
            for gpio_num, gpio in self._gpios.items():
                try:
                    err, state = gpio.read()
                    if not err:
                        self._client.publish(f"{self._hostname}/metrics/gpio/{gpio_num}", state, qos=0)
                except Exception:
                    pass
        except Exception as e:
            self._logger.error(f"GPIO metrics error: {e}")

    def stop(self):
        if self._running:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            if self._client:
                self._client.disconnect()
            self._logger.info("Metrics worker stopped")
