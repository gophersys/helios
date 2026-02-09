"""MTIB V2 gRPC service provider.

Wires all 71 RPCs to their respective handler implementations.
"""

import functools
import json
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional

import grpc
import paho.mqtt.client as mqtt

from corekinect.utils import Logger
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Servicer
from src.hardware import HardwareContext
from src.shared.types import *

# Handler imports
from .handlers.ble import BleHandler
from .handlers.can import CanHandler
from .handlers.debug import DebugHandler
from .handlers.files import FilesHandler
from .handlers.flash import FlashHandler
from .handlers.gpio import GpioHandler
from .handlers.i2c import I2cHandler
from .handlers.logic import LogicHandler
from .handlers.observability import ObservabilityHandler
from .handlers.power import PowerHandler
from .handlers.rtt import RttHandler
from .handlers.spi import SpiHandler
from .handlers.swo import SwoHandler
from .handlers.system import SystemHandler
from .handlers.target import ProbeManager, TargetHandler
from .handlers.uart import UartHandler
from .handlers.zephyr import ZephyrHandler
from .observability import ObservabilityEngine

LOG_MODULE = "grpc"


# -------------------------------------------------
#                             gRPC Method Decorator
# -------------------------------------------------
def grpc_method(func: Callable) -> Callable:
    """Decorator to log and time gRPC method calls."""

    @functools.wraps(func)
    def method(self, request, context, *args, **kwargs):
        method_name = func.__name__
        self.logger.debug(f"{method_name}: Request received from {context.peer()}")
        start_time = time.time()

        try:
            response = func(self, request, context, *args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"{method_name}: OK in {elapsed_ms:.2f}ms for {context.peer()}")
            return response
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.error(f"{method_name}: Exception in {elapsed_ms:.2f}ms for {context.peer()}: {e}")
            raise

    return method


# -------------------------------------------------
#                                            Config
# -------------------------------------------------
@dataclass
class MtibV2ProviderConfig:
    """Configuration for the MTIB V2 gRPC provider."""
    HARDWARE: HardwareContext
    ASSETS_DIR: str
    METRICS_ENABLED: bool
    METRICS_BROKER_URL: str
    MOTION_ENABLED: bool


# -------------------------------------------------
#                                 MTIB V2 Provider
# -------------------------------------------------
class MtibV2Provider(MtibV2Servicer):
    """MTIB V2 gRPC service provider.

    Implements all 71 RPCs defined in mtib_v2.proto by delegating to
    domain-specific handler classes.
    """

    def __init__(self, config: MtibV2ProviderConfig, logger: Logger = None):
        self._start_time = time.time()
        self.config = config
        self.hardware = config.HARDWARE

        if logger is None:
            raise ValueError("Logger is required")
        self.logger = logger.from_parent(LOG_MODULE)

        self.errors: List[str] = []
        self._hostname = socket.gethostname()

        # Metrics client
        self._metrics_client: Optional[mqtt.Client] = None
        self._metrics_thread: Optional[threading.Thread] = None
        self._metrics_running = False

        self.logger.info(f"Hostname: {self._hostname}")
        self.logger.info(f"Hardware revision: {self.hardware.revision}")

        # Initialize all handlers
        self._init_handlers()

        # Initialize metrics
        self._init_metrics()

        elapsed = (time.time() - self._start_time) * 1000
        self.logger.info(f"MtibV2Provider initialized OK in {elapsed:.0f}ms")

    def _init_handlers(self) -> None:
        """Initialize all handler instances."""
        # Initialize observability engine first so trackers can be passed to handlers
        self._observability_engine = ObservabilityEngine(self.logger, self.hardware)

        self._system = SystemHandler(self.logger, self.hardware, self._start_time)
        self._target = TargetHandler(self.logger, self.hardware)
        self._debug = DebugHandler(self.logger, self.hardware)
        self._flash = FlashHandler(self.logger, self.hardware, self.config.ASSETS_DIR)
        self._rtt = RttHandler(self.logger, self.hardware)
        self._swo = SwoHandler(self.logger, self.hardware)
        self._uart = UartHandler(self.logger, self.hardware, uart_observer=self._observability_engine.uart_observer)
        self._power = PowerHandler(self.logger, self.hardware, power_monitor=self._observability_engine.power_monitor)
        self._logic = LogicHandler(self.logger, self.hardware)
        self._gpio = GpioHandler(self.logger, self.hardware, gpio_tracker=self._observability_engine.gpio_tracker)
        self._i2c = I2cHandler(self.logger, self.hardware)
        self._spi = SpiHandler(self.logger, self.hardware)
        self._can = CanHandler(self.logger, self.hardware)
        self._ble = BleHandler(self.logger, self.hardware)
        self._zephyr = ZephyrHandler(self.logger, self.hardware)
        self._files = FilesHandler(self.logger, self.hardware, self.config.ASSETS_DIR)
        self._observability = ObservabilityHandler(self.logger, self._observability_engine)

        # ProbeManager — auto-discovers J-Link probes and maps them to targets
        self._probe_manager = ProbeManager(self.logger, self.hardware)
        err = self._probe_manager.discover()
        if err:
            self.logger.warning(f"ProbeManager discovery failed: {err}")
        else:
            self.logger.info(
                f"ProbeManager: mode={self._probe_manager.mode}, "
                f"probes={self._probe_manager.probe_count}"
            )

        # Cross-handler wiring
        self._flash.set_debug_handler(self._debug)
        self._flash.set_probe_manager(self._probe_manager)
        self._debug.set_probe_manager(self._probe_manager)
        self._target.set_probe_manager(self._probe_manager)

    # =========================================================================
    # Metrics (MQTT)
    # =========================================================================
    def _init_metrics(self) -> None:
        """Initialize MQTT metrics client."""
        if not self.config.METRICS_ENABLED:
            return

        try:
            self._metrics_client = mqtt.Client()
            self._metrics_client.on_connect = self._on_mqtt_connect
            self._metrics_client.on_disconnect = self._on_mqtt_disconnect

            broker_url = self.config.METRICS_BROKER_URL
            if broker_url.startswith("mqtts://"):
                host_part = broker_url[8:]
                if ":" in host_part:
                    host, port = host_part.split(":", 1)
                    port = int(port)
                else:
                    host, port = host_part, 8883
                self._metrics_client.tls_set()
            elif broker_url.startswith("mqtt://"):
                host_part = broker_url[7:]
                if ":" in host_part:
                    host, port = host_part.split(":", 1)
                    port = int(port)
                else:
                    host, port = host_part, 1883
            else:
                host, port = broker_url, 1883

            self._metrics_client.connect(host, port, 60)
            self._metrics_running = True
            self._metrics_thread = threading.Thread(target=self._metrics_worker, daemon=True)
            self._metrics_thread.start()
            self.logger.info("Metrics client initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize metrics: {e}")

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"MQTT connection failed: {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnect: {rc}")

    def _metrics_worker(self):
        """Worker thread for publishing metrics at 10Hz."""
        while self._metrics_running:
            try:
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Metrics error: {e}")
                time.sleep(1)

    def start_observability(self):
        """Start the observability engine background threads."""
        self._observability_engine.start()

    def stop_observability(self):
        """Stop the observability engine background threads."""
        self._observability_engine.stop()

    def stop_metrics(self):
        """Stop the metrics client."""
        if self._metrics_running:
            self._metrics_running = False
            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=5)
            if self._metrics_client:
                self._metrics_client.disconnect()

    def __del__(self):
        self.stop_metrics()

    # =========================================================================
    # Health & System (2 RPCs)
    # =========================================================================
    @grpc_method
    def HealthCheck(self, request, context):
        return self._system.health_check(request, context)

    @grpc_method
    def SystemInfo(self, request, context):
        return self._system.system_info(request, context)

    # =========================================================================
    # Target Management (2 RPCs)
    # =========================================================================
    @grpc_method
    def ListTargets(self, request, context):
        return self._target.list_targets(request, context)

    @grpc_method
    def ListProbes(self, request, context):
        return self._target.list_probes(request, context)

    # =========================================================================
    # Debug Probe (15 RPCs)
    # =========================================================================
    @grpc_method
    def DebugConnect(self, request, context):
        return self._debug.connect(request, context)

    @grpc_method
    def DebugDisconnect(self, request, context):
        return self._debug.disconnect(request, context)

    @grpc_method
    def DebugStatus(self, request, context):
        return self._debug.status(request, context)

    @grpc_method
    def DebugHalt(self, request, context):
        return self._debug.halt(request, context)

    @grpc_method
    def DebugResume(self, request, context):
        return self._debug.resume(request, context)

    @grpc_method
    def DebugStep(self, request, context):
        return self._debug.step(request, context)

    @grpc_method
    def DebugReset(self, request, context):
        return self._debug.reset(request, context)

    @grpc_method
    def ReadRegisters(self, request, context):
        return self._debug.read_registers(request, context)

    @grpc_method
    def WriteRegister(self, request, context):
        return self._debug.write_register(request, context)

    @grpc_method
    def ReadMemory(self, request, context):
        return self._debug.read_memory(request, context)

    @grpc_method
    def WriteMemory(self, request, context):
        return self._debug.write_memory(request, context)

    @grpc_method
    def SetBreakpoint(self, request, context):
        return self._debug.set_breakpoint(request, context)

    @grpc_method
    def ClearBreakpoint(self, request, context):
        return self._debug.clear_breakpoint(request, context)

    @grpc_method
    def SetWatchpoint(self, request, context):
        return self._debug.set_watchpoint(request, context)

    @grpc_method
    def Backtrace(self, request, context):
        return self._debug.backtrace(request, context)

    # =========================================================================
    # Flash Programming (4 RPCs)
    # =========================================================================
    @grpc_method
    def FlashInfo(self, request, context):
        return self._flash.info(request, context)

    @grpc_method
    def FlashErase(self, request, context):
        return self._flash.erase(request, context)

    @grpc_method
    def FlashWrite(self, request, context):
        return self._flash.write(request, context)

    @grpc_method
    def FlashProgram(self, request, context):
        return self._flash.program(request, context)

    # =========================================================================
    # RTT (3 RPCs)
    # =========================================================================
    @grpc_method
    def RttStart(self, request, context):
        return self._rtt.start(request, context)

    @grpc_method
    def RttStop(self, request, context):
        return self._rtt.stop(request, context)

    def RttStream(self, request_iterator, context):
        """Bidirectional streaming - no @grpc_method decorator for streaming."""
        return self._rtt.stream(request_iterator, context)

    # =========================================================================
    # SWO (3 RPCs)
    # =========================================================================
    @grpc_method
    def SwoStart(self, request, context):
        return self._swo.start(request, context)

    @grpc_method
    def SwoStop(self, request, context):
        return self._swo.stop(request, context)

    def SwoStream(self, request, context):
        """Server streaming - no decorator."""
        return self._swo.stream(request, context)

    # =========================================================================
    # UART (3 RPCs)
    # =========================================================================
    @grpc_method
    def UartOpen(self, request, context):
        return self._uart.open(request, context)

    @grpc_method
    def UartClose(self, request, context):
        return self._uart.close(request, context)

    def UartStream(self, request_iterator, context):
        """Bidirectional streaming - no decorator."""
        return self._uart.stream(request_iterator, context)

    # =========================================================================
    # Power (5 RPCs)
    # =========================================================================
    @grpc_method
    def PowerEnable(self, request, context):
        return self._power.enable(request, context)

    @grpc_method
    def PowerDisable(self, request, context):
        return self._power.disable(request, context)

    @grpc_method
    def PowerStatus(self, request, context):
        return self._power.status(request, context)

    def PowerStream(self, request, context):
        """Server streaming - no decorator."""
        return self._power.stream(request, context)

    @grpc_method
    def PowerMeasure(self, request, context):
        return self._power.measure(request, context)

    # =========================================================================
    # Logic Analyzer (5 RPCs)
    # =========================================================================
    @grpc_method
    def LogicCaptureStart(self, request, context):
        return self._logic.capture_start(request, context)

    @grpc_method
    def LogicCaptureStatus(self, request, context):
        return self._logic.capture_status(request, context)

    @grpc_method
    def LogicCaptureStop(self, request, context):
        return self._logic.capture_stop(request, context)

    @grpc_method
    def AddDecoder(self, request, context):
        return self._logic.add_decoder(request, context)

    @grpc_method
    def GetDecodedData(self, request, context):
        return self._logic.get_decoded_data(request, context)

    # =========================================================================
    # GPIO (4 RPCs)
    # =========================================================================
    @grpc_method
    def GpioConfig(self, request, context):
        return self._gpio.config(request, context)

    @grpc_method
    def GpioWrite(self, request, context):
        return self._gpio.write(request, context)

    @grpc_method
    def GpioRead(self, request, context):
        return self._gpio.read(request, context)

    def GpioWatch(self, request, context):
        """Server streaming - no decorator."""
        return self._gpio.watch(request, context)

    # =========================================================================
    # I2C Master (3 RPCs)
    # =========================================================================
    @grpc_method
    def I2cConfigure(self, request, context):
        return self._i2c.configure(request, context)

    @grpc_method
    def I2cTransfer(self, request, context):
        return self._i2c.transfer(request, context)

    @grpc_method
    def I2cScan(self, request, context):
        return self._i2c.scan(request, context)

    # =========================================================================
    # SPI Master (2 RPCs)
    # =========================================================================
    @grpc_method
    def SpiConfigure(self, request, context):
        return self._spi.configure(request, context)

    @grpc_method
    def SpiTransfer(self, request, context):
        return self._spi.transfer(request, context)

    # =========================================================================
    # CAN Bus (4 RPCs)
    # =========================================================================
    @grpc_method
    def CanConfigure(self, request, context):
        return self._can.configure(request, context)

    @grpc_method
    def CanSend(self, request, context):
        return self._can.send(request, context)

    @grpc_method
    def CanSetFilter(self, request, context):
        return self._can.set_filter(request, context)

    def CanReceive(self, request, context):
        """Server streaming - no decorator."""
        return self._can.receive(request, context)

    # =========================================================================
    # BLE (7 RPCs)
    # =========================================================================
    @grpc_method
    def BleScan(self, request, context):
        return self._ble.scan(request, context)

    @grpc_method
    def BleConnect(self, request, context):
        return self._ble.connect(request, context)

    @grpc_method
    def BleDisconnect(self, request, context):
        return self._ble.disconnect(request, context)

    @grpc_method
    def BleDiscoverServices(self, request, context):
        return self._ble.discover_services(request, context)

    @grpc_method
    def BleRead(self, request, context):
        return self._ble.read(request, context)

    @grpc_method
    def BleWrite(self, request, context):
        return self._ble.write(request, context)

    def BleNotifications(self, request, context):
        """Server streaming - no decorator."""
        return self._ble.notifications(request, context)

    # =========================================================================
    # Zephyr (5 RPCs)
    # =========================================================================
    @grpc_method
    def ZephyrShell(self, request, context):
        return self._zephyr.shell(request, context)

    def ZephyrLogStream(self, request, context):
        """Server streaming - no decorator."""
        return self._zephyr.log_stream(request, context)

    @grpc_method
    def ZephyrDevicetree(self, request, context):
        return self._zephyr.devicetree(request, context)

    @grpc_method
    def ZephyrThreads(self, request, context):
        return self._zephyr.threads(request, context)

    @grpc_method
    def TwisterRun(self, request, context):
        return self._zephyr.twister_run(request, context)

    # =========================================================================
    # File Management (4 RPCs)
    # =========================================================================
    @grpc_method
    def ListFiles(self, request, context):
        return self._files.list_files(request, context)

    def UploadFile(self, request_iterator, context):
        """Client streaming - no decorator."""
        return self._files.upload(request_iterator, context)

    def DownloadFile(self, request, context):
        """Server streaming - no decorator."""
        return self._files.download(request, context)

    @grpc_method
    def DeleteFile(self, request, context):
        return self._files.delete(request, context)

    # =========================================================================
    # Observability (2 RPCs)
    # =========================================================================
    @grpc_method
    def GetObservabilitySnapshot(self, request, context):
        return self._observability.get_snapshot(request, context)

    def ObservabilityStream(self, request, context):
        """Server streaming - no decorator."""
        return self._observability.stream(request, context)
