"""FUOTA stage — shared fixtures and utilities.

Stage 5: Over-the-air firmware update verification — blocks merge.

MTIB, UART, power, and artifact infrastructure come from the root conftest's
``ctx`` fixture (TestContext). FUOTA tests use ``ctx.mtib`` for hardware
access, and get background UART capture + artifact streaming for free.

FUOTA-specific fixtures (defined here):
    pipeline_assets:  ArtifactResolver — strict (fails if PIPELINE_ID missing)
    fuota_client:     CoreCloud FUOTA API client
    device_config:    Device identity (SNR, device_id, IMEI, ICCIDs)

Utilities:
    parse_cfw_header:        CFW binary header parsing (from framework)
    register_fuota_cleanup:  atexit handler to disable FUOTA on exit
"""

import atexit
import os
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from corekinect.utils import Logger

# CFW parsing — re-export from framework for backward compat
from corekinect.test.cfw import parse_cfw_header  # noqa: F401

log = Logger(log_name="fuota")


def pytest_configure(config):
    """Register sequential test plugin for fail-fast within test classes."""
    from corekinect.test.sequential import SequentialTestPlugin

    if not config.pluginmanager.has_plugin("sequential_tests"):
        plugin = SequentialTestPlugin()
        config.pluginmanager.register(plugin, "sequential_tests")


# =============================================================================
# DEVICE CONFIG
# =============================================================================


@dataclass
class DeviceConfig:
    """Device identity and hardware constants for FUOTA tests.

    Populated from environment variables (set by K8s Job) or CLI options.
    All fields are validated by the device_config fixture.
    """

    device_id: str = ""
    device_snr: str = ""
    device_imei: str = ""
    device_iccids: List[str] = field(default_factory=list)
    device_type_id: int = 2   # Alpha
    device_variant_id: int = 3  # Alpha B0


# =============================================================================
# FUOTA-SPECIFIC FIXTURES
# =============================================================================
#
# The root conftest provides:
#   ctx           — TestContext (session-scoped): MTIB, UART, power, artifacts
#   product       — ProductContext from Concord catalog API
#   mock_cloud    — MockCloudClient for offline testing
#
# The root conftest's _test_lifecycle autouse fixture calls:
#   ctx.setup_test()    — clears UART buffer, marks test start
#   ctx.teardown_test() — dumps UART logs, uploads artifacts
#
# These run automatically for any test that requests ``ctx``.
# =============================================================================


@pytest.fixture(scope="session")
def device_config(request) -> DeviceConfig:
    """Device identity from environment variables or CLI options."""
    config = DeviceConfig(
        device_id=os.environ.get("DEVICE_ID", ""),
        device_snr=(
            request.config.getoption("--device-snr", default=None)
            or os.environ.get("DEVICE_SNR", "")
        ),
        device_imei=os.environ.get("DEVICE_IMEI", ""),
        device_iccids=[
            s.strip()
            for s in os.environ.get("DEVICE_ICCIDS", "").split(",")
            if s.strip()
        ],
    )

    return config


@pytest.fixture(scope="session")
def pipeline_assets(request):
    """Artifact resolver for FUOTA builds. Downloads hex/CFW on demand.

    Shadows the root conftest's pipeline_assets fixture with a stricter
    version that fails immediately if PIPELINE_ID is not set (FUOTA stage
    always requires a pipeline).

    Returns an ArtifactResolver instance.
    """
    from corekinect.test.artifact_resolver import ArtifactResolver

    pipeline_id = (
        request.config.getoption("--pipeline-id", default=None)
        or os.environ.get("PIPELINE_ID")
    )
    if not pipeline_id:
        pytest.fail("PIPELINE_ID is required for FUOTA tests")

    resolver = ArtifactResolver(
        pipeline_id=pipeline_id,
        api_url=os.environ.get("CONCORD_API_URL", ""),
        api_key=os.environ.get("CONCORD_API_KEY", ""),
    )
    log.info("ArtifactResolver loaded: %s", pipeline_id)

    yield resolver

    resolver.cleanup()


@pytest.fixture(scope="session")
def fuota_client():
    """CoreCloud FUOTA API client (lazy-init on first use)."""
    from corekinect.test.fuota_client import FuotaClient
    return FuotaClient(api_env="VAL_1_0")


# =============================================================================
# CLEANUP
# =============================================================================

_cleanup_registry: List[tuple] = []  # [(device_id, plan_id), ...]


def register_fuota_cleanup(device_id: str, plan_id: int) -> None:
    """Register device+plan for cleanup on exit.

    Uses a list (not dict) so both setup and upgrade plans from two-phase
    tests are tracked — a dict would overwrite the setup plan entry.
    """
    _cleanup_registry.append((device_id, plan_id))
    log.info("Registered FUOTA cleanup: device=%s plan=%d", device_id, plan_id)


def _run_fuota_cleanup() -> None:
    """Clean up all registered FUOTA assignments on exit."""
    if not _cleanup_registry:
        return

    log.info("Running FUOTA cleanup for %d assignment(s)...", len(_cleanup_registry))

    try:
        from corekinect.test.fuota_client import FuotaClient

        client = FuotaClient(api_env="VAL_1_0")

        for device_id, plan_id in _cleanup_registry:
            try:
                client.disable_device(device_id, plan_id)
                log.info("Cleaned up: device=%s plan=%d", device_id, plan_id)
            except Exception as e:
                log.warning("Cleanup failed for %s: %s", device_id, e)
    except Exception as e:
        log.warning("Cleanup init failed: %s", e)


atexit.register(_run_fuota_cleanup)
