# Standard imports
import functools
import json
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional

# 3rd party imports
import grpc
import paho.mqtt.client as mqtt
from gpiod.line import Direction

# Corekinect imports
LOG_MODULE = "grpc"
from corekinect.utils import Logger

# Protocol imports
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer
from src.shared.types import *

# Function handlers makes it easier to write service handlers
from .handlers.adc import AdcHandler
from .handlers.firmware import FirmwareHandler
from .handlers.gpio import Gpio, GpioHandler, Pin
from .handlers.motion import MotionHandler
from .handlers.power import PowerHandler
from .handlers.sensors import SensorsHandler
from .handlers.uart import UartHandler

# -------------------------------------------------
#                             Toradex SoM GPIO Maps
# -------------------------------------------------
HARDWARE_REV_1_1_GPIO_PIN_MAP = {
    # Main connector
    0: Pin.SODIMM_206,  # GPIO_0 - available on gpiochip2, line 4
    1: Pin.SODIMM_208,  # GPIO_1 - available on gpiochip4, line 5
    2: Pin.SODIMM_210,  # GPIO_2 - available on gpiochip4, line 26
    3: Pin.SODIMM_212,  # GPIO_3 - available on gpiochip4, line 27
    4: Pin.SODIMM_34,  # I2S1_D_OUT - available on gpiochip3, line 26
    5: Pin.SODIMM_30,  # I2S1_BCLK - available on gpiochip3, line 25
    6: Pin.SODIMM_32,  # I2S1_SYNC - available on gpiochip3, line 24
    # Auxiliary connector
    7: Pin.SODIMM_15,  # PWM_1 - available on gpiochip4, line 10
    8: Pin.SODIMM_16,  # PWM_2 - available on gpiochip4, line 12
}

# Where the serial port is located
HARDWARE_REV_1_1_SERIAL_PORT: str = "/dev/ttyUSB0"
HARDWARE_REV_1_1_RESET_PIN: Pin = Pin.SODIMM_36

HARDWARE_REV_1_2_GPIO_PIN_MAP = {
    # Main connector
    0: Pin.SODIMM_206,  # GPIO_0 - available on gpiochip2, line 4
    1: Pin.SODIMM_208,  # GPIO_1 - available on gpiochip4, line 5
    2: Pin.SODIMM_210,  # GPIO_2 - available on gpiochip4, line 26
    3: Pin.SODIMM_212,  # GPIO_3 - available on gpiochip4, line 27
    4: Pin.SODIMM_34,  # I2S1_D_OUT - available on gpiochip3, line 26
    5: Pin.SODIMM_30,  # I2S1_BCLK - available on gpiochip3, line 25
    6: Pin.SODIMM_32,  # I2S1_SYNC - available on gpiochip3, line 24
    # Auxiliary connector
    7: Pin.SODIMM_15,  # PWM_1 - available on gpiochip4, line 10
    8: Pin.SODIMM_16,  # PWM_2 - available on gpiochip4, line 12
}

HARDWARE_REV_1_2_SERIAL_PORT: str = "/dev/ttyUSB0"
HARDWARE_REV_1_2_RESET_PIN: Pin = Pin.SODIMM_36

# -------------------------------------------------
#                             gRPC Method Decorator
# -------------------------------------------------


def grpc_method(func: Callable) -> Callable:
    @functools.wraps(func)
    def method(self, request, context, *args, **kwargs):
        """
        Decorator to log important information about a gRPC method.
        """
        # Get method name from the original function
        method_name = func.__name__

        # Log request received
        self.logger.debug(f"{method_name}: Request received from {context.peer()}")

        # Time the request
        start_time = time.time()

        try:
            # Execute the original function
            response = func(self, request, context, *args, **kwargs)

            # Log request completion time
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"{method_name}: Request processed OK in {elapsed_ms:.2f}ms for {context.peer()}")

            return response

        except Exception as e:
            # Log any errors that occur
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.error(f"{method_name}: Request exception, {elapsed_ms:.2f}ms for {context.peer()}: {e}")
            raise  # Re-raise the exception

    return method


# -------------------------------------------------
#                                            Config
# -------------------------------------------------
@dataclass
class MtibV1ProviderConfig:
    # Supported hardware versions:
    # - REV1.1
    # - REV1.2
    HARDWARE_VERSION: str

    # Where the server will look for assets for all of its components
    # that need configurations or firmware files (e.g. FluidNC)
    ASSETS_DIR: str

    # Whether to enable metrics
    METRICS_ENABLED: bool

    # Where the metrics broker is located
    METRICS_BROKER_URL: str

    # Whether to enable motion
    MOTION_ENABLED: bool


# -----------------------------------------------------
#                                 MTIB Service Provider
# -----------------------------------------------------
class MtibV1Provider(MtibV1Servicer):
    # -------------------------------------------------
    #                                              Init
    # -------------------------------------------------
    def __init__(self, config: MtibV1ProviderConfig, logger: Logger = None):
        start_time = time.time()
        self.config: MtibV1ProviderConfig = config

        # Setup the logger for the server
        self.logger: Logger = logger
        if self.logger is None:
            raise ValueError("Logger is required")
        else:
            self.logger = logger.from_parent(LOG_MODULE)

        # Global error list for all components
        self.errors: List[str] = []

        # Objects we manage
        self._gpios: Dict[int, Gpio] = {}

        # Metrics client
        self._metrics_client: Optional[mqtt.Client] = None
        self._metrics_thread: Optional[threading.Thread] = None
        self._metrics_running = False
        self._hostname = socket.gethostname()

        self.logger.info(f"Hostname: {self._hostname}")

        # Initialize all the objects
        if err := self._config_gpio():
            self.logger.error(f"Failed to initialize the components: {err}")
            raise Exception(err)

        if err := self._init_handlers():
            self.logger.error(f"Failed to initialize the handlers: {err}")
            raise Exception(err)

        if err := self._init_metrics():
            self.logger.error(f"Failed to initialize the metrics: {err}")
            raise Exception(err)

        self.logger.info("MtibV1Provider initialized OK in %s ms", (time.time() - start_time) * 1000)

    def _config_gpio(self) -> Optional[str]:
        """
        Configure the GPIOs.
        """
        # Determine which GPIO map to use based on the hardware version
        if self.config.HARDWARE_VERSION == "REV1.1":
            gpio_map = HARDWARE_REV_1_1_GPIO_PIN_MAP
        elif self.config.HARDWARE_VERSION == "REV1.2":
            gpio_map = HARDWARE_REV_1_2_GPIO_PIN_MAP
        else:
            return f"Unsupported hardware version: {self.config.HARDWARE_VERSION}"

        # Initialize all GPIOs as INPUTs by default
        for logical_num, pin in gpio_map.items():
            # Initialize as INPUT with initial value INACTIVE (0)
            gpio = Gpio(consumer=f"mtib-gpio-{logical_num}", pin=pin, direction=Direction.INPUT)
            if err := gpio.init():
                return f"Failed to initialize GPIO {logical_num} ({pin}): {err}"
            self._gpios[logical_num] = gpio

        self.logger.debug("All GPIOs configured successfully")
        return None

    def _init_handlers(self) -> Optional[str]:
        """
        Initialize the servicer function handlers, such as GPIO, ADC, Motion, Power, Sensors, Firmware, and UART.
        """
        # Determine which GPIO map to use based on the hardware version
        if self.config.HARDWARE_VERSION == "REV1.1":
            gpio_map = HARDWARE_REV_1_1_GPIO_PIN_MAP
        elif self.config.HARDWARE_VERSION == "REV1.2":
            gpio_map = HARDWARE_REV_1_2_GPIO_PIN_MAP
        else:
            return f"Unsupported hardware version: {self.config.HARDWARE_VERSION}"

        self._gpio_handlers = GpioHandler(self._gpios, self.logger)
        self._adc_handlers = AdcHandler(self.logger)
        self._power_handlers = PowerHandler(self.logger)
        self._firmware_handlers = FirmwareHandler(self.logger)
        self._sensors_handlers = SensorsHandler(self.logger)
        self._uart_handlers = UartHandler(self.logger)

        # Initialize the motion handler based on the hardware version
        if self.config.MOTION_ENABLED:
            if self.config.HARDWARE_VERSION == "REV1.1":
                self._motion_handlers = MotionHandler(
                    self.logger, self.config.ASSETS_DIR, HARDWARE_REV_1_1_SERIAL_PORT, HARDWARE_REV_1_1_RESET_PIN
                )
            elif self.config.HARDWARE_VERSION == "REV1.2":
                self._motion_handlers = MotionHandler(
                    self.logger, self.config.ASSETS_DIR, HARDWARE_REV_1_2_SERIAL_PORT, HARDWARE_REV_1_2_RESET_PIN
                )
            else:
                return f"Unsupported hardware version: {self.config.HARDWARE_VERSION}"

        return None

    def _init_metrics(self) -> Optional[str]:
        """
        Initialize the metrics client.
        """
        if not self.config.METRICS_ENABLED:
            return None

        try:
            # Create MQTT client
            self._metrics_client = mqtt.Client()

            # Set up callbacks
            self._metrics_client.on_connect = self._on_mqtt_connect
            self._metrics_client.on_disconnect = self._on_mqtt_disconnect
            self._metrics_client.on_publish = self._on_mqtt_publish

            # Connect to broker
            broker_url = self.config.METRICS_BROKER_URL
            self.logger.info(f"Connecting to MQTT broker at {broker_url}")

            # Parse broker URL (format: mqtt://host:port or mqtts://host:port)
            if broker_url.startswith("mqtts://"):
                # MQTT over SSL/TLS
                broker_host = broker_url[8:]  # Remove "mqtts://"
                if ":" in broker_host:
                    host, port = broker_host.split(":", 1)
                    port = int(port)
                else:
                    host = broker_host
                    port = 8883
                self._metrics_client.tls_set()
            elif broker_url.startswith("mqtt://"):
                # Plain MQTT
                broker_host = broker_url[7:]  # Remove "mqtt://"
                if ":" in broker_host:
                    host, port = broker_host.split(":", 1)
                    port = int(port)
                else:
                    host = broker_host
                    port = 1883
            else:
                # Assume plain MQTT with default port
                host = broker_url
                port = 1883

            # Connect to broker
            self._metrics_client.connect(host, port, 60)

            # Start the metrics thread
            self._metrics_running = True
            self._metrics_thread = threading.Thread(target=self._metrics_worker, daemon=True)
            self._metrics_thread.start()

            self.logger.info("Metrics client initialized successfully")
            return None

        except Exception as e:
            self.logger.error(f"Failed to initialize metrics client: {e}")
            return f"Failed to initialize metrics client: {e}"

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection."""
        if rc == 0:
            self.logger.info("Connected to MQTT broker successfully")
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection."""
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnection: {rc}")
        else:
            self.logger.info("Disconnected from MQTT broker")

    def _on_mqtt_publish(self, client, userdata, mid):
        """Callback for MQTT message publish."""
        pass

    def _metrics_worker(self):
        """Worker thread that publishes metrics at 10Hz."""
        self.logger.info("Metrics worker thread started")

        while self._metrics_running:
            try:
                # Publish ADC metrics
                self._publish_adc_metrics()

                # Publish GPIO metrics
                self._publish_gpio_metrics()

                # Sleep for 100ms (10Hz)
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in metrics worker: {e}")
                time.sleep(1)  # Wait longer on error

        self.logger.info("Metrics worker thread stopped")

    def _publish_adc_metrics(self):
        """Publish ADC channel metrics to MQTT."""
        if not self._metrics_client or not self._adc_handlers:
            return

        try:
            # Read all ADC channels
            for channel in range(8):
                err, raw_value = self._adc_handlers._read_raw(channel)
                if not err:
                    voltage = self._adc_handlers._calculate_real_voltage(raw_value, channel)

                    # Publish individual channel metric - just the voltage value
                    topic = f"{self._hostname}/metrics/adc/{channel}"
                    payload = voltage

                    result = self._metrics_client.publish(topic, payload, qos=0)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        self.logger.warning(f"Failed to publish ADC metric for channel {channel}: {result.rc}")

                else:
                    self.logger.warning(f"Failed to read ADC channel {channel}: {err}")

        except Exception as e:
            self.logger.error(f"Error publishing ADC metrics: {e}")

    def _publish_gpio_metrics(self):
        """Publish GPIO state metrics to MQTT."""
        if not self._metrics_client or not self._gpios:
            return

        try:
            # Read all GPIO states
            for gpio_num, gpio in self._gpios.items():
                try:
                    err, state = gpio.read()
                    if err:
                        self.logger.warning(f"Failed to read GPIO {gpio_num}: {err}")
                        continue

                    # Publish individual GPIO metric - just the state value
                    topic = f"{self._hostname}/metrics/gpio/{gpio_num}"
                    payload = state

                    result = self._metrics_client.publish(topic, payload, qos=0)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        self.logger.warning(f"Failed to publish GPIO metric for GPIO {gpio_num}: {result.rc}")

                except Exception as e:
                    self.logger.warning(f"Failed to read GPIO {gpio_num}: {e}")

        except Exception as e:
            self.logger.error(f"Error publishing GPIO metrics: {e}")

    def stop_metrics(self):
        """Stop the metrics client and worker thread."""
        if self._metrics_running:
            self.logger.info("Stopping metrics client...")
            self._metrics_running = False

            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=5)

            if self._metrics_client:
                self._metrics_client.disconnect()
                self.logger.info("Metrics client stopped")

    def __del__(self):
        """Cleanup when the provider is destroyed."""
        self.stop_metrics()

    # -------------------------------------------------
    #                                     Health Check
    # -------------------------------------------------
    @grpc_method
    def HealthCheck(self, request: Empty, context: grpc.ServicerContext) -> HealthCheckResponse:
        self.logger.info("HealthCheck request received")
        return HealthCheckResponse(ready=True, errors=self.errors)

    # -------------------------------------------------
    #                                              GPIO
    # -------------------------------------------------
    @grpc_method
    def GpioConfig(self, request: GpioConfigRequest, context: grpc.ServicerContext) -> GpioConfigResponse:
        return self._gpio_handlers.config(request, context)

    @grpc_method
    def GpioWrite(self, request: GpioWriteRequest, context: grpc.ServicerContext) -> GpioWriteResponse:
        return self._gpio_handlers.write(request, context)

    @grpc_method
    def GpioRead(self, request: GpioReadRequest, context: grpc.ServicerContext) -> GpioReadResponse:
        return self._gpio_handlers.read(request, context)

    # -------------------------------------------------
    #                                               ADC
    # -------------------------------------------------
    @grpc_method
    def AdcRead(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        return self._adc_handlers.read(request, context)

    @grpc_method
    def AdcReadAll(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        return self._adc_handlers.read_all(request, context)

    # -------------------------------------------------
    #                                             Power
    # -------------------------------------------------
    @grpc_method
    def DutPowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_power_enable(request, context)

    @grpc_method
    def DutPowerDisable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_power_disable(request, context)

    @grpc_method
    def DutChargePowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_charge_power_enable(request, context)

    @grpc_method
    def DutChargePowerDisable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_charge_power_disable(request, context)

    # -------------------------------------------------
    #                                 Power Consumption
    # -------------------------------------------------
    @grpc_method
    def DutPowerRead(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        return self._power_handlers.dut_power_read(request, context)

    @grpc_method
    def DutChargePowerRead(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        return self._power_handlers.dut_charge_power_read(request, context)

    # -------------------------------------------------
    #                                           Sensors
    # -------------------------------------------------
    @grpc_method
    def AltimeterRead(self, request: Empty, context: grpc.ServicerContext) -> AltimeterReadResponse:
        return self._sensors_handlers.read_altimeter(request, context)

    @grpc_method
    def AccelRead(self, request: Empty, context: grpc.ServicerContext) -> AccelReadResponse:
        return self._sensors_handlers.read_accel(request, context)

    # -------------------------------------------------
    #                                            Motion
    # -------------------------------------------------
    @grpc_method
    def GetMotionStatus(self, request: Empty, context: grpc.ServicerContext) -> GetMotionStatusResponse:
        if not self.config.MOTION_ENABLED:
            return GetMotionStatusResponse(success=False, message="Motion is not enabled")
        return self._motion_handlers.get_status(request, context)

    @grpc_method
    def MotionStart(self, request: MotionStartRequest, context: grpc.ServicerContext) -> MotionStartResponse:
        if not self.config.MOTION_ENABLED:
            return MotionStartResponse(success=False, message="Motion is not enabled")
        return self._motion_handlers.start(request, context)

    @grpc_method
    def MotionHome(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
        if not self.config.MOTION_ENABLED:
            return MotionHomeResponse(success=False, message="Motion is not enabled")
        return self._motion_handlers.home(request, context)

    @grpc_method
    def MotionStop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
        if not self.config.MOTION_ENABLED:
            return MotionStopResponse(success=False, message="Motion is not enabled")
        return self._motion_handlers.stop(request, context)

    # -------------------------------------------------
    #                                          Firmware
    # -------------------------------------------------
    @grpc_method
    def ListProgrammers(self, request: Empty, context: grpc.ServicerContext) -> ListProgrammersResponse:
        return self._firmware_handlers.list_programmers(request, context)

    @grpc_method
    def ListFwFiles(self, request: Empty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        return self._firmware_handlers.list_fw_files(request, context)

    @grpc_method
    def UploadFwFile(
        self, request_iterator: Iterator[UploadFwFileRequest], context: grpc.ServicerContext
    ) -> UploadFwFileResponse:
        return self._firmware_handlers.upload_fw_file(request_iterator, context)

    @grpc_method
    def DeleteFwFile(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        return self._firmware_handlers.delete_fw_file(request, context)

    @grpc_method
    def FlashFwFile(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        return self._firmware_handlers.flash_fw_file(request, context)

    @grpc_method
    def EraseFlash(self, request: EraseFlashRequest, context: grpc.ServicerContext) -> EraseFlashResponse:
        return self._firmware_handlers.erase_flash(request, context)

    @grpc_method
    def EnableAppProtect(
        self, request: EnableAppProtectRequest, context: grpc.ServicerContext
    ) -> EnableAppProtectResponse:
        return self._firmware_handlers.enable_app_protect(request, context)

    # -------------------------------------------------
    #                                              UART
    # -------------------------------------------------
    def UartStream(
        self, request_iterator: Iterator[UartStreamRequest], context: grpc.ServicerContext
    ) -> Iterator[UartStreamResponse]:
        return self._uart_handlers.stream(request_iterator, context)
