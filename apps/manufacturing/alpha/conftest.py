"""pytest fixtures for Alpha manufacturing tests.

Uses the autoconf plugin for multi-slot fixture management, reporter
integration, and test lifecycle. This file only defines product-specific
fixtures that autoconf doesn't provide.

Required environment:
    MTIB_HOSTS          Comma-separated MTIB addresses (multi-slot)
    SLOT_FILTER         Comma-separated slot indices (set by mfg runner per-panel)
    SLOT_SNRS           Comma-separated serial numbers (set by mfg runner per-panel)

Optional:
    FIXTURE_CONFIG_PATH Path to fixture config JSON
    ARTIFACTS_DIR       Directory for test artifacts
    CONCORD_RUN_ID      Run ID (activates reporter plugin)
    CONCORD_API_URL     Concord HTTP API base URL
    CONCORD_API_KEY     API key for reporter auth
    ASSET_SET_ID        AssetSet ID for firmware resolution
"""

import os
from typing import Dict, Optional

import pytest

from corekinect.utils import Logger

log = Logger(log_name="manufacturing")

# Auto-discover autoconf (multi-slot, reporter, lifecycle) and reporter plugins
pytest_plugins = ["corekinect.test.autoconf", "corekinect.test.reporter"]


# ── Product-specific fixtures ────────────────────────────────────────────

@pytest.fixture(scope="session")
def config(fixture_ctx) -> Dict:
    """Fixture configuration dict (thresholds, test parameters).

    Reads from the fixture controller's config (loaded from fixture.yaml).
    """
    # If slots have fixture controllers, get config from the first one
    for slot_id, slot in fixture_ctx.slots.items():
        if hasattr(slot, "fixture") and slot.fixture and hasattr(slot.fixture, "config"):
            return slot.fixture.config
    return {}


@pytest.fixture(scope="session")
def mfg_assets():
    """Session-scoped firmware set — source-agnostic.

    Uses the framework's FirmwareSet which auto-detects the firmware source:
      1. ASSET_SET_ID → Concord AssetSet (independent of build system)
      2. BUILD_RUN_ID → CI BuildRun artifacts
      3. None → tests fall back to config-based filenames or skip
    """
    from corekinect.test.firmware_set import FirmwareSet

    fw = FirmwareSet.from_env()
    if fw:
        log.info("Firmware resolved: %s", fw)
        yield fw
        fw.cleanup()
    else:
        log.info("No firmware configured — firmware-dependent tests will use fallbacks")
        yield None
