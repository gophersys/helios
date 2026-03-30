"""MtibV1Provider — thin gRPC router with driver/handler wiring."""

import functools
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional

import grpc
import paho.mqtt.client as mqtt
from gpiod.line import Direction

from corekinect.utils import Logger
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer

from src.shared.types import (
    Empty,
    GpioConfigRequest,
    GpioConfigResponse,
    GpioDirection,
    GpioReadRequest,
    GpioReadResponse,
    GpioWriteRequest,
    GpioWriteResponse,
    GpioWatchRequest,
    GpioWatchEvent,
    AdcReadRequest,
    AdcReadResponse,
    AdcReadAllResponse,
    AdcStreamRequest,
    AdcStreamResponse,
    PowerEnableRequest,
    PowerDisableRequest,
    PowerReadRequest,
    PowerReadResponse,
    PowerMeasureRequest,
    PowerMeasureResponse,
    PowerResponse,
    PowerStreamRequest,
    PowerStreamResponse,
    AltimeterReadResponse,
    AccelReadResponse,
    GetMotionStatusResponse,
    MotionStartRequest,
    MotionStartResponse,
    MotionHomeResponse,
    MotionStopResponse,
    ListProgrammersResponse,
    ListFwFilesResponse,
    UploadFwFileRequest,
    UploadFwFileResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    EraseFlashRequest,
    EraseFlashResponse,
    EnableAppProtectRequest,
    EnableAppProtectResponse,
    UartStreamRequest,
    UartStreamResponse,
    NfcPollRequest,
    NfcPollResponse,
    NfcReadNdefRequest,
    NfcReadNdefResponse,
    HealthCheckResponse,
    GetSnapshotResponse,
)

from src.config import MtibV1ProviderConfig, GPIO_PIN_MAP, FLUIDNC_SERIAL_PORT, FLUIDNC_RESET_PIN
from src.drivers.gpio import Gpio

from src.handlers.adc import AdcHandler
from src.handlers.firmware import FirmwareHandler
from src.handlers.gpio import GpioHandler
from src.handlers.motion import MotionHandler
from src.handlers.power import PowerHandler
from src.handlers.nfc import NfcHandler
from src.handlers.sensors import SensorsHandler
from src.handlers.uart import UartHandler


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
#                           Capabilities list
# -------------------------------------------------
_BASE_CAPABILITIES = ["power", "gpio", "adc", "uart", "flash"]
_MOTION_CAPABILITY = "motion"
_NFC_CAPABILITY = "nfc"
_OBSERVABILITY_CAPABILITY = "observability"


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
            self.logger = logger.from_parent("grpc")

        # Global error list for all components
        self.errors: List[str] = []

        # Objects we manage
        self._gpios: Dict[int, Gpio] = {}

        # TCA9534A GPIO expander (REV 1.2 only)
        self._gpio_expander = None

        # NFC handler (set in _init_handlers, may be None if init fails)
        self._nfc_handlers = None

        # Thread-safe I2C bus (shared by MCP4017, TCA9534A, BME280)
        self._i2c_bus = None

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

        # Create shared I2C bus
        try:
            from src.drivers.i2c_bus import I2CBus
            self._i2c_bus = I2CBus(3)
            self.logger.info("I2C bus initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize I2C bus: {e}")
            raise Exception(f"I2C bus init failed: {e}")

        if err := self._init_hw_extensions():
            self.logger.error(f"Failed to initialize hardware extensions: {err}")
            # Non-fatal: REV 1.2 features just won't be available

        if err := self._init_handlers():
            self.logger.error(f"Failed to initialize the handlers: {err}")
            raise Exception(err)

        if err := self._init_metrics():
            self.logger.error(f"Failed to initialize the metrics: {err}")
            raise Exception(err)

        self.logger.info("MtibV1Provider initialized OK in %s ms", (time.time() - start_time) * 1000)

    def _config_gpio(self) -> Optional[str]:
        """Configure the GPIOs."""
        if self.config.HARDWARE_VERSION not in ("REV1.1", "REV1.2"):
            return f"Unsupported hardware version: {self.config.HARDWARE_VERSION}"

        # Initialize all GPIOs as INPUTs by default
        for logical_num, pin in GPIO_PIN_MAP.items():
            # Initialize as INPUT with initial value INACTIVE (0)
            gpio = Gpio(consumer=f"mtib-gpio-{logical_num}", pin=pin, direction=Direction.INPUT)
            if err := gpio.init():
                return f"Failed to initialize GPIO {logical_num} ({pin}): {err}"
            self._gpios[logical_num] = gpio

        self.logger.debug("All GPIOs configured successfully")
        return None

    def _init_hw_extensions(self) -> Optional[str]:
        """Initialize REV 1.2 hardware extensions (TCA9534A GPIO expander)."""
        if self.config.HARDWARE_VERSION != "REV1.2":
            self.logger.info("Hardware version is not REV1.2, skipping TCA9534A init")
            return None

        try:
            from src.drivers.tca9534a import TCA9534A
            self._gpio_expander = TCA9534A(self._i2c_bus)
            self.logger.info("TCA9534A GPIO expander initialized (REV 1.2)")
            return None
        except ImportError:
            self.logger.warning("TCA9534A driver not available, REV 1.2 features disabled")
            return None
        except Exception as e:
            self.logger.warning(f"TCA9534A init failed: {e}. REV 1.2 features disabled.")
            self._gpio_expander = None
            return None

    def _init_handlers(self) -> Optional[str]:
        """Initialize the servicer function handlers."""
        # Create I2C-based drivers with shared bus
        from src.drivers.mcp4017 import MCP4017
        from src.drivers.bme280 import BME280

        mcp4017 = MCP4017(i2c_bus=self._i2c_bus, logger=self.logger)

        # Try BME280 at common addresses
        bme280 = None
        for address in [0x77, 0x76]:
            try:
                candidate = BME280(i2c_bus=self._i2c_bus, address=address, logger=self.logger)
                if candidate.initialize():
                    bme280 = candidate
                    self.logger.info(f"BME280 initialized at address 0x{address:02x}")
                    break
            except Exception as e:
                self.logger.debug(f"BME280 at 0x{address:02x} not available: {e}")
        if bme280 is None:
            self.logger.warning("BME280 sensor not found on I2C bus")

        self._gpio_handlers = GpioHandler(self._gpios, self.logger)
        self._adc_handlers = AdcHandler(self.logger)
        self._power_handlers = PowerHandler(self.logger, mcp4017)
        self._firmware_handlers = FirmwareHandler(self.logger)
        self._sensors_handlers = SensorsHandler(self.logger, bme280)
        self._uart_handlers = UartHandler(self.logger)
        self._nfc_handlers = NfcHandler(self.logger)

        # Pass TCA9534A to handlers that need it (REV 1.2 features)
        if self._gpio_expander is not None:
            self._firmware_handlers.set_gpio_expander(self._gpio_expander)

        # Initialize motion handler
        if self.config.MOTION_ENABLED:
            self._motion_handlers = MotionHandler(
                self.logger, self.config.ASSETS_DIR, FLUIDNC_SERIAL_PORT, FLUIDNC_RESET_PIN
            )
            # Pass TCA9534A for VMM_EN motor power switch (REV 1.2)
            if self._gpio_expander is not None:
                self._motion_handlers.set_gpio_expander(self._gpio_expander)

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
                broker_host = broker_url[8:]
                if ":" in broker_host:
                    host, port = broker_host.split(":", 1)
                    port = int(port)
                else:
                    host = broker_host
                    port = 8883
                self._metrics_client.tls_set()
            elif broker_url.startswith("mqtt://"):
                broker_host = broker_url[7:]
                if ":" in broker_host:
                    host, port = broker_host.split(":", 1)
                    port = int(port)
                else:
                    host = broker_host
                    port = 1883
            else:
                host = broker_url
                port = 1883

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
        if rc == 0:
            self.logger.info("Connected to MQTT broker successfully")
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnection: {rc}")
        else:
            self.logger.info("Disconnected from MQTT broker")

    def _on_mqtt_publish(self, client, userdata, mid):
        pass

    def _metrics_worker(self):
        """Worker thread that publishes metrics at 10Hz."""
        self.logger.info("Metrics worker thread started")

        while self._metrics_running:
            try:
                self._publish_adc_metrics()
                self._publish_gpio_metrics()
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in metrics worker: {e}")
                time.sleep(1)

        self.logger.info("Metrics worker thread stopped")

    def _publish_adc_metrics(self):
        if not self._metrics_client or not self._adc_handlers:
            return
        try:
            for channel in range(8):
                err, raw_value = self._adc_handlers._read_raw(channel)
                if not err:
                    voltage = self._adc_handlers._calculate_real_voltage(raw_value, channel)
                    topic = f"{self._hostname}/metrics/adc/{channel}"
                    result = self._metrics_client.publish(topic, voltage, qos=0)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        self.logger.warning(f"Failed to publish ADC metric for channel {channel}: {result.rc}")
        except Exception as e:
            self.logger.error(f"Error publishing ADC metrics: {e}")

    def _publish_gpio_metrics(self):
        if not self._metrics_client or not self._gpios:
            return
        try:
            for gpio_num, gpio in self._gpios.items():
                try:
                    err, state = gpio.read()
                    if err:
                        continue
                    topic = f"{self._hostname}/metrics/gpio/{gpio_num}"
                    result = self._metrics_client.publish(topic, state, qos=0)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        self.logger.warning(f"Failed to publish GPIO metric for GPIO {gpio_num}: {result.rc}")
                except Exception as e:
                    self.logger.warning(f"Failed to read GPIO {gpio_num}: {e}")
        except Exception as e:
            self.logger.error(f"Error publishing GPIO metrics: {e}")

    def stop_metrics(self):
        if self._metrics_running:
            self.logger.info("Stopping metrics client...")
            self._metrics_running = False
            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=5)
            if self._metrics_client:
                self._metrics_client.disconnect()
                self.logger.info("Metrics client stopped")

    def __del__(self):
        self.stop_metrics()
        if self._i2c_bus is not None:
            try:
                self._i2c_bus.close()
            except Exception:
                pass

    # -------------------------------------------------
    #                          Capabilities helper
    # -------------------------------------------------
    def _get_capabilities(self) -> List[str]:
        caps = list(_BASE_CAPABILITIES)
        if self.config.MOTION_ENABLED:
            caps.append(_MOTION_CAPABILITY)
        if self._nfc_handlers and self._nfc_handlers.is_available:
            caps.append(_NFC_CAPABILITY)
        caps.append(_OBSERVABILITY_CAPABILITY)
        return caps

    # -------------------------------------------------
    #                                     Health Check
    # -------------------------------------------------
    @grpc_method
    def HealthCheck(self, request: Empty, context: grpc.ServicerContext) -> HealthCheckResponse:
        self.logger.info("HealthCheck request received")
        return HealthCheckResponse(
            ready=True,
            errors=self.errors,
            hw_revision=self.config.HARDWARE_VERSION,
            capabilities=self._get_capabilities(),
        )

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

    def GpioWatch(self, request: GpioWatchRequest, context: grpc.ServicerContext) -> Iterator[GpioWatchEvent]:
        self.logger.debug(f"GpioWatch: Request received from {context.peer()}")
        return self._gpio_handlers.watch(request, context)

    # -------------------------------------------------
    #                                               ADC
    # -------------------------------------------------
    @grpc_method
    def AdcRead(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        return self._adc_handlers.read(request, context)

    @grpc_method
    def AdcReadAll(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        return self._adc_handlers.read_all(request, context)

    def AdcStream(self, request: AdcStreamRequest, context: grpc.ServicerContext) -> Iterator[AdcStreamResponse]:
        self.logger.debug(f"AdcStream: Request received from {context.peer()}")
        return self._adc_handlers.stream(request, context)

    # -------------------------------------------------
    #                                            Power
    # -------------------------------------------------
    @grpc_method
    def PowerEnable(self, request: PowerEnableRequest, context: grpc.ServicerContext) -> PowerResponse:
        return self._power_handlers.power_enable(request, context)

    @grpc_method
    def PowerDisable(self, request: PowerDisableRequest, context: grpc.ServicerContext) -> PowerResponse:
        return self._power_handlers.power_disable(request, context)

    @grpc_method
    def PowerRead(self, request: PowerReadRequest, context: grpc.ServicerContext) -> PowerReadResponse:
        return self._power_handlers.power_read(request, context)

    @grpc_method
    def PowerMeasure(self, request: PowerMeasureRequest, context: grpc.ServicerContext) -> PowerMeasureResponse:
        return self._power_handlers.power_measure(request, context)

    def PowerStream(self, request: PowerStreamRequest, context: grpc.ServicerContext) -> Iterator[PowerStreamResponse]:
        self.logger.debug(f"PowerStream: Request received from {context.peer()}")
        return self._power_handlers.power_stream(request, context)

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

    def MotionStart(self, request: MotionStartRequest, context: grpc.ServicerContext) -> MotionStartResponse:
        self.logger.debug(f"MotionStart: Request received from {context.peer()}")
        if not self.config.MOTION_ENABLED:
            yield MotionStartResponse(success=False, message="Motion is not enabled")
            return
        yield from self._motion_handlers.start(request, context)

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

    # -------------------------------------------------
    #                                            NFC
    # -------------------------------------------------
    @grpc_method
    def NfcPoll(self, request: NfcPollRequest, context: grpc.ServicerContext) -> NfcPollResponse:
        if self._nfc_handlers is None:
            return NfcPollResponse(success=False, message="NFC handler not initialized", tag_present=False)
        return self._nfc_handlers.poll(request, context)

    @grpc_method
    def NfcReadNdef(self, request: NfcReadNdefRequest, context: grpc.ServicerContext) -> NfcReadNdefResponse:
        if self._nfc_handlers is None:
            return NfcReadNdefResponse(success=False, message="NFC handler not initialized")
        return self._nfc_handlers.read_ndef(request, context)

    # -------------------------------------------------
    #                                   Observability
    # -------------------------------------------------
    @grpc_method
    def GetSnapshot(self, request: Empty, context: grpc.ServicerContext) -> GetSnapshotResponse:
        """Return a one-shot system state snapshot (V2 RPC)."""
        self.logger.info("GetSnapshot request received")
        try:
            import time as _time
            timestamp_ms = int(_time.time() * 1000)

            power_data = self._power_handlers.get_snapshot_data()
            gpio_data = self._gpio_handlers.get_snapshot_data()
            adc_data = self._adc_handlers.get_snapshot_data()

            return GetSnapshotResponse(
                success=True,
                timestamp_ms=timestamp_ms,
                hw_revision=self.config.HARDWARE_VERSION,
                power=power_data,
                gpio=gpio_data,
                adc=adc_data,
            )
        except Exception as e:
            self.logger.error(f"GetSnapshot error: {e}")
            return GetSnapshotResponse(success=False, message=str(e))
