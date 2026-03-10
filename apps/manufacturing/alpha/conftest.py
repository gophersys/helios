"""pytest fixtures for Alpha manufacturing tests.

Provides multi-slot test context for 4-panel fixtures.
Each slot has its own MTIB connection, UART capture, and power profiling.

Required environment variables:
    FIXTURE_CONFIG_PATH: Path to fixture config JSON (ThetaFixtureConfig)
    MTIB_HOSTS: Comma-separated MTIB addresses (e.g., "10.4.45.33:50053,10.4.45.34:50053")

Optional:
    MOCK_MODE: Set to "1" for offline testing with mock hardware
    ARTIFACTS_DIR: Directory for test artifacts (UART logs, power traces)
    CONCORD_RUN_ID: Validation run ID (activates reporter plugin)
    CONCORD_API_URL: Concord HTTP API base URL
    CONCORD_API_KEY: API key for reporter auth

Log streaming:
    When CONCORD_RUN_ID is set, all stdout/stderr and UART logs are streamed
    to the Concord backend via the reporter plugin. The frontend displays
    live logs via WebSocket subscription.
"""

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# Load root .env before anything else
try:
    from dotenv import load_dotenv
    _root_env = Path(__file__).resolve().parents[3] / ".env"
    if _root_env.exists():
        load_dotenv(_root_env, override=False)
except (ImportError, IndexError):
    pass

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.utils import EnvConfig, Logger

# ── Configuration ────────────────────────────────────────────────────────────

class ManufacturingConfig(EnvConfig):
    """Manufacturing test config from environment variables."""
    ENV_PREFIX = ""

    # Fixture configuration
    FIXTURE_CONFIG_PATH: Optional[str] = None

    # MTIB hosts (comma-separated for multi-slot)
    MTIB_HOSTS: Optional[str] = None

    # Single MTIB (for single-slot testing)
    MTIB_HOST: Optional[str] = None
    MTIB_PORT: int = 50053

    # Test artifacts
    ARTIFACTS_DIR: Optional[str] = None

    # Mock mode
    MOCK_MODE: Optional[str] = None


cfg = ManufacturingConfig()
log = Logger(log_name="manufacturing")

# Mock mode detection
MOCK_MODE = (cfg.MOCK_MODE or "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
pytest_plugins = ["corekinect.test.validation.reporter"]


# ── Slot Context ─────────────────────────────────────────────────────────────

@dataclass
class SlotContext:
    """Per-slot test context for manufacturing.

    Each slot has its own MTIB connection, UART capture, and shared data.
    """
    slot_id: str
    snr: str
    mtib: MtibV1Client
    uart_buffer: List[str] = field(default_factory=list)
    shared_data: Dict = field(default_factory=dict)
    _uart_thread: Optional[threading.Thread] = None
    _uart_stop: threading.Event = field(default_factory=threading.Event)

    def connect(self) -> None:
        """Connect to MTIB server."""
        err = self.mtib.connect()
        if err:
            raise ConnectionError(f"MTIB connection failed for {self.slot_id}: {err}")

        ready, errors, err = self.mtib.HealthCheck()
        if err:
            raise ConnectionError(f"MTIB health check failed for {self.slot_id}: {err}")
        if not ready:
            raise ConnectionError(f"MTIB not ready for {self.slot_id}: {errors}")

        log.info("Connected to MTIB for %s (SNR=%s)", self.slot_id, self.snr)

    def disconnect(self) -> None:
        """Disconnect from MTIB server."""
        self._uart_stop.set()
        if self._uart_thread:
            self._uart_thread.join(timeout=2.0)
        err = self.mtib.disconnect()
        if err:
            log.warning("MTIB disconnect error for %s: %s", self.slot_id, err)

    def start_uart_capture(self) -> None:
        """Start background UART capture."""
        # Implementation depends on MTIB V1 UART streaming API
        pass

    def get_uart_log(self) -> str:
        """Return captured UART output."""
        return "\n".join(self.uart_buffer)

    def clear_uart(self) -> None:
        """Clear UART buffer."""
        self.uart_buffer.clear()


# ── Multi-Slot Fixture Context ───────────────────────────────────────────────

@dataclass
class FixtureContext:
    """Multi-slot manufacturing fixture context.

    Manages N slots (typically 4) for batch manufacturing.
    Each slot can be tested in parallel.
    """
    config: Dict
    slots: Dict[str, SlotContext] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "FixtureContext":
        """Create FixtureContext from environment variables."""
        # Load fixture config
        config_path = cfg.FIXTURE_CONFIG_PATH
        if config_path and os.path.isfile(config_path):
            with open(config_path) as f:
                config = json.load(f)
        else:
            # Default 4-slot config
            config = {
                "snrs": {
                    "slot-1": "000A",
                    "slot-2": "000B",
                    "slot-3": "000C",
                    "slot-4": "000D",
                }
            }

        # Parse MTIB hosts
        mtib_hosts = []
        if cfg.MTIB_HOSTS:
            mtib_hosts = [h.strip() for h in cfg.MTIB_HOSTS.split(",")]
        elif cfg.MTIB_HOST:
            mtib_hosts = [f"{cfg.MTIB_HOST}:{cfg.MTIB_PORT}"]

        # Create slot contexts
        slots = {}
        snrs = config.get("snrs", {})

        for i, slot_id in enumerate(sorted(snrs.keys())):
            snr = snrs[slot_id]

            # Get MTIB host for this slot (round-robin if fewer hosts than slots)
            if mtib_hosts:
                host_addr = mtib_hosts[i % len(mtib_hosts)]
                if ":" in host_addr:
                    host, port = host_addr.rsplit(":", 1)
                    port = int(port)
                else:
                    host = host_addr
                    port = 50053
            else:
                raise ValueError("MTIB_HOSTS or MTIB_HOST must be set")

            mtib_config = MtibV1Client.Config(net=NetConfig(addr=host, port=port))
            mtib = MtibV1Client(mtib_config)

            slots[slot_id] = SlotContext(
                slot_id=slot_id,
                snr=snr,
                mtib=mtib,
            )

        return cls(config=config, slots=slots)

    def connect_all(self) -> None:
        """Connect all slots to their MTIB servers."""
        for slot in self.slots.values():
            slot.connect()

    def disconnect_all(self) -> None:
        """Disconnect all slots."""
        for slot in self.slots.values():
            slot.disconnect()

    def slot(self, slot_id: str) -> SlotContext:
        """Get context for a specific slot."""
        return self.slots[slot_id]

    @property
    def all_snrs(self) -> List[str]:
        """Return list of all serial numbers."""
        return [s.snr for s in self.slots.values()]


# ── Mock Context ─────────────────────────────────────────────────────────────

def _build_mock_context() -> FixtureContext:
    """Build a FixtureContext with mock MTIB clients."""
    config = {
        "snrs": {
            "slot-1": "MOCK1",
            "slot-2": "MOCK2",
            "slot-3": "MOCK3",
            "slot-4": "MOCK4",
        }
    }

    # Mock MTIB client that does nothing
    class MockMtibClient:
        def connect(self): return None
        def disconnect(self): return None
        def HealthCheck(self): return True, [], None
        def PowerEnable(self, *args, **kwargs): return None, None
        def PowerDisable(self, *args, **kwargs): return None, None
        def GpioConfig(self, *args, **kwargs): return None
        def GpioWrite(self, *args, **kwargs): return None
        def DutPowerRead(self, *args, **kwargs):
            from collections import namedtuple
            Result = namedtuple("Result", ["current_ma", "voltage_v", "power_mw"])
            return Result(current_ma=25.0, voltage_v=4.5, power_mw=112.5), None

    slots = {}
    for slot_id, snr in config["snrs"].items():
        slots[slot_id] = SlotContext(
            slot_id=slot_id,
            snr=snr,
            mtib=MockMtibClient(),
        )

    log.info("Mock mode: 4-slot fixture with mock MTIB clients")
    return FixtureContext(config=config, slots=slots)


# ── pytest Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fixture_ctx(request) -> FixtureContext:
    """Session-scoped multi-slot fixture context.

    In mock mode (MOCK_MODE=1), returns a context with mock MTIB clients.
    In hardware mode, connects to real MTIB servers.

    Yields:
        FixtureContext with all slots connected.
    """
    if MOCK_MODE:
        ctx = _build_mock_context()
        yield ctx
        return

    ctx = FixtureContext.from_env()
    ctx.connect_all()
    yield ctx
    ctx.disconnect_all()


@pytest.fixture(scope="session")
def config(fixture_ctx) -> Dict:
    """Access fixture configuration."""
    return fixture_ctx.config


@pytest.fixture(params=["slot-1", "slot-2", "slot-3", "slot-4"])
def slot(fixture_ctx, request) -> SlotContext:
    """Per-slot fixture — parametrizes tests across all slots.

    Tests using this fixture run once per slot. Use for parallel slot testing.

    Example:
        def test_chip_id(slot):
            result = slot.mtib.get_chip_id()
            assert result.success
    """
    slot_id = request.param
    if slot_id not in fixture_ctx.slots:
        pytest.skip(f"Slot {slot_id} not configured")
    return fixture_ctx.slots[slot_id]


@pytest.fixture
def slot_1(fixture_ctx) -> SlotContext:
    """Direct access to slot-1 (for tests that need specific slot)."""
    return fixture_ctx.slots.get("slot-1")


@pytest.fixture
def slot_2(fixture_ctx) -> SlotContext:
    """Direct access to slot-2."""
    return fixture_ctx.slots.get("slot-2")


@pytest.fixture
def slot_3(fixture_ctx) -> SlotContext:
    """Direct access to slot-3."""
    return fixture_ctx.slots.get("slot-3")


@pytest.fixture
def slot_4(fixture_ctx) -> SlotContext:
    """Direct access to slot-4."""
    return fixture_ctx.slots.get("slot-4")


# ── Test Lifecycle Hooks ─────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "electrical: marks electrical tests (Step 1-10)",
    )
    config.addinivalue_line(
        "markers",
        "post: marks POST tests (chip ID, BMS, charger, GPS, etc.)",
    )
    config.addinivalue_line(
        "markers",
        "fw_flash: marks firmware flash tests",
    )
    config.addinivalue_line(
        "markers",
        "personalize: marks device personalization tests",
    )
    config.addinivalue_line(
        "markers",
        "sequential: marks tests that must run in order",
    )


@pytest.fixture(autouse=True)
def _test_lifecycle(request, fixture_ctx):
    """Auto-applied per-test lifecycle hook.

    Clears UART buffers before each test and dumps logs after.
    """
    # Setup: clear UART for all slots
    for slot in fixture_ctx.slots.values():
        slot.clear_uart()

    yield

    # Teardown: dump UART logs if artifacts dir is set
    artifacts_dir = cfg.ARTIFACTS_DIR
    if artifacts_dir:
        os.makedirs(artifacts_dir, exist_ok=True)
        for slot in fixture_ctx.slots.values():
            uart_log = slot.get_uart_log()
            if uart_log:
                log_path = os.path.join(
                    artifacts_dir,
                    f"{request.node.name}_{slot.slot_id}_uart.log"
                )
                with open(log_path, "w") as f:
                    f.write(uart_log)


# ── Log Streaming Setup ──────────────────────────────────────────────────────

class LogStreamWriter:
    """Tee stdout/stderr to both console and a buffer for upload."""

    def __init__(self, original, buffer: List[str], name: str):
        self.original = original
        self.buffer = buffer
        self.name = name

    def write(self, text):
        if text.strip():
            self.buffer.append(text)
        self.original.write(text)

    def flush(self):
        self.original.flush()


_log_buffer: List[str] = []


def pytest_sessionstart(session):
    """Hook: called before test collection.

    Sets up stdout/stderr capture for log streaming.
    """
    run_id = os.environ.get("CONCORD_RUN_ID")
    if run_id:
        # Tee stdout/stderr to buffer for upload
        sys.stdout = LogStreamWriter(sys.stdout, _log_buffer, "stdout")
        sys.stderr = LogStreamWriter(sys.stderr, _log_buffer, "stderr")
        log.info("Log streaming enabled for run %s", run_id)


def pytest_sessionfinish(session, exitstatus):
    """Hook: called after all tests complete.

    Restores stdout/stderr and uploads captured logs.
    """
    # Restore original streams
    if hasattr(sys.stdout, "original"):
        sys.stdout = sys.stdout.original
    if hasattr(sys.stderr, "original"):
        sys.stderr = sys.stderr.original

    # Upload captured logs
    run_id = os.environ.get("CONCORD_RUN_ID")
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")

    if run_id and api_url and api_key and _log_buffer:
        try:
            import base64
            import requests

            log_content = "".join(_log_buffer)
            url = f"{api_url}/v2/validation/runs/{run_id}/report/log-chunk"
            headers = {"Authorization": f"Bearer {api_key}"}
            data = {
                "file": "console.log",
                "offset": 0,
                "data": base64.b64encode(log_content.encode()).decode(),
                "timestamp": time.time(),
            }
            requests.post(url, json=data, headers=headers, timeout=10)
            log.info("Uploaded console log (%d bytes)", len(log_content))
        except Exception as e:
            log.warning("Failed to upload console log: %s", e)
