"""pytest fixtures for Alpha manufacturing tests.

Provides:
  - Multi-slot test context via corekinect's FixtureContext
  - Per-slot MTIB connection for parallel panel testing
  - Shell fixtures (AlphaAppShell, CommsCoprocShell) for UART commands
  - Firmware asset resolution from CI pipeline
  - Mock mode for offline development

Required environment:
    MTIB_HOSTS          Comma-separated MTIB addresses (multi-slot)
    — OR —
    MTIB_HOST           Single MTIB address (single-slot)

Optional:
    FIXTURE_CONFIG_PATH Path to fixture config JSON (overrides env vars)
    MOCK_MODE           Set to "1" for offline testing with mock hardware
    ARTIFACTS_DIR       Directory for test artifacts
    CONCORD_RUN_ID      Run ID (activates reporter plugin)
    CONCORD_API_URL     Concord HTTP API base URL
    CONCORD_API_KEY     API key for reporter auth
    PRODUCT_SLUG        Product slug for API config (default: "alpha_b0")
    BUILD_RUN_ID        Build run ID for firmware resolution
    PROXY_SERVER_URL    CoreOps proxy for personalization
"""

import logging
import os
import time
from collections import namedtuple
from typing import Dict, List, Optional

import pytest

from corekinect.test.slot import FixtureContext, SlotContext
from corekinect.utils import Logger

log = Logger(log_name="manufacturing")

# ── Mock mode ──────────────────────────────────────────────────────────────

MOCK_MODE = os.environ.get("MOCK_MODE", "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
pytest_plugins = ["corekinect.test.reporter"]


# ── Product metadata ──────────────────────────────────────────────────────

_DEFAULT_PRODUCT_METADATA = {
    "device_type": 2,
    "device_variant": 3,
    "app_ids": {"nrf52840": 109, "nrf9151": 108},
    "corecloud_env": "VAL_1_0",
}


def _load_product_metadata() -> Dict:
    """Load product metadata from Concord API, fall back to defaults."""
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")
    slug = os.environ.get("PRODUCT_SLUG", "alpha_b0")

    if api_url and api_key:
        try:
            import requests

            url = f"{api_url}/v2/products/by-slug/{slug}"
            headers = {"Authorization": f"ApiKey {api_key}"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                body = resp.json()
                product = body.get("data", body)
                metadata = product.get("metadata")
                if metadata:
                    log.info("Loaded product metadata from API: %s", product.get("name"))
                    return metadata
        except Exception as e:
            log.warning("Failed to fetch product metadata from API: %s", e)

    log.info("Using default product metadata for %s", slug)
    return dict(_DEFAULT_PRODUCT_METADATA)


_product_metadata: Optional[Dict] = None


def _get_product_metadata() -> Dict:
    global _product_metadata
    if _product_metadata is None:
        _product_metadata = _load_product_metadata()
    return _product_metadata


# ── Mock hardware ─────────────────────────────────────────────────────────

PowerReadResult = namedtuple("PowerReadResult", ["current_ma", "voltage_v", "power_mw"])


class MockMtibClient:
    """Minimal MTIB mock for offline testing.

    Supports all APIs called by the manufacturing tests so they can
    exercise the full code path without real hardware.
    """

    def connect(self):
        return None

    def disconnect(self):
        return None

    def HealthCheck(self):
        return True, [], None

    def PowerEnable(self, channel=0, voltage_v=0.0):
        return None

    def PowerDisable(self, channel=0):
        return None

    def PowerRead(self, channel=0):
        return PowerReadResult(current_ma=25.0, voltage_v=4.5, power_mw=112.5), None

    def GpioConfig(self, gpio=0, direction=None, resistor=None):
        return None

    def GpioWrite(self, gpio=0, state=False):
        return None

    def AdcRead(self, channel=0):
        # Return plausible values per channel
        adc_values = {0: 3.3, 1: 4.5, 2: 4.5, 3: 0.01, 7: 3.3}
        return adc_values.get(channel, 0.0), None

    def FlashFwFile(self, fw_info=None, sector_erase=False, recover=False):
        return 1200, None

    def UploadFwFile(self, filepath="", host_type=None):
        return None

    def DeleteFwFile(self, fw_info=None):
        return None

    def EnableAppProtect(self, target=None):
        return True, None

    def UartStream(self, target, request_iter):
        """Yield nothing — shell commands detect mock via is_mock flag."""
        return iter([])


def _build_mock_context() -> FixtureContext:
    """Build a FixtureContext with mock MTIB clients for offline testing."""
    slots = {}
    for i, snr in enumerate(["MOCK0", "MOCK1", "MOCK2", "MOCK3"]):
        slot_id = f"slot-{i}"
        slot = SlotContext(
            slot_id=slot_id,
            slot_index=i,
            mtib_address="127.0.0.1",
            serial_number=snr,
        )
        slot.mtib = MockMtibClient()
        slots[slot_id] = slot

    log.info("Mock mode: %d-slot fixture with mock MTIB clients", len(slots))
    return FixtureContext(
        slots=slots,
        config={"product_metadata": _get_product_metadata()},
    )


# ── Slot discovery ────────────────────────────────────────────────────────

def _get_slot_ids() -> List[str]:
    """Determine slot IDs at collection time for fixture parametrization."""
    if MOCK_MODE:
        return ["slot-0", "slot-1", "slot-2", "slot-3"]

    mtib_hosts = os.environ.get("MTIB_HOSTS", "").strip()
    if mtib_hosts:
        count = len([a for a in mtib_hosts.split(",") if a.strip()])
        return [f"slot-{i}" for i in range(count)]

    config_path = os.environ.get("FIXTURE_CONFIG_PATH")
    if config_path and os.path.isfile(config_path):
        import json
        with open(config_path) as f:
            data = json.load(f)
        slot_count = len(data.get("slots", []))
        if slot_count:
            return [f"slot-{i}" for i in range(slot_count)]

    return ["slot-0"]


# ── pytest fixtures ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fixture_ctx() -> FixtureContext:
    """Session-scoped multi-slot fixture context."""
    if MOCK_MODE:
        ctx = _build_mock_context()
        yield ctx
        return

    ctx = FixtureContext.from_env()
    ctx.connect_all()
    ctx.config["product_metadata"] = _get_product_metadata()

    yield ctx
    ctx.disconnect_all()


@pytest.fixture(scope="session")
def config(fixture_ctx) -> Dict:
    """Fixture configuration dict (thresholds, test parameters)."""
    return fixture_ctx.config


@pytest.fixture(scope="session")
def is_mock() -> bool:
    """Whether tests are running in mock mode (no real hardware)."""
    return MOCK_MODE


@pytest.fixture(scope="session")
def mfg_assets():
    """Session-scoped firmware assets from a build run.

    When BUILD_RUN_ID is set, fetches build artifacts from Concord API.
    Returns None otherwise — tests fall back to config-based filenames.
    """
    build_run_id = os.environ.get("BUILD_RUN_ID")
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")

    if build_run_id and api_url and api_key:
        from corekinect.test.stage_assets import StageAssets

        assets = StageAssets.from_pipeline(
            pipeline_id=build_run_id,
            stage="manufacturing",
            api_url=api_url,
            api_key=api_key,
            strict=False,
        )
        log.info("Manufacturing firmware loaded from build run %s", build_run_id)
        yield assets
        assets.cleanup()
    else:
        yield None


@pytest.fixture(params=_get_slot_ids())
def slot(fixture_ctx, request) -> SlotContext:
    """Per-slot fixture — parametrizes tests across all panel slots.

    Each test using this fixture runs once per DUT.
    """
    slot_id = request.param
    if slot_id not in fixture_ctx.slots:
        pytest.skip(f"Slot {slot_id} not configured")
    return fixture_ctx.slots[slot_id]


# ── Test lifecycle ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _test_lifecycle(request, fixture_ctx):
    """Per-test setup/teardown."""
    yield

    artifacts_dir = os.environ.get("ARTIFACTS_DIR")
    if not artifacts_dir:
        return
    os.makedirs(artifacts_dir, exist_ok=True)
