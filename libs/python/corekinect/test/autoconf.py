"""Automatic pytest configuration from concord.yaml manifests.

Replaces per-product conftest.py boilerplate with a single line:

    # conftest.py
    pytest_plugins = ["corekinect.test.autoconf"]

The plugin reads the concord.yaml manifest (v2) from the test app
directory, then wires up all standard fixtures, hooks, and the
Concord reporter automatically. Product test apps only need custom
conftest.py code for product-specific fixtures (e.g., firmware_build
parametrization, mock scenarios).

Activation:
    Listed in conftest.py via pytest_plugins, or registered as a
    setuptools entry point under ``pytest11``.

No-op conditions:
    - No concord.yaml or concord.test.yaml found (silent no-op)
    - v1 manifest found but missing v2 fields (warning, no-op)
    - MTIB/hardware env vars missing (ctx fixture skips with pytest.skip)

Environment variables:
    MOCK_MODE / MOCK_CLOUD   "1" to enable mock mode (no hardware)
    BUILD_RUN_ID             Build run ID for firmware artifact resolution
    CONCORD_RUN_ID           Activates the Concord reporter plugin
    CONCORD_API_URL          Concord HTTP API base URL
    CONCORD_API_KEY          API key for reporter + artifact access
    ARTIFACTS_DIR            Directory for per-test UART log artifacts
    STAGE                    Validation stage name (default: "fuota")
"""

from __future__ import annotations

import importlib
import os
import re
import time
import warnings
from pathlib import Path
from typing import Any, List, Optional, TYPE_CHECKING

import pytest

# Regex for extracting the slot index from a parametrized test node id like
# "tests/foo.py::test_x[slot-2]". Used to assign each test to an xdist
# group so pytest-xdist runs all tests for a given slot on the same worker
# (and different slots run in parallel on different workers).
_SLOT_PARAM_RE = re.compile(r"\[slot-(\d+)\]")

if TYPE_CHECKING:
    from corekinect.manifest.types import Manifest

from corekinect.utils import Logger

log = Logger(log_name="autoconf")

# ---------------------------------------------------------------------------
# Internal state — populated during pytest_configure, read by fixtures
# ---------------------------------------------------------------------------

_manifest: Optional["Manifest"] = None
_manifest_path: Optional[Path] = None
_mock_mode: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _is_mock_mode(config: Optional[pytest.Config] = None) -> bool:
    """Check if mock mode is active via env var or CLI flag."""
    env_val = (
        os.environ.get("MOCK_MODE")
        or os.environ.get("MOCK_CLOUD")
        or ""
    ).strip().lower()
    if env_val in ("1", "true", "yes"):
        return True
    if config is not None:
        try:
            return config.getoption("--mock-cloud", default=False)
        except ValueError:
            pass
    return False


def _import_controller(dotted_path: str) -> Any:
    """Import a fixture controller class from a dotted module path.

    Accepts ``package.module.ClassName`` format. The last component is
    the class/callable name; everything before it is the module path.

    Returns:
        The imported class or callable.

    Raises:
        ImportError: If the module cannot be found or the name doesn't exist.
    """
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ImportError(
            f"Invalid controller path: {dotted_path!r} "
            f"— expected 'module.path.ClassName'"
        )
    module_path, class_name = parts
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ImportError(
            f"Controller class {class_name!r} not found in module {module_path!r}"
        )
    return cls


def _patch_sleep_for_mock() -> None:
    """Replace time.sleep with a near-instant version for mock mode.

    Stage tests contain hardware settle delays (30-60s) that are
    meaningless without real hardware.
    """
    real_sleep = time.sleep
    time.sleep = lambda s: real_sleep(min(s, 0.01))


# ═══════════════════════════════════════════════════════════════════════════
# pytest hooks — configure, CLI options, collection
# ═══════════════════════════════════════════════════════════════════════════


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options shared across all test apps."""
    group = parser.getgroup("concord", "Concord test framework options")
    group.addoption(
        "--device-id",
        action="store",
        default=None,
        help="Device ID hex string (overrides DEVICE_ID env var)",
    )
    group.addoption(
        "--mtib-host",
        action="store",
        default=None,
        help="MTIB server address (overrides MTIB_HOST env var)",
    )
    group.addoption(
        "--mtib-addr",
        action="store",
        default=None,
        help="MTIB address (alias for --mtib-host, overrides MTIB_ADDRESS env var)",
    )
    group.addoption(
        "--device-snr",
        action="store",
        default=None,
        help="Device serial number (overrides DEVICE_SNR env var)",
    )
    group.addoption(
        "--artifacts-dir",
        action="store",
        default=None,
        help="Directory for test artifacts (overrides ARTIFACTS_DIR env var)",
    )
    group.addoption(
        "--db-env",
        action="store",
        default=None,
        help="CoreCloud namespace, e.g. DEV_1_0 or VAL_1_0 (overrides CORECLOUD_DB_ENV)",
    )
    group.addoption(
        "--mock-cloud",
        action="store_true",
        default=False,
        help="Run in mock mode (no hardware/cloud required). Same as MOCK_MODE=1.",
    )
    group.addoption(
        "--build-run-id",
        action="store",
        default=None,
        help="Build run ID for firmware artifact resolution (overrides BUILD_RUN_ID)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Load the manifest, register reporter, and register markers.

    This is the entry point. When no manifest is found the plugin
    becomes a silent no-op — no fixtures are registered and tests
    that don't depend on them run normally.
    """
    global _manifest, _manifest_path, _mock_mode

    # ── 1. Find and load the manifest ──
    from corekinect.manifest.loader import find_manifest, load_manifest

    rootdir = Path(str(config.rootdir))
    manifest_path = find_manifest(start_dir=rootdir)
    if manifest_path is None:
        log.debug("No concord.yaml found under %s — autoconf is a no-op", rootdir)
        return

    try:
        manifest, result = load_manifest(manifest_path, validate=False)
    except Exception as exc:
        # v1 manifests or malformed YAML — warn and bail out
        warnings.warn(
            f"corekinect.test.autoconf: failed to load {manifest_path}: {exc}. "
            f"The manifest may be v1 format. Run 'corectl test migrate' to upgrade.",
            stacklevel=2,
        )
        return

    # Sanity check: from_dict succeeded but produced an empty manifest
    if not manifest.package.type:
        warnings.warn(
            f"corekinect.test.autoconf: manifest at {manifest_path} has no package type. "
            f"It may be a v1 manifest. Run 'corectl test migrate' to upgrade.",
            stacklevel=2,
        )
        return

    _manifest = manifest
    _manifest_path = manifest_path
    config._concord_manifest = manifest  # type: ignore[attr-defined]

    # ── 2. Mock mode ──
    _mock_mode = _is_mock_mode(config)
    if _mock_mode:
        _patch_sleep_for_mock()

    # ── 3. Register the Concord reporter plugin ──
    # The reporter self-activates based on CONCORD_RUN_ID; we just ensure
    # it is imported. Registering via pluginmanager avoids duplicate
    # registration if the test app's conftest.py also lists it.
    from corekinect.test.reporter import pytest_configure as reporter_configure

    if not config.pluginmanager.has_plugin("concord_reporter"):
        reporter_configure(config)

    # ── 4. Register custom markers from manifest stages ──
    if manifest.is_validation:
        for stage in manifest.stages.values():
            for marker in stage.markers:
                config.addinivalue_line(
                    "markers",
                    f"{marker}: auto-registered from concord.yaml stage '{stage.name}'",
                )

    # Common markers used across test apps
    config.addinivalue_line(
        "markers",
        "corecloud: marks tests that require CoreCloud connectivity",
    )
    config.addinivalue_line(
        "markers",
        "nfc: marks tests that require NFC reader hardware",
    )

    log.info(
        "autoconf: loaded %s manifest from %s (type=%s, product=%s)",
        manifest.schema_version,
        manifest_path.name,
        manifest.package.type,
        manifest.product.slug,
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """Reorder parametrized tests and skip cloud-dependent tests when needed.

    Firmware variant grouping:
        Default pytest interleaves: test_A[debug], test_A[release], test_B[debug]...
        Reordered: test_A[debug], test_B[debug]..., test_A[release], test_B[release]...
        This reduces full flash cycles from 2*N to just 2.

    Cloud test skipping:
        Tests marked @pytest.mark.corecloud are skipped in mock mode or
        when CoreCloud DB credentials are not configured.
    """
    if _manifest is None:
        return

    # ── Skip cloud-dependent tests ──
    skip_reason = None
    if _mock_mode:
        skip_reason = "Requires CoreCloud DB/API — skipped in mock mode"
    elif not _has_cloud_db():
        skip_reason = "CoreCloud DB not configured"

    if skip_reason:
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "corecloud" in item.keywords:
                item.add_marker(skip_marker)

    # ── Reorder for firmware variant grouping ──
    def _variant_sort_key(item: pytest.Item):
        if "[release]" in item.nodeid:
            return (1, item.nodeid)
        if "[debug]" in item.nodeid:
            return (0, item.nodeid)
        return (-1, item.nodeid)

    items.sort(key=_variant_sort_key)

    # ── Assign xdist_group per slot for parallel execution ──
    # When pytest-xdist is invoked with `--dist=loadgroup`, all tests sharing
    # the same group run on the same worker, and different groups run on
    # different workers in parallel. By grouping tests by their [slot-N]
    # parameterization, each slot runs all its tests on a dedicated worker
    # while slots advance in parallel. Single-slot/standalone runs naturally
    # collapse to one worker (one group → one worker), so this is safe for
    # both panel and standalone runs.
    for item in items:
        match = _SLOT_PARAM_RE.search(item.nodeid)
        if match:
            slot_id = f"slot-{match.group(1)}"
            item.add_marker(pytest.mark.xdist_group(name=slot_id))


def _has_cloud_db() -> bool:
    """Check whether CoreCloud DB credentials are available."""
    return bool(
        os.environ.get("CORECLOUD_DB_ENV")
        or os.environ.get("DEV_1_0_DB_HOST")
        or os.environ.get("VAL_1_0_DB_HOST")
    )


# ═══════════════════════════════════════════════════════════════════════════
# CLI overrides — apply before fixture creation
# ═══════════════════════════════════════════════════════════════════════════


def _apply_cli_overrides(config: pytest.Config) -> None:
    """Push CLI option values into environment variables.

    Called once when creating the session-scoped context. CLI options
    take precedence over env vars set by K8s Job templates.
    """
    _overrides = {
        "--device-id": "DEVICE_ID",
        "--mtib-host": "MTIB_HOST",
        "--mtib-addr": "MTIB_ADDRESS",
        "--device-snr": "DEVICE_SNR",
        "--artifacts-dir": "ARTIFACTS_DIR",
        "--db-env": "CORECLOUD_DB_ENV",
        "--build-run-id": "BUILD_RUN_ID",
    }
    for option, env_var in _overrides.items():
        try:
            value = config.getoption(option)
        except ValueError:
            continue
        if value:
            os.environ[env_var] = str(value)


# ═══════════════════════════════════════════════════════════════════════════
# Slot ID resolution — must be defined before the slot fixture
# ═══════════════════════════════════════════════════════════════════════════


def _get_slot_ids() -> List[str]:
    """Resolve slot IDs from environment at collection time.

    Delegates to get_slot_ids_from_env() which respects SLOT_FILTER
    (set per-panel by the manufacturing runner), MTIB_HOSTS, and
    FIXTURE_CONFIG_PATH. No mock fallbacks — real hardware or fail.
    """
    from corekinect.test.slot import get_slot_ids_from_env
    return get_slot_ids_from_env()


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def manifest() -> "Manifest":
    """The loaded Manifest object from concord.yaml.

    Session-scoped and read-only. Access product config, stage
    definitions, fixture controller path, etc.
    """
    if _manifest is None:
        pytest.skip("No concord.yaml manifest found — cannot provide manifest fixture")
    return _manifest


@pytest.fixture(scope="session")
def ctx(request: pytest.FixtureRequest, manifest: "Manifest"):
    """Session-scoped test context — connects once, shared across all tests.

    Validation packages:
        Creates a TestContext with the fixture controller specified in
        concord.yaml (``fixture.controller``). Connects to MTIB and
        starts UART capture, power polling, and telemetry.

    Mock mode (MOCK_MODE=1 or --mock-cloud):
        Returns a context with in-memory mocks. No hardware or network.

    Skips the entire session if required env vars are missing rather
    than raising an opaque connection error.
    """
    if _manifest is None:
        pytest.skip("No concord.yaml manifest — ctx fixture unavailable")

    # Manufacturing packages use fixture_ctx, not ctx
    if manifest.fixture.multi_slot:
        pytest.skip(
            "Multi-slot manifest — use fixture_ctx and slot fixtures instead of ctx"
        )

    _apply_cli_overrides(request.config)

    if _is_mock_mode(request.config):
        context = _build_mock_validation_context(manifest)
        yield context
        return

    # ── Hardware mode ──
    # Validate required env vars before attempting connection
    mtib_addr = os.environ.get("MTIB_ADDRESS") or os.environ.get("MTIB_HOST")
    if not mtib_addr:
        pytest.skip(
            "MTIB_ADDRESS or MTIB_HOST not set — cannot connect to hardware. "
            "Set MOCK_MODE=1 to run without hardware."
        )

    device_id = os.environ.get("DEVICE_ID")
    if not device_id:
        pytest.skip("DEVICE_ID not set — cannot create test context")

    # Import and instantiate the fixture controller from the manifest
    controller_path = manifest.fixture.controller
    try:
        controller_class = _import_controller(controller_path)
    except ImportError as exc:
        pytest.skip(
            f"Cannot import fixture controller {controller_path!r}: {exc}"
        )

    from corekinect.test.context import TestContext

    try:
        context = TestContext.from_env(
            fixture_factory=lambda mtib: controller_class(mtib)
        )
        context.connect()
    except Exception as exc:
        pytest.fail(f"Failed to create/connect TestContext: {exc}")

    yield context
    context.disconnect()


@pytest.fixture(scope="session")
def fixture_ctx(request: pytest.FixtureRequest, manifest: "Manifest"):
    """Session-scoped multi-slot fixture context.

    Connects all MTIB slots defined by MTIB_HOSTS or FIXTURE_CONFIG_PATH.
    Each slot gets its own MTIB client for parallel DUT access.
    Also builds SlotTestContexts with per-slot UART/power/artifacts.

    Mock mode (MOCK_MODE=1 or --mock-cloud):
        Returns a context with mock MTIB clients. No hardware or network.
    """
    if _manifest is None:
        pytest.skip("No concord.yaml manifest — fixture_ctx unavailable")

    _apply_cli_overrides(request.config)

    from corekinect.test.slot import FixtureContext

    # Validate required env vars before attempting connection
    import os as _os
    mtib_hosts = _os.environ.get("MTIB_HOSTS", "").strip()
    mtib_host = _os.environ.get("MTIB_HOST", "") or _os.environ.get("MTIB_ADDRESS", "")
    fixture_config = _os.environ.get("FIXTURE_CONFIG_PATH", "").strip()
    if not mtib_hosts and not mtib_host and not fixture_config:
        pytest.skip(
            "No MTIB hardware configured (MTIB_HOSTS, MTIB_HOST, or FIXTURE_CONFIG_PATH required)"
        )

    fctx = FixtureContext.from_env()
    fctx.connect_all()

    # Create telemetry streamer for live power/UART streaming to frontend
    telemetry = None
    run_id = _os.environ.get("CONCORD_RUN_ID", "").strip()
    api_url = _os.environ.get("CONCORD_API_URL", "").strip()
    api_key = _os.environ.get("CONCORD_API_KEY", "").strip()
    if run_id and api_url and api_key:
        from .telemetry import TelemetryStreamer
        from .artifact_writer import ArtifactWriter

        artifact_writer = ArtifactWriter()

        def _telemetry_storage(object_path: str, content_bytes: bytes) -> None:
            artifact_writer.write_bytes(object_path, content_bytes)

        telemetry = TelemetryStreamer(
            run_id=run_id,
            api_url=api_url,
            api_key=api_key,
            on_flush_storage=_telemetry_storage,
        )
        telemetry.start()

    # Build slot_id → RunTarget ID mapping from SLOT_TARGET_IDS env var.
    # The mfg_runner sets this from the run assignment targets so each
    # slot's telemetry (power, UART) includes the targetId for frontend routing.
    slot_target_id_env = _os.environ.get("SLOT_TARGET_IDS", "").strip()
    slot_target_ids: dict = {}  # slot_id (e.g., "slot-0") → RunTarget ID
    if slot_target_id_env:
        parts = [p.strip() for p in slot_target_id_env.split(",")]
        for i, tid in enumerate(parts):
            if tid:
                slot_target_ids[f"slot-{i}"] = tid

    # Build per-slot rich contexts (UART, power, artifacts)
    slot_test_ctxs = fctx.build_slot_test_contexts(
        telemetry=telemetry,
        target_ids=slot_target_ids,
    )
    for stc in slot_test_ctxs.values():
        stc.connect()
    fctx._slot_test_contexts = slot_test_ctxs
    fctx._telemetry = telemetry

    # Store slot_index → serial_number mapping on the reporter.
    # The reporter uses this in pytest_runtest_logstart to set deviceSerial
    # BEFORE execution-start fires — critical for multi-slot result routing.
    slot_serials = {
        stc.slot.slot_index: stc.slot.serial_number
        for stc in slot_test_ctxs.values()
        if stc.slot.serial_number
    }
    reporter = getattr(request.config, "_concord_reporter", None)
    if reporter and slot_serials:
        reporter._slot_serials = slot_serials
        log.info("Slot→serial mapping for reporter: %s", slot_serials)
    if slot_target_ids:
        log.info("Slot→targetId mapping for telemetry: %s", slot_target_ids)

    yield fctx

    # Teardown: disconnect per-slot services, stop telemetry, disconnect MTIB
    for stc in slot_test_ctxs.values():
        try:
            stc.disconnect()
        except Exception as e:
            log.warning("Error disconnecting slot test context: %s", e)
    if telemetry:
        try:
            telemetry.stop()
        except Exception as e:
            log.warning("Error stopping telemetry: %s", e)
    fctx.disconnect_all()


@pytest.fixture(params=_get_slot_ids())
def slot(fixture_ctx, request):
    """Per-slot fixture — parametrizes tests across all DUT slots.

    Returns a SlotTestContext (with UART/power) if available,
    otherwise the raw SlotContext. Tests can use slot.mtib,
    slot.shared_data, slot.serial_number etc. either way.
    """
    slot_id = request.param
    if slot_id not in fixture_ctx.slots:
        pytest.skip(f"Slot {slot_id} not configured in fixture context")

    # Prefer the rich SlotTestContext if available
    slot_test_ctxs = getattr(fixture_ctx, "_slot_test_contexts", {})
    if slot_id in slot_test_ctxs:
        return slot_test_ctxs[slot_id]
    return fixture_ctx.slots[slot_id]


@pytest.fixture(scope="session")
def stage_assets():
    """Session-scoped firmware assets resolved from the build run.

    When BUILD_RUN_ID is set (injected by K8s Job), provides typed
    access to firmware artifacts via StageAssets and BuildAsset:

        hex_path = stage_assets.hex("app", "debug")
        app, comms = stage_assets.hex_pair("debug")
        version = stage_assets.by_label("smoke_app_debug").version()

    Returns None if BUILD_RUN_ID is not set (manual run).
    """
    build_run_id = os.environ.get("BUILD_RUN_ID")
    if not build_run_id:
        log.info("BUILD_RUN_ID not set — stage_assets returning None")
        yield None
        return

    api_url = os.environ.get("CONCORD_API_URL", "")
    api_key = os.environ.get("CONCORD_API_KEY", "")
    stage = os.environ.get("STAGE", "fuota")

    try:
        from corekinect.test.stage_assets import StageAssets

        assets = StageAssets.from_build_run(
            build_run_id=build_run_id,
            stage=stage,
            api_url=api_url,
            api_key=api_key,
            strict=False,
        )
        log.info(
            "StageAssets loaded: build_run=%s, stage=%s, labels=%s",
            build_run_id, stage, assets.labels,
        )
        yield assets
        assets.cleanup()
    except Exception as exc:
        log.error("Failed to initialize StageAssets: %s", exc)
        yield None


@pytest.fixture
def report(request: pytest.FixtureRequest):
    """Active ConcordReporter or NoOpReporter for offline/local runs.

    Usage in tests::

        def test_boot(report, dut):
            with report.step("Power on"):
                dut.power_enable(0, 4.5)

            with report.step("Verify current"):
                assert dut.read_current() > 5.0
    """
    from corekinect.test.reporter import NoOpReporter

    reporter = getattr(request.config, "_concord_reporter", None)
    if reporter is None:
        return NoOpReporter()
    return reporter


@pytest.fixture(autouse=True)
def _test_lifecycle(request: pytest.FixtureRequest):
    """Per-test setup/teardown — auto-applied to every test.

    When the test uses ``ctx`` (single-slot validation):
        Before: clears UART buffer, marks test start for cloud polling
        After: dumps UART logs, uploads artifacts

    When the test uses ``slot`` (multi-slot manufacturing/validation):
        Before: sets reporter device to slot SNR, clears per-slot UART
        After: dumps per-slot UART logs to artifacts directory

    No-op for tests that don't use either context fixture.
    """
    has_ctx = "ctx" in request.fixturenames
    has_slot = "slot" in request.fixturenames

    if not has_ctx and not has_slot:
        yield
        return

    test_name = request.node.name
    module_name = None
    if hasattr(request.node, "module") and request.node.module:
        mod_name = getattr(request.node.module, "__name__", "")
        if "." in mod_name:
            module_name = mod_name.rsplit(".", 1)[-1]

    # ── Setup ──
    if has_ctx:
        ctx = request.getfixturevalue("ctx")
        ctx.setup_test(test_name=test_name, module=module_name)

    elif has_slot:
        slot_val = request.getfixturevalue("slot")
        # Tag reporter with this slot's serial number for RunTarget mapping
        reporter = getattr(request.config, "_concord_reporter", None)
        if reporter and hasattr(slot_val, "serial_number") and slot_val.serial_number:
            reporter.set_device(slot_val.serial_number)
        # Clear per-slot UART if SlotTestContext
        if hasattr(slot_val, "setup_test"):
            slot_val.setup_test(test_name=test_name, module=module_name)

    yield

    # ── Teardown ──
    artifacts_dir = os.environ.get("ARTIFACTS_DIR")

    if has_ctx:
        ctx = request.getfixturevalue("ctx")
        ctx.teardown_test(test_name, artifacts_dir)
        if artifacts_dir and ctx.artifacts.enabled:
            uart_log = os.path.join(artifacts_dir, f"{test_name}_uart.log")
            if os.path.isfile(uart_log):
                ctx.artifacts.upload(uart_log, f"{test_name}_uart.log")

    elif has_slot and artifacts_dir:
        slot_val = request.getfixturevalue("slot")
        if hasattr(slot_val, "teardown_test"):
            slot_val.teardown_test(test_name, artifacts_dir)


# ═══════════════════════════════════════════════════════════════════════════
# Per-slot cascade failure tracking
# ═══════════════════════════════════════════════════════════════════════════

# Tracks which slots have failed, keyed by slot_id.
# When a test fails for a slot, all remaining tests for that slot are skipped.
# This gives per-slot independence: slot-0 can pass while slot-2 fails.
_slot_failures: dict = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Record per-slot test failures for cascade skipping.

    When a multi-slot test (parametrized by slot) fails, record the failure
    so subsequent tests for the same slot are auto-skipped. Other slots
    are unaffected.
    """
    outcome = yield
    report = outcome.get_result()

    # Only track call-phase failures (not setup/teardown)
    if report.when != "call" or not report.failed:
        return

    # Extract slot ID from the test's parametrize suffix: [slot-N]
    import re as _re
    m = _re.search(r"\[slot-(\d+)\]", item.nodeid)
    if not m:
        return

    slot_id = f"slot-{m.group(1)}"
    # Extract module (stage) from the file path
    parts = item.nodeid.split("::")
    module = None
    if len(parts) >= 2:
        file_part = parts[0]
        if "/" in file_part:
            file_part = file_part.rsplit("/", 1)[-1]
        if file_part.endswith(".py"):
            module = file_part[:-3]

    _slot_failures[slot_id] = {
        "failed_test": item.name,
        "module": module,
    }
    log.info("Cascade: slot %s failed at %s (module=%s) — remaining tests for this slot will skip", slot_id, item.name, module)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip tests for slots that have already failed.

    This gives manufacturing per-slot independence: if slot-2 fails during
    firmware flash, all remaining tests for slot-2 (flash + POST) are
    skipped, but slots 0, 1, 3 continue independently.
    """
    import re as _re
    m = _re.search(r"\[slot-(\d+)\]", item.nodeid)
    if not m:
        return

    slot_id = f"slot-{m.group(1)}"
    failure = _slot_failures.get(slot_id)
    if not failure:
        return

    # This slot has a recorded failure — skip this test
    pytest.skip(
        f"Skipped: {slot_id} failed at {failure['failed_test']} "
        f"(stage {failure['module']})"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Mock context builders
# ═══════════════════════════════════════════════════════════════════════════


def _build_mock_validation_context(manifest: "Manifest"):
    """Build a TestContext with all-mock components for offline testing.

    Mirrors the mock setup from the Alpha validation conftest but
    driven by the manifest's product config.
    """
    from corekinect.test.context import TestContext

    # Late imports — these may not be installed in all environments
    try:
        from corekinect.test.mock_cloud import MockCloudClient
        from corekinect.test.mock_hardware import (
            MockFixtureController,
            MockPowerProfiler,
            MockUartDemuxer,
        )
    except ImportError as exc:
        pytest.skip(f"Mock mode dependencies not available: {exc}")

    device_id_hex = os.environ.get("DEVICE_ID", "0000")
    device_id = int(device_id_hex, 16)

    cloud = MockCloudClient(device_id=device_id)
    fixture_ctrl = MockFixtureController()
    uart = MockUartDemuxer()
    power = MockPowerProfiler()

    # Load product context from Concord API if available
    product_ctx = None
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")
    product_slug = manifest.product.slug
    if api_url and api_key and product_slug:
        try:
            from corekinect.test.runner import ProductContext
            product_ctx = ProductContext.from_api(product_slug, api_url, api_key)
        except Exception:
            pass

    if not product_ctx:
        try:
            from corekinect.test.runner import ProductContext
            parts = product_slug.rsplit("_", 1)
            name = parts[0] if len(parts) == 2 else product_slug
            board = parts[1] if len(parts) == 2 else manifest.product.board
            product_ctx = ProductContext.default(name, board)
        except Exception:
            pass

    log.info("Mock mode: device_id=%s, product=%s", device_id_hex, product_slug)

    return TestContext(
        mtib=None,
        cloud=cloud,
        fixture=fixture_ctrl,
        uart=uart,
        power=power,
        product=product_ctx,
    )


def _build_mock_fixture_context():
    """Build a FixtureContext with mock MTIB clients for manufacturing."""
    from collections import namedtuple
    from corekinect.test.slot import FixtureContext, SlotContext

    class MockMtibClient:
        """Minimal MTIB stub for mock-mode manufacturing tests."""

        def connect(self):
            return None

        def disconnect(self):
            return None

        def HealthCheck(self):
            return True, [], None

        def PowerEnable(self, *a, **kw):
            return None

        def PowerDisable(self, *a, **kw):
            return None

        def GpioConfig(self, *a, **kw):
            return None

        def GpioWrite(self, *a, **kw):
            return None

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
    return FixtureContext(slots=slots, config={})
