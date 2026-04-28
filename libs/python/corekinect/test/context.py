"""Unified test context for product validation.

Composes MTIB client, CloudClient, fixture controller, UartDemuxer,
and PowerProfiler into a single object shared across all tests.

    ctx = TestContext.from_env(fixture_factory=AlphaFixture)
    ctx.connect()
    # ... run tests ...
    ctx.disconnect()

The fixture parameter is duck-typed. Product test apps inject their
own fixture via from_env(fixture_factory=...).
"""

import os
import threading
import time
from typing import Any, Callable, Optional, Tuple

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import PowerChannel
from corekinect.utils import Logger

from .artifact_uploader import ArtifactUploader
from .artifact_writer import ArtifactWriter
from .cloud_client import CloudClient
from .firmware import FirmwareAssetManager
from .acceleration_profiler import AccelerationProfiler
from .power_profiler import PowerProfiler
from .env import get_run_id
from .telemetry import TelemetryStreamer
from .runner import ProductContext
from .uart_demuxer import UartDemuxer

log = Logger(log_name="test_context")


class TestContext:
    """Composes all test infrastructure into a single session-scoped object.

    Created once via from_env(), shared across all tests in a session.

    Attributes:
        mtib: MTIB V1 gRPC client.
        cloud: CoreCloud polling client.
        fixture: Physical stimulus controller (duck-typed).
        uart: Dual-target UART capture.
        power: Power measurement profiler.
        accel: Accelerometer profiler (None if hardware doesn't support it).
        firmware: Firmware asset manager (MinIO upload/cleanup).
        artifact_writer: Streaming artifact writer.
        product: Product context from Concord catalog.
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
        run_id = get_run_id()
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
        self._has_joulescope: bool = False

    # ═══════════════════════════════════════════════════════════════════════
    # from_env() and its helper methods
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _load_mtib_config() -> Tuple[str, int]:
        """Parse MTIB host/port from env vars.

        MTIB_ADDRESS takes precedence over MTIB_HOST and can include
        port as ``host:port``. Falls back to MTIB_PORT (default 50053).

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
        """Load product metadata from Concord catalog, falling back to defaults."""
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
            fixture_factory: Takes an MtibV1Client, returns a product-specific
                fixture controller. If None, fixture is set to None.

        Required env vars: MTIB_HOST or MTIB_ADDRESS, DEVICE_ID.
        Returns an unconnected instance -- call connect() next.
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
        """Connect to MTIB and start background services (UART, power polling, telemetry).

        Raises:
            ConnectionError: If the MTIB connection or health check fails.
        """
        err = self.mtib.connect()
        if err:
            raise ConnectionError(f"MTIB connection failed: {err}")

        # Verify MTIB is healthy and check capabilities
        ready, errors, err = self.mtib.HealthCheck()
        if err:
            raise ConnectionError(f"MTIB health check failed: {err}")
        if not ready:
            raise ConnectionError(f"MTIB not ready: {errors}")

        # Check for Joulescope capability
        ext, ext_err = self.mtib.HealthCheckExtended()
        if not ext_err and ext and ext.capabilities:
            self._has_joulescope = "joulescope" in ext.capabilities
            if self._has_joulescope:
                log.info("Joulescope detected — enabling high-resolution power polling")

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
        """Stop all background services and disconnect from MTIB."""
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
        """Poll power channels at ~2 Hz and push to telemetry.

        Reads DUT + Charger always, and Joulescope when available.
        Errors are logged at debug level to avoid flooding during
        power cycling between tests.
        """
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

                # Read Joulescope channel (ch2) when available — nanoamp resolution
                if self._has_joulescope:
                    js, err_js = self.mtib.PowerRead(channel=PowerChannel.JOULESCOPE)
                    if not err_js and js:
                        self.telemetry.push(
                            "power_js",
                            {
                                "uA": round(js.current_ma * 1000, 2),  # mA → µA
                                "mV": round(js.voltage_v * 1000, 1),
                                "nA": round(js.current_na, 0),
                            },
                        )
            except Exception as exc:
                log.debug("Power poll read error: %s", exc)

    # ═══════════════════════════════════════════════════════════════════════
    # Per-test lifecycle
    # ═══════════════════════════════════════════════════════════════════════

    def setup_test(self, test_name: Optional[str] = None, module: Optional[str] = None) -> None:
        """Mark test start, clear UART buffer, reset fixture state."""
        self.cloud.mark_test_start()
        self.uart.clear()
        if test_name:
            self.telemetry.set_test(test_name, module=module)
        # Reset transient fixture state (button press, etc.) between tests
        # for fixtures that track it. Real Fixture subclasses drive GPIO
        # directly and don't carry this attribute.
        if hasattr(self.fixture, '_button_pressed'):
            self.fixture._button_pressed = False

    def teardown_test(self, test_name: str, artifacts_dir: Optional[str] = None) -> None:
        """Dump UART logs to artifacts_dir if provided."""
        if artifacts_dir:
            log_path = os.path.join(artifacts_dir, f"{test_name}_uart.log")
            self.uart.dump_to_file(log_path)
