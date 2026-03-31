"""Unified test context for Stage 4 product validation.

Composes MTIB client, CloudClient, FixtureController, UartDemuxer,
and PowerProfiler into a single object passed to every test via
pytest fixture.
"""

import os
import threading
import time
from typing import Optional

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.utils import Logger

from .artifact_uploader import ArtifactUploader
from .artifact_writer import ArtifactWriter
from .cloud_client import CloudClient
from .firmware import FirmwareAssetManager
from .fixture_controller import FixtureController
from .profiles import FixtureProfile
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
        fixture: FixtureController,
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

    @classmethod
    def from_env(cls) -> "TestContext":
        """Create TestContext from environment variables.

        Required env vars:
            MTIB_HOST or MTIB_ADDRESS: MTIB server address (e.g., 10.4.45.33:50053)
            MTIB_PORT: MTIB server port (default: 50053, can be in MTIB_ADDRESS)
            DEVICE_ID: CoreCloud device ID as hex string (e.g., 70B3D584C01E1FCC)
            CORECLOUD_DB_ENV: CoreCloud namespace (default: DEV_1_0)

        Profile loading (one of the following):
            API mode (preferred):
                BENCH_ID: TestBench ID or station_id
                CONCORD_API_URL: Base URL of Concord API
                CONCORD_API_KEY: API key for authentication

            File mode (fallback):
                FIXTURE_PROFILE_PATH: Path to fixture profile JSON

        MTIB_ADDRESS takes precedence over MTIB_HOST (bench scheduler sets MTIB_ADDRESS).
        MTIB_ADDRESS can include port (e.g., "10.4.45.33:50053").

        Returns:
            Configured TestContext instance (not yet connected).
        """
        # MTIB_ADDRESS from bench scheduler takes precedence over MTIB_HOST
        mtib_addr = os.environ.get("MTIB_ADDRESS") or os.environ.get("MTIB_HOST")
        if not mtib_addr:
            raise ValueError("MTIB_ADDRESS or MTIB_HOST must be set")

        # Parse host:port if present in address
        if ":" in mtib_addr:
            mtib_host, port_str = mtib_addr.rsplit(":", 1)
            mtib_port = int(port_str)
        else:
            mtib_host = mtib_addr
            mtib_port = int(os.environ.get("MTIB_PORT", "50053"))

        device_id_hex = os.environ["DEVICE_ID"]
        db_env = os.environ.get("CORECLOUD_DB_ENV", "DEV_1_0")

        # Parse device ID (hex string -> int)
        device_id = int(device_id_hex, 16)

        # Load fixture profile — prefer API if configured, fall back to file
        bench_id = os.environ.get("BENCH_ID")
        api_url = os.environ.get("CONCORD_API_URL")
        api_key = os.environ.get("CONCORD_API_KEY")

        if bench_id and api_url and api_key:
            log.info(f"Loading fixture profile from API: {api_url}/benches/{bench_id}")
            profile = FixtureProfile.from_api(bench_id, api_url, api_key)
        else:
            # Fallback to file-based loading
            profile_path = os.environ.get("FIXTURE_PROFILE_PATH")
            if not profile_path:
                raise ValueError(
                    "Either BENCH_ID+CONCORD_API_URL+CONCORD_API_KEY or "
                    "FIXTURE_PROFILE_PATH must be set"
                )
            log.info(f"Loading fixture profile from file: {profile_path}")
            profile = FixtureProfile.from_json(profile_path)

        # Load product context from API if available
        product_ctx = None
        product_slug = os.environ.get("PRODUCT_SLUG")
        if not product_slug and profile:
            # Derive slug from fixture profile product+board (e.g., "alpha" + "b0" -> "alpha_b0")
            product_slug = f"{profile.product}_{profile.board}"

        if product_slug and api_url and api_key:
            try:
                from .runner import ProductContext
                product_ctx = ProductContext.from_api(product_slug, api_url, api_key)
                log.info("Loaded product context from API: %s (deviceType=%d, deviceVariant=%d)",
                         product_ctx.name, product_ctx.device_type_id, product_ctx.device_variant_id)
                # Use product's coreCloudEnv if available
                if product_ctx.core_cloud_env:
                    db_env = product_ctx.core_cloud_env
            except Exception as e:
                log.warning("Failed to load product context from API: %s — using defaults", e)

        if not product_ctx and product_slug:
            from .runner import ProductContext
            parts = product_slug.rsplit("_", 1)
            product_name = parts[0] if len(parts) == 2 else product_slug
            board_name = parts[1] if len(parts) == 2 else ""
            product_ctx = ProductContext.default(product_name, board_name)
            log.info("Using default product context for %s", product_slug)

        # Build MTIB client
        config = MtibV1Client.Config(net=NetConfig(addr=mtib_host, port=mtib_port))
        mtib = MtibV1Client(config)

        # Build components
        cloud = CloudClient(device_id=device_id, api_env=db_env)
        fixture = FixtureController(mtib=mtib, profile=profile)
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

    def connect(self) -> None:
        """Connect to MTIB server, start UART capture and telemetry streaming."""
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
        """Stop power polling, telemetry, UART capture, cleanup firmware assets, and disconnect from MTIB."""
        # Stop power polling
        if hasattr(self, '_power_poll_stop'):
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
        """Background thread: read power from both channels every 500ms."""
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

    def setup_test(self, test_name: Optional[str] = None, module: Optional[str] = None) -> None:
        """Per-test setup: mark test start time, clear UART buffer, reset fixture state."""
        self.cloud.mark_test_start()
        self.uart.clear()
        if test_name:
            self.telemetry.set_test(test_name, module=module)
        # Reset transient mock fixture state (button press, etc.) between tests.
        if hasattr(self.fixture, '_button_pressed'):
            self.fixture._button_pressed = False

    def teardown_test(self, test_name: str, artifacts_dir: Optional[str] = None) -> None:
        """Per-test teardown: dump UART logs if artifacts_dir provided."""
        if artifacts_dir:
            log_path = os.path.join(artifacts_dir, f"{test_name}_uart.log")
            self.uart.dump_to_file(log_path)
