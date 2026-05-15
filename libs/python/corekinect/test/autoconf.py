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
    - No concord.yaml found (silent no-op)
    - MTIB/hardware env vars missing (the ``slot`` fixture skips with pytest.skip)

Test-author surface:
    The canonical fixtures used by tests are ``slot`` (per-DUT context,
    parametrized across slots) and ``report`` (reporter for events).
    ``ctx`` and ``fixture_ctx`` are session-scoped contexts that the
    framework uses internally and are rarely used directly by tests.

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
import warnings
from pathlib import Path
from typing import Any, List, Optional, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from corekinect.manifest.types import Manifest

from corekinect.manifest.loader import find_manifest, load_manifest
from corekinect.test.artifact_writer import ArtifactWriter
from corekinect.test.context import TestContext
from corekinect.test.reporter import NoOpReporter
from corekinect.test.reporter import pytest_configure as reporter_configure
from corekinect.test.runner import ProductContext
from corekinect.test.slot import TestBedContext, SlotContext, get_slot_ids_from_env
from corekinect.test.slot_binding import attach_binding
from corekinect.test.slot_env import resolve_slot_bindings, slot_bindings_by_index
from corekinect.test.stage_assets import StageAssets
from corekinect.test.telemetry import TelemetryStreamer
from corekinect.utils import Logger
from corekinect.test.errors import bad_testbed_class, missing_env_var

try:
    from corekinect.test.mock_cloud import MockCloudClient
    from corekinect.test.mock_hardware import (
        MockMtibClient,
        MockPowerProfiler,
        MockUartDemuxer,
    )
    _HAS_MOCKS = True
except ImportError:
    _HAS_MOCKS = False

log = Logger(log_name="autoconf")

# ---------------------------------------------------------------------------
# Per-session state lives on ``pytest.Config.stash`` (not module globals).
#
# Stash keys are the idiomatic way to attach typed, plugin-scoped state to a
# pytest config object. Using ``config.stash`` instead of module globals means:
#
#   * Two concurrent ``pytest.main()`` invocations in the same process (e.g.
#     pytester meta-tests) can't clobber each other's manifest.
#   * TestBeds read from ``request.config`` directly, so there's no
#     "whoever called pytest_configure first wins" race.
#   * The state is garbage-collected with the config, avoiding a cross-run
#     leak in tools that embed pytest.
#
# The reporter already uses this pattern (see ``config._concord_reporter``
# in reporter.py::pytest_configure); we mirror it here for manifest state.
# ---------------------------------------------------------------------------

_MANIFEST_KEY: pytest.StashKey["Manifest"] = pytest.StashKey()
_MANIFEST_PATH_KEY: pytest.StashKey[Path] = pytest.StashKey()
_MOCK_MODE_KEY: pytest.StashKey[bool] = pytest.StashKey()


def _get_manifest(config: pytest.Config) -> Optional["Manifest"]:
    """Return the loaded manifest from config stash, or ``None``."""
    return config.stash.get(_MANIFEST_KEY, None)


def _get_manifest_path(config: pytest.Config) -> Optional[Path]:
    """Return the manifest file path from config stash, or ``None``."""
    return config.stash.get(_MANIFEST_PATH_KEY, None)


def _get_mock_mode(config: pytest.Config) -> bool:
    """Return whether mock mode is active for this session."""
    return config.stash.get(_MOCK_MODE_KEY, False)


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


def _import_testbed_class(module_ref: str) -> Any:
    """Import a TestBed subclass from a ``module:Class`` reference.

    The format matches ``concord.yaml`` ``fixture.module``:
    ``dotted.module.path:ClassName``.

    Raises:
        ImportError: If the module cannot be found or the name doesn't exist.
    """
    if ":" not in module_ref:
        raise ImportError(
            f"Invalid fixture module reference: {module_ref!r} "
            f"— expected 'module.path:ClassName'"
        )
    module_path, class_name = module_ref.split(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ImportError(
            f"TestBed class {class_name!r} not found in module {module_path!r}"
        )
    return cls


def _maybe_register_slot_parallel(config: pytest.Config) -> None:
    """Register the slot_parallel plugin when the run targets >1 slot.

    Single-slot and standalone runs always use the default pytest loop:
    slot_parallel installs a pytest-timeout neutralizer that disables
    ``@pytest.mark.timeout`` for the standard loop, so loading it for
    single-slot would silently break per-test timeout enforcement on
    validation runs.

    Slot count comes from :func:`slot_env.resolve_slot_bindings` — the
    canonical parser used everywhere else (TestBedContext.from_env,
    autoconf._attach_slot_bindings, slot.get_slot_ids_from_env). One
    source of truth means the registration decision can never disagree
    with the bindings the rest of the framework will see at fixture
    time.
    """
    if os.environ.get("PYTEST_PARALLEL", "1") in ("0", "false", "no", "False"):
        return

    if len(resolve_slot_bindings()) <= 1:
        return

    if not config.pluginmanager.has_plugin("corekinect.test.slot_parallel"):
        config.pluginmanager.import_plugin("corekinect.test.slot_parallel")
        log.info("autoconf: slot_parallel registered")


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
    # ── 1. Find and load the manifest ──
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

    config.stash[_MANIFEST_KEY] = manifest
    config.stash[_MANIFEST_PATH_KEY] = manifest_path
    # Back-compat: historical code reads ``config._concord_manifest``;
    # keep the attribute mirrored until internal callers migrate to the
    # stash key.
    config._concord_manifest = manifest  # type: ignore[attr-defined]

    # ── 2. Mock mode ──
    # Mock fixtures (mock_hardware, mock_cloud_client) own their own
    # ``time.sleep`` shortcuts via ``monkeypatch`` — there is no global
    # patch here. Real-hardware tests get the real ``time.sleep`` even
    # when one mock-mode test ran before them in the same session.
    config.stash[_MOCK_MODE_KEY] = _is_mock_mode(config)

    # ── 3. Register the Concord reporter plugin ──
    # The reporter self-activates based on CONCORD_RUN_ID; we just ensure
    # it is imported. Registering via pluginmanager avoids duplicate
    # registration if the test app's conftest.py also lists it.
    if not config.pluginmanager.has_plugin("concord_reporter"):
        reporter_configure(config)

    # ── 3b. Register slot_parallel plugin for multi-slot manufacturing ──
    # Activated when the run targets >1 slot AND PYTEST_PARALLEL isn't
    # explicitly disabled. The plugin's own hooks no-op when the run has
    # only singleton groups (e.g., validation), so this is safe to
    # register unconditionally, but we gate here to keep the plugin
    # opt-in and debuggable from env flags.
    _maybe_register_slot_parallel(config)

    # ── 3c. Register sequential (per-slot fail-fast) plugin ──
    # If any test on slot-N fails, every remaining test on slot-N is
    # skipped from the setup phase — panel rejected early, no wasted
    # time booting known-bad DUTs.  Inline tests and other slots are
    # unaffected.  Registered unconditionally because the plugin itself
    # no-ops when a run has no ``[slot-N]`` parametrization (the pure
    # validation case already behaves this way), so there's nothing to
    # gate on.  Historically this sat in ``corekinect.test.sequential``
    # and each product had to opt in; promoting it to autoconf means
    # every framework user gets the correct manufacturing semantics
    # without touching their conftest.
    if not config.pluginmanager.has_plugin("sequential_tests"):
        config.pluginmanager.import_plugin("corekinect.test.sequential")
        log.info("autoconf: sequential registered (slot-scoped fail-fast)")

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


# ═══════════════════════════════════════════════════════════════════════════
# Collection-time attribution
# ═══════════════════════════════════════════════════════════════════════════
#
# Every pytest item parametrized by ``[slot-N]`` is tied to exactly one
# slot's hardware. The reporter, telemetry streamer, and backend target
# lookup all depend on knowing that slot-to-item mapping; previously
# each of them re-derived it from the nodeid + a session-scoped
# fixture map, creating a race where the first test on each slot
# shipped before the map was populated.
#
# We now resolve attribution ONCE at collection time and stash a
# :class:`SlotBinding` on every matching item. Downstream consumers
# read ``item.stash[SLOT_BINDING_KEY]`` and never re-parse the nodeid
# or the environment.

_SLOT_SUFFIX_RE = __import__("re").compile(r"\[slot-(\d+)\]")


def _attach_slot_bindings(items: List[pytest.Item]) -> None:
    """Stash a :class:`SlotBinding` on every parametrized item.

    Items whose nodeid does not contain ``[slot-N]`` (single-slot
    validation, unparametrized maintenance tests) are left alone —
    their reporter path uses the single-target backend fallback.

    When ``resolve_slot_bindings()`` returns empty (no ``MTIB_HOSTS``),
    this is a no-op. When a binding for a given ``slot_index`` does
    not exist (e.g. the item was collected but ``SLOT_FILTER``
    excluded the slot), the item is left unstashed — pytest itself
    limits collection via ``_get_slot_ids()`` so this is rare, but we
    handle it gracefully rather than raise.
    """
    bindings = resolve_slot_bindings()
    if not bindings:
        return

    by_index = slot_bindings_by_index(bindings)

    for item in items:
        match = _SLOT_SUFFIX_RE.search(item.nodeid)
        if not match:
            continue
        slot_index = int(match.group(1))
        binding = by_index.get(slot_index)
        if binding is None:
            continue
        attach_binding(item, binding)


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """Stash slot attribution, skip cloud tests, and reorder for variant grouping.

    Slot attribution:
        For every ``[slot-N]`` item, resolve the :class:`SlotBinding`
        from the environment once and stash it on the item. Reporter
        and telemetry read from the stash — no runtime re-derivation.

    Firmware variant grouping:
        Default pytest interleaves: test_A[debug], test_A[release], test_B[debug]...
        Reordered: test_A[debug], test_B[debug]..., test_A[release], test_B[release]...
        This reduces full flash cycles from 2*N to just 2.

    Cloud test skipping:
        Tests marked @pytest.mark.corecloud are skipped in mock mode or
        when CoreCloud DB credentials are not configured.
    """
    # Slot attribution runs unconditionally — the function is a no-op
    # when the env is unconfigured, so it doesn't need the manifest gate.
    _attach_slot_bindings(items)

    if _get_manifest(config) is None:
        return

    # ── Skip cloud-dependent tests ──
    skip_reason = None
    if _get_mock_mode(config):
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
    return get_slot_ids_from_env()


# ═══════════════════════════════════════════════════════════════════════════
# TestBeds
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def manifest(request: pytest.FixtureRequest) -> "Manifest":
    """The loaded Manifest object from concord.yaml.

    Session-scoped and read-only. Access product config, stage
    definitions, fixture controller path, etc.
    """
    loaded = _get_manifest(request.config)
    if loaded is None:
        pytest.skip("No concord.yaml manifest found — cannot provide manifest fixture")
    return loaded


@pytest.fixture(scope="session")
def ctx(request: pytest.FixtureRequest, manifest: "Manifest"):
    """Session-scoped test context — connects once, shared across all tests.

    Most tests should NOT consume this directly. Use the per-slot
    ``slot`` fixture instead — it parametrizes correctly over single
    and multi-slot fixtures and gives test code a uniform interface.
    ``ctx`` exists for the rare session-scoped needs (e.g., a fixture
    parametrize that depends on the connected hardware).

    Single-slot manifests:
        Creates a TestContext with the fixture class specified in
        concord.yaml (``fixture.module``). Connects to MTIB and
        starts UART capture, power polling, and telemetry.

    Mock mode (MOCK_MODE=1 or --mock-cloud):
        Returns a context with in-memory mocks. No hardware or network.

    Skips the entire session if required env vars are missing rather
    than raising an opaque connection error.
    """
    if _get_manifest(request.config) is None:
        pytest.skip("No concord.yaml manifest — ctx fixture unavailable")

    # Manufacturing packages use fixture_ctx, not ctx
    if manifest.testbed.multi_slot:
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
            missing_env_var(
                "MTIB_ADDRESS",
                "connect to hardware",
                alternatives=("MTIB_HOST",),
                hint="set MOCK_MODE=1 to run without hardware",
            )
        )

    device_id = os.environ.get("DEVICE_ID")
    if not device_id:
        pytest.skip(missing_env_var("DEVICE_ID", "create test context"))

    # Import and instantiate the fixture class from the manifest
    module_ref = manifest.testbed.module
    try:
        testbed_cls = _import_testbed_class(module_ref)
    except ImportError as exc:
        pytest.skip(bad_testbed_class(module_ref, exc))

    try:
        context = TestContext.from_env(
            testbed_factory=lambda mtib: testbed_cls(mtib)
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
    if _get_manifest(request.config) is None:
        pytest.skip("No concord.yaml manifest — fixture_ctx unavailable")

    _apply_cli_overrides(request.config)

    # Validate required env vars before attempting connection
    mtib_hosts = os.environ.get("MTIB_HOSTS", "").strip()
    mtib_host = os.environ.get("MTIB_HOST", "") or os.environ.get("MTIB_ADDRESS", "")
    fixture_config = os.environ.get("FIXTURE_CONFIG_PATH", "").strip()
    if not mtib_hosts and not mtib_host and not fixture_config:
        pytest.skip(
            missing_env_var(
                "MTIB_HOSTS",
                "enumerate slots",
                alternatives=("MTIB_HOST", "FIXTURE_CONFIG_PATH"),
            )
        )

    # Import the testbed controller class declared in the manifest and
    # pass it as a factory so ``slot.connect()`` can attach an instance
    # to each ``SlotContext.testbed``. Without this, every test that
    # reads ``slot.testbed`` AttributeErrors on ``None`` — the single-
    # slot path below already does this; multi-slot was forgetting to.
    module_ref = manifest.testbed.module
    try:
        testbed_cls = _import_testbed_class(module_ref)
    except ImportError as exc:
        pytest.skip(bad_testbed_class(module_ref, exc))

    fctx = TestBedContext.from_env()
    fctx.connect_all(testbed_factory=lambda mtib: testbed_cls(mtib))

    # Create telemetry streamer for live power/UART streaming to frontend
    telemetry = None
    run_id = os.environ.get("CONCORD_RUN_ID", "").strip()
    api_url = os.environ.get("CONCORD_API_URL", "").strip()
    api_key = os.environ.get("CONCORD_API_KEY", "").strip()
    if run_id and api_url and api_key:
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
    slot_target_id_env = os.environ.get("SLOT_TARGET_IDS", "").strip()
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

    # Slot attribution is resolved at collection time by
    # ``_attach_slot_bindings`` and stashed on each pytest item.
    # The reporter reads from that stash, not from a reporter-side
    # map, so there is nothing to inject here.
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


@pytest.fixture(scope="module", params=_get_slot_ids())
def slot(fixture_ctx, request):
    """Per-slot fixture — parametrizes tests across all DUT slots.

    Returns a SlotTestContext (with UART/power) if available,
    otherwise the raw SlotContext. Tests can use slot.mtib,
    slot.shared_data, slot.serial_number etc. either way.

    Scope is ``"module"`` because the underlying ``SlotTestContext`` is
    just a handle into session-scoped ``fixture_ctx`` state — there is
    nothing per-test about it. Module scope lets downstream fixtures
    (like ``booted_device``) be module-scoped too, which avoids one
    full power-cycle + dual shell-lock round-trip per test in a stage.
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
        # Attribution comes from the item's SlotBinding stash, which
        # the reporter reads directly — no per-test injection here.
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
# Mock context builders
# ═══════════════════════════════════════════════════════════════════════════


def _build_mock_validation_context(manifest: "Manifest"):
    """Build a TestContext with all-mock components for offline testing.

    The fixture is the real ``TestBed`` subclass declared by the test
    package; the difference from hardware mode is that it's bound to a
    ``MockMtibClient`` instead of a live gRPC channel.
    """
    if not _HAS_MOCKS:
        pytest.skip("Mock mode dependencies not available")

    device_id_hex = os.environ.get("DEVICE_ID", "0000")
    device_id = int(device_id_hex, 16)

    cloud = MockCloudClient(device_id=device_id)
    mock_mtib = MockMtibClient()
    try:
        testbed_cls = _import_testbed_class(manifest.testbed.module)
    except ImportError as exc:
        pytest.skip(bad_testbed_class(manifest.testbed.module, exc))
    fixture_ctrl = testbed_cls(mtib=mock_mtib)
    uart = MockUartDemuxer()
    power = MockPowerProfiler()

    # Load product context from Concord API if available
    product_ctx = None
    api_url = os.environ.get("CONCORD_API_URL")
    api_key = os.environ.get("CONCORD_API_KEY")
    product_slug = manifest.product.slug
    if api_url and api_key and product_slug:
        try:
            product_ctx = ProductContext.from_api(product_slug, api_url, api_key)
        except Exception:
            pass

    if not product_ctx:
        try:
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
    """Build a TestBedContext with mock MTIB clients for manufacturing."""
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
    return TestBedContext(slots=slots, config={})
