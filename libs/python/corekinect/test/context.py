"""Unified test context for Stage 4 product validation.

Composes MTIB client, CloudClient, fixture controller, UartDemuxer,
and PowerProfiler into a single object passed to every test via
pytest fixture.

The fixture parameter is duck-typed — any object with the standard
fixture interface (power_on, power_off, press_button, has_capability,
etc.) works. Product test apps inject their own fixture implementation
via from_env(fixture_factory=...).
"""

import os
import threading
import time
from typing import Any, Callable, Optional, Tuple

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.utils import Logger

from .artifact_uploader import ArtifactUploader
from .artifact_writer import ArtifactWriter
from .cloud_client import CloudClient
from .firmware import FirmwareAssetManager
from .acceleration_profiler import AccelerationProfiler
from .power_profiler import PowerProfiler
from .telemetry import TelemetryStreamer
from .uart_demuxer import UartDemuxer

log = Logger(log_name="test_context")


class TestContext:
    """Unified test context for Stage 4 product validation.

    Composes all test infrastructure components into a single object.
    Created once per session via from_env(), shared across all tests.

    Stage 3 extension: adding ``harness: HarnessTransport`` is a
    single-field addition. No other changes needed.

    Attributes:
        mtib: MTIB V1 gRPC client (hardware control).
        cloud: CoreCloud polling client (message verification).
        fixture: Physical stimulus controller (GPIO/power/motion).
        uart: UART log capture (debug builds only).
        power: Power measurement profiler.
        accel: Accelerometer profiler (optional, started only if hardware supports it).
        firmware: Firmware asset manager (MinIO → MTIB upload/cleanup).
        artifacts: Simple file uploader (legacy).
        artifact_writer: Unified artifact writer with streaming support.
        product: Product context from Concord catalog (deviceTypeId, appIds, etc.).
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        cloud: CloudClient,
        fixture: Any,
        uart: UartDemuxer,
        power: PowerProfiler,
        product=None,
    ):
        self.mtib = mtib
        self.cloud = cloud
        self.fixture = fixture
        self.uart = uart
        self.power = power
        self.product = product
        self.firmware = FirmwareAssetManager(mtib=mtib, auto_cleanup=False)
        self.artifacts = ArtifactUploader()
        self.artifact_writer = ArtifactWriter()

        # Telemetry streamer — wired to UART and power callbacks in connect()
        run_id = os.environ.get("CONCORD_RUN_ID", "")
        api_url = os.environ.get("CONCORD_API_URL", "")
        api_key = os.environ.get("CONCORD_API_KEY", "")

        def _telemetry_storage(object_path: str, content_bytes: bytes) -> None:
            """Write telemetry JSONL to MinIO via ArtifactWriter."""
            self.artifact_writer.write_bytes(object_path, content_bytes)

        self.telemetry = TelemetryStreamer(
            run_id=run_id,
            api_url=api_url,
            api_key=api_key,
            on_flush_storage=_telemetry_storage if run_id else None,
        )

        # Accelerometer profiler — probed and started in connect() if hardware supports it
        self.accel: Optional[AccelerationProfiler] = None

        # Background power polling state — initialized in connect(), checked in disconnect()
        self._power_poll_stop: Optional[threading.Event] = None
        self._power_poll_thread: Optional[threading.Thread] = None

    # ═══════════════════════════════════════════════════════════════════════
    # from_env() and its helper methods
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _load_mtib_config() -> Tuple[str, int]:
        """Parse MTIB host and port from environment variables.

        MTIB_ADDRESS (set by bench scheduler) takes precedence over MTIB_HOST.
        MTIB_ADDRESS can include port as ``host:port``; otherwise MTIB_PORT
        is read separately (default 50053).

        Returns:
            Tuple of (host, port).

        Raises:
            ValueError: If neither MTIB_ADDRESS nor MTIB_HOST is set.
        """
        mtib_addr = os.environ.get("MTIB_ADDRESS") or os.environ.get("MTIB_HOST")
        if not mtib_addr:
            raise ValueError("MTIB_ADDRESS or MTIB_HOST must be set")

        if ":" in mtib_addr:
            host, port_str = mtib_addr.rsplit(":", 1)
            return host, int(port_str)

        return mtib_addr, int(os.environ.get("MTIB_PORT", "50053"))

    @staticmethod
    def _load_product_context(
        product_slug: str,
        api_url: Optional[str],
        api_key: Optional[str],
    ):
        """Load product metadata from the Concord catalog API.

        Attempts an API lookup first. If that fails or credentials are missing,
        builds a default ProductContext from the slug (``product_board``).

        Args:
            product_slug: Product identifier like ``alpha_b0``.
            api_url: Concord API base URL (optional).
            api_key: Concord API key (optional).

        Returns:
            A ProductContext instance (from API or defaults).
        """
        from .runner import ProductContext

        if api_url and api_key:
            try:
                product_ctx = ProductContext.from_api(product_slug, api_url, api_key)
                log.info(
                    "Loaded product context from API: %s (deviceType=%d, deviceVariant=%d)",
                    product_ctx.name,
                    product_ctx.device_type_id,
                    product_ctx.device_variant_id,
                )
                return product_ctx
            except Exception as e:
                log.warning("Failed to load product context from API: %s — using defaults", e)

        parts = product_slug.rsplit("_", 1)
        product_name = parts[0] if len(parts) == 2 else product_slug
        board_name = parts[1] if len(parts) == 2 else ""
        product_ctx = ProductContext.default(product_name, board_name)
        log.info("Using default product context for %s", product_slug)
        return product_ctx

    @classmethod
    def from_env(
        cls,
        fixture_factory: Optional[Callable[[MtibV1Client], Any]] = None,
    ) -> "TestContext":
        """Create TestContext from environment variables.

        Args:
            fixture_factory: Optional callable that takes an MtibV1Client and
                returns a product-specific fixture controller. Product test apps
                inject their own fixture implementation here. If None, fixture
                is set to None (product conftest must provide one).

        Required env vars:
            MTIB_HOST or MTIB_ADDRESS: MTIB server address
            DEVICE_ID: CoreCloud device ID as hex string
            CORECLOUD_DB_ENV: CoreCloud namespace (default: DEV_1_0)

        Returns:
            Configured TestContext instance (not yet connected).
        """
        mtib_host, mtib_port = cls._load_mtib_config()

        device_id_hex = os.environ["DEVICE_ID"]
        db_env = os.environ.get("CORECLOUD_DB_ENV", "DEV_1_0")
        device_id = int(device_id_hex, 16)

        api_url = os.environ.get("CONCORD_API_URL")
        api_key = os.environ.get("CONCORD_API_KEY")

        # Determine product slug
        product_slug = os.environ.get("PRODUCT_SLUG")

        # Load product context and apply its coreCloudEnv override
        product_ctx = None
        if product_slug:
            product_ctx = cls._load_product_context(product_slug, api_url, api_key)
            if product_ctx and product_ctx.core_cloud_env:
                db_env = product_ctx.core_cloud_env

        # Build MTIB client
        config = MtibV1Client.Config(net=NetConfig(addr=mtib_host, port=mtib_port))
        mtib = MtibV1Client(config)

        # Build fixture via product-specific factory or leave None
        fixture = fixture_factory(mtib) if fixture_factory else None

        # Build components
        cloud = CloudClient(device_id=device_id, api_env=db_env)
        uart = UartDemuxer(mtib=mtib)
        power = PowerProfiler(mtib=mtib)

        return cls(
            mtib=mtib,
            cloud=cloud,
            fixture=fixture,
            uart=uart,
            power=power,
            product=product_ctx,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════════════════

    def connect(self) -> None:
        """Connect to the MTIB server and start all background services.

        Performs three steps in order:
        1. Establishes the gRPC connection and verifies MTIB health.
        2. Starts UART capture, wires it to the telemetry streamer,
           and begins telemetry streaming.
        3. Starts background power polling (both DUT and charger channels
           at 2 Hz) and probes the accelerometer profiler.

        Raises:
            ConnectionError: If the MTIB connection or health check fails.
        """
        err = self.mtib.connect()
        if err:
            raise ConnectionError(f"MTIB connection failed: {err}")

        # Verify MTIB is healthy
        ready, errors, err = self.mtib.HealthCheck()
        if err:
            raise ConnectionError(f"MTIB health check failed: {err}")
        if not ready:
            raise ConnectionError(f"MTIB not ready: {errors}")

        log.info("Connected to MTIB, starting UART capture")
        self.uart.start()

        # Wire UART lines to telemetry streamer for live streaming + storage
        self.uart.on_line = self.telemetry.push_uart
        self.telemetry.start()

        # Start background power polling (reads both channels every 500ms)
        self._power_poll_stop = threading.Event()
        self._power_poll_thread = threading.Thread(
            target=self._power_poll_loop, daemon=True, name="power-poll"
        )
        self._power_poll_thread.start()

        # Start accelerometer profiler if hardware supports it
        accel_profiler = AccelerationProfiler(mtib=self.mtib, streamer=self.telemetry)
        if accel_profiler.probe():
            accel_profiler.start()
            self.accel = accel_profiler
        else:
            log.info("Accelerometer not available — profiler disabled")

    def disconnect(self) -> None:
        """Tear down all background services and disconnect from MTIB.

        Stops services in reverse-start order:
        1. Power polling thread (signal + join with 3s timeout).
        2. Accelerometer profiler (if running).
        3. Telemetry streamer (flushes pending data).
        4. UART capture.
        5. Firmware asset cleanup (best-effort).
        6. MTIB gRPC disconnect.
        """
        # Stop power polling
        if self._power_poll_stop is not None:
            self._power_poll_stop.set()
            if self._power_poll_thread and self._power_poll_thread.is_alive():
                self._power_poll_thread.join(timeout=3)

        # Stop accelerometer profiler
        if self.accel:
            self.accel.stop()

        self.telemetry.stop()
        self.uart.stop()
        # Cleanup uploaded firmware files from MTIB server
        try:
            self.firmware.cleanup()
        except Exception as e:
            log.warning("Firmware cleanup error: %s", e)
        err = self.mtib.disconnect()
        if err:
            log.warning("MTIB disconnect error: %s", err)
        log.info("Disconnected from MTIB")

    def _power_poll_loop(self) -> None:
        """Poll DUT and charger power channels at ~2 Hz, pushing readings to telemetry.

        Reads both INA219 channels (DUT ch0 and charger ch1) every 500ms and
        forwards the measurements to the telemetry streamer for live display
        and storage. Runs as a daemon thread; exits when ``_power_poll_stop``
        is set.

        Errors from individual reads are logged at debug level to avoid
        flooding logs during transient power state changes (e.g., power
        cycling between tests).
        """
        from corekinect.mtib_client.v1.client.types import PowerChannel

        while not self._power_poll_stop.wait(0.5):
            try:
                ts = time.time()
                # Read DUT channel (ch0)
                ch0, err0 = self.mtib.PowerRead(channel=PowerChannel.DUT)
                if not err0 and ch0:
                    self.telemetry.push_power(ts, ch0.current_ma, ch0.voltage_v * 1000)

                # Read Charger channel (ch1) — push as separate type for dual-line chart
                ch1, err1 = self.mtib.PowerRead(channel=PowerChannel.CHARGER)
                if not err1 and ch1:
                    self.telemetry.push(
                        "power_chg", {"mA": round(ch1.current_ma, 2), "mV": round(ch1.voltage_v * 1000, 1)},
                    )
            except Exception as exc:
                log.debug("Power poll read error: %s", exc)

    # ═══════════════════════════════════════════════════════════════════════
    # Per-test lifecycle
    # ═══════════════════════════════════════════════════════════════════════

    def setup_test(self, test_name: Optional[str] = None, module: Optional[str] = None) -> None:
        """Per-test setup: mark test start time, clear UART buffer, reset fixture state."""
        self.cloud.mark_test_start()
        self.uart.clear()
        if test_name:
            self.telemetry.set_test(test_name, module=module)
        # Reset transient fixture state (button press, etc.) between tests.
        # Mock, stub, and programmable fixtures track _button_pressed; the
        # real FixtureController does not (it drives GPIO directly).
        if hasattr(self.fixture, '_button_pressed'):
            self.fixture._button_pressed = False

    def teardown_test(self, test_name: str, artifacts_dir: Optional[str] = None) -> None:
        """Per-test teardown: dump UART logs if artifacts_dir provided."""
        if artifacts_dir:
            log_path = os.path.join(artifacts_dir, f"{test_name}_uart.log")
            self.uart.dump_to_file(log_path)
