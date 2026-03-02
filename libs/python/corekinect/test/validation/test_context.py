"""Unified test context for Stage 4 product validation.

Composes MTIB client, CloudClient, FixtureController, UartDemuxer,
and PowerProfiler into a single object passed to every test via
pytest fixture.
"""

import logging
import os
from typing import Optional

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig

from .cloud_client import CloudClient
from .fixture_controller import FixtureController, FixtureProfile
from .power_profiler import PowerProfiler
from .uart_demuxer import UartDemuxer

log = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        cloud: CloudClient,
        fixture: FixtureController,
        uart: UartDemuxer,
        power: PowerProfiler,
    ):
        self.mtib = mtib
        self.cloud = cloud
        self.fixture = fixture
        self.uart = uart
        self.power = power

    @classmethod
    def from_env(cls) -> "TestContext":
        """Create TestContext from environment variables.

        Required env vars:
            MTIB_HOST: MTIB server address (e.g., 10.4.45.33)
            MTIB_PORT: MTIB server port (default: 50053)
            DEVICE_ID: CoreCloud device ID as hex string (e.g., 70B3D584C01E1FCC)
            CORECLOUD_DB_ENV: CoreCloud namespace (default: DEV_1_0)
            FIXTURE_PROFILE_PATH: Path to fixture profile JSON

        Returns:
            Configured TestContext instance (not yet connected).
        """
        mtib_host = os.environ["MTIB_HOST"]
        mtib_port = int(os.environ.get("MTIB_PORT", "50053"))
        device_id_hex = os.environ["DEVICE_ID"]
        db_env = os.environ.get("CORECLOUD_DB_ENV", "DEV_1_0")
        profile_path = os.environ["FIXTURE_PROFILE_PATH"]

        # Parse device ID (hex string → int)
        device_id = int(device_id_hex, 16)

        # Build MTIB client
        config = MtibV1Client.Config(net=NetConfig(addr=mtib_host, port=mtib_port))
        mtib = MtibV1Client(config)

        # Build components
        cloud = CloudClient(device_id=device_id, db_env=db_env)
        profile = FixtureProfile.from_json(profile_path)
        fixture = FixtureController(mtib=mtib, profile=profile)
        uart = UartDemuxer(mtib=mtib)
        power = PowerProfiler(mtib=mtib)

        return cls(
            mtib=mtib,
            cloud=cloud,
            fixture=fixture,
            uart=uart,
            power=power,
        )

    def connect(self) -> None:
        """Connect to MTIB server and start UART capture."""
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

    def disconnect(self) -> None:
        """Stop UART capture and disconnect from MTIB."""
        self.uart.stop()
        err = self.mtib.disconnect()
        if err:
            log.warning("MTIB disconnect error: %s", err)
        log.info("Disconnected from MTIB")

    def setup_test(self) -> None:
        """Per-test setup: mark test start time, clear UART buffer."""
        self.cloud.mark_test_start()
        self.uart.clear()

    def teardown_test(self, test_name: str, artifacts_dir: Optional[str] = None) -> None:
        """Per-test teardown: dump UART logs if artifacts_dir provided."""
        if artifacts_dir:
            log_path = os.path.join(artifacts_dir, f"{test_name}_uart.log")
            self.uart.dump_to_file(log_path)
