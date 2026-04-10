"""pytest fixtures for Alpha manufacturing tests.

Provides multi-slot test context using corekinect's FixtureContext.
Each slot has its own MTIB connection for parallel panel testing.

Required environment variables:
    MTIB_HOSTS: Comma-separated MTIB addresses (multi-slot)
    — OR —
    MTIB_HOST / MTIB_ADDRESS: Single MTIB address (single-slot)

Optional:
    FIXTURE_CONFIG_PATH: Path to fixture config JSON (overrides env vars)
    MOCK_MODE: Set to "1" for offline testing with mock hardware
    ARTIFACTS_DIR: Directory for test artifacts (UART logs)
    CONCORD_RUN_ID: Run ID (activates reporter plugin)
    CONCORD_API_URL: Concord HTTP API base URL
    CONCORD_API_KEY: API key for reporter auth
    PRODUCT_SLUG: Product slug for API-based config loading (default: "alpha_b0")
    PIPELINE_ID: Build pipeline for firmware resolution
"""

import os
import time
from typing import Dict, List, Optional

import pytest

from corekinect.test.slot import FixtureContext, SlotContext
from corekinect.utils import Logger

log = Logger(log_name="manufacturing")

# ── Mock mode ───────────────────────────────────────────────────────────────

MOCK_MODE = os.environ.get("MOCK_MODE", "").strip().lower() in ("1", "true", "yes")

if MOCK_MODE:
    _real_sleep = time.sleep
    time.sleep = lambda s: _real_sleep(min(s, 0.01))

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
pytest_plugins = ["corekinect.test.reporter"]


# ── Product config ──────────────────────────────────────────────────────────

_DEFAULT_PRODUCT_METADATA = {
    "device_type": 2,
    "device_variant": 3,
    "app_ids": {"nrf52840": 109, "nrf9151": 108},
    "corecloud_env": "VAL_1_0",
}


def _load_product_metadata() -> Dict:
    """Load product metadata from API or fall back to defaults."""
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
                    log.info("Loaded product config from API: %s", product.get("name"))
                    return metadata
        except Exception as e:
            log.warning("Failed to fetch product config from API: %s", e)

    log.info("Using default product metadata for %s", slug)
    return dict(_DEFAULT_PRODUCT_METADATA)


_product_metadata: Optional[Dict] = None


def _get_product_metadata() -> Dict:
    global _product_metadata
    if _product_metadata is None:
        _product_metadata = _load_product_metadata()
    return _product_metadata


# ── Mock fixture ────────────────────────────────────────────────────────────

def _build_mock_context() -> FixtureContext:
    """Build a FixtureContext with mock MTIB clients for offline testing."""
    from collections import namedtuple

    class MockMtibClient:
        def connect(self): return None
        def disconnect(self): return None
        def HealthCheck(self): return True, [], None
        def PowerEnable(self, *a, **kw): return None
        def PowerDisable(self, *a, **kw): return None
        def GpioConfig(self, *a, **kw): return None
        def GpioWrite(self, *a, **kw): return None
        def PowerRead(self, *a, **kw):
            R = namedtuple("R", ["current_ma", "voltage_v", "power_mw"])
            return R(current_ma=25.0, voltage_v=4.5, power_mw=112.5), None

    mock_snrs = ["MOCK0", "MOCK1", "MOCK2", "MOCK3"]
    slots = {}
    for i, snr in enumerate(mock_snrs):
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


# ── Slot discovery ──────────────────────────────────────────────────────────

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

    # Single-slot fallback
    return ["slot-0"]


# ── pytest fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fixture_ctx() -> FixtureContext:
    """Session-scoped multi-slot fixture context."""
    if MOCK_MODE:
        ctx = _build_mock_context()
        yield ctx
        return

    ctx = FixtureContext.from_env()
    ctx.connect_all()

    # Merge product metadata into config
    ctx.config["product_metadata"] = _get_product_metadata()

    yield ctx
    ctx.disconnect_all()


@pytest.fixture(scope="session")
def config(fixture_ctx) -> Dict:
    """Fixture configuration dict."""
    return fixture_ctx.config


@pytest.fixture(scope="session")
def mfg_assets():
    """Session-scoped firmware assets from build pipeline.

    When PIPELINE_ID is set, fetches build artifacts from Concord API.
    Returns None otherwise — tests fall back to config-based filenames.
    """
    pipeline_id = os.environ.get("PIPELINE_ID")
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")

    if pipeline_id and api_url and api_key:
        from corekinect.test.stage_assets import StageAssets
        assets = StageAssets.from_pipeline(
            pipeline_id=pipeline_id,
            stage="manufacturing",
            api_url=api_url,
            api_key=api_key,
            strict=False,
        )
        log.info("Manufacturing firmware loaded from pipeline %s", pipeline_id)
        yield assets
        assets.cleanup()
    else:
        yield None


@pytest.fixture(scope="session")
def product_config() -> Dict:
    """Product metadata (device_type, device_variant, app_ids, corecloud_env)."""
    return _get_product_metadata()


@pytest.fixture(params=_get_slot_ids())
def slot(fixture_ctx, request) -> SlotContext:
    """Per-slot fixture — parametrizes tests across all slots.

    Tests using this fixture run once per slot.
    """
    slot_id = request.param
    if slot_id not in fixture_ctx.slots:
        pytest.skip(f"Slot {slot_id} not configured")
    return fixture_ctx.slots[slot_id]


# ── Test lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _test_lifecycle(request, fixture_ctx):
    """Per-test setup/teardown. Dumps UART logs to artifacts dir."""
    yield

    artifacts_dir = os.environ.get("ARTIFACTS_DIR")
    if not artifacts_dir:
        return

    os.makedirs(artifacts_dir, exist_ok=True)
