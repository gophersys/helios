"""Capability-based test skipping for pytest.

Tests skip gracefully when the testbed lacks required hardware.
Capabilities are plain strings (e.g., "button", "ppg_servo") defined
in product testbed YAML.

    @requires_capability("button")
    def test_button_press(testbed):
        testbed.press_button()

    class TestBiometric:
        @requires_capability("ppg_servo", "ppg_led")
        def test_on_skin(self):
            self.ctx.testbed.simulate_on_skin(True)
"""

import functools
import inspect
from typing import Callable, List, Optional

import pytest


def _find_testbed(func: Callable, args: tuple, kwargs: dict):
    """Find the TestBed instance from a test's args/kwargs. Returns None if not found.

    Looks up under "testbed" first (the post-rename canonical name), then
    falls back to "fixture" / "validation_fixture" for legacy callers.
    """
    testbed = kwargs.get("testbed") or kwargs.get("fixture") or kwargs.get("validation_fixture")
    if testbed is not None:
        return testbed

    ctx = kwargs.get("ctx")
    if ctx is not None:
        if hasattr(ctx, "testbed"):
            return ctx.testbed
        if hasattr(ctx, "fixture"):
            return ctx.fixture

    if args and hasattr(args[0], "ctx"):
        ctx = args[0].ctx
        if ctx is not None:
            if hasattr(ctx, "testbed"):
                return ctx.testbed
            if hasattr(ctx, "fixture"):
                return ctx.fixture

    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        for i, param in enumerate(params):
            if param in ("testbed", "fixture", "validation_fixture"):
                if i < len(args):
                    return args[i]
            elif param == "ctx" and i < len(args):
                obj = args[i]
                if hasattr(obj, "testbed"):
                    return obj.testbed
                if hasattr(obj, "fixture"):
                    return obj.fixture
    except (ValueError, TypeError):
        pass

    return None


# Back-compat alias — old callers may have imported _find_fixture directly.
_find_fixture = _find_testbed


def _cap_to_str(cap) -> str:
    """Convert a capability to a string. Accepts str or Capability enum."""
    return cap.value if hasattr(cap, "value") else str(cap)


def requires_capability(*caps: str) -> Callable:
    """Skip test if testbed lacks any of the listed capabilities.

    Works with function-based tests, class-based tests with testbed/ctx
    params, and class-based tests with self.ctx.

    Args:
        *caps: Capability strings (e.g., "button", "ppg_servo").
    """
    cap_strings = [_cap_to_str(c) for c in caps]

    def decorator(func: Callable) -> Callable:
        """Wrap func to skip if testbed lacks required capabilities."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Invoke the wrapped test, skipping if capabilities are missing."""
            testbed = _find_testbed(func, args, kwargs)

            if testbed is None:
                return func(*args, **kwargs)

            # Check capabilities — try has() first (new API), fall back to has_capability()
            missing = []
            for cap_str in cap_strings:
                if hasattr(testbed, "has"):
                    if not testbed.has(cap_str):
                        missing.append(cap_str)
                elif hasattr(testbed, "has_capability"):
                    if not testbed.has_capability(cap_str):
                        missing.append(cap_str)

            if missing:
                missing_str = ", ".join(missing)
                pytest.skip(f"TestBed lacks capabilities: {missing_str}")

            return func(*args, **kwargs)

        wrapper._required_capabilities = list(cap_strings)
        return wrapper

    return decorator



def get_required_capabilities(func: Callable) -> List[str]:
    """Return list of required capability strings from a decorated function."""
    return getattr(func, "_required_capabilities", [])


def get_required_feature(func: Callable) -> Optional[str]:
    """Return required feature string from a decorated function, or None."""
    return getattr(func, "_required_feature", None)


# ────────────────────────────────────────────────────────────────────────
# @pytest.mark.mfg_stage(...) — compound marker (Phase 4)
# ────────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``mfg_stage`` compound marker.

    Manufacturing tests today carry three decorators each
    (``@pytest.mark.<stage>`` + ``@pytest.mark.sequential`` +
    ``@pytest.mark.timeout(N)``). The ``mfg_stage`` compound rolls
    them into one:

        @pytest.mark.mfg_stage("electrical", timeout=30)
        def test_01_uvlo(slot, config, report): ...

    Expansion happens at collection time in
    :func:`pytest_collection_modifyitems` so the rest of the
    pipeline (slot_parallel grouping, sequential plugin, soft
    per-test timer) sees the same three markers as today.
    """
    config.addinivalue_line(
        "markers",
        "mfg_stage(name, timeout=None): manufacturing-stage compound — "
        "expands to @pytest.mark.<name> + @pytest.mark.sequential + "
        "@pytest.mark.timeout(timeout) at collection time",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Expand each ``mfg_stage`` marker into its three constituent markers.

    Idempotent: an item that already carries one of the constituent
    markers (e.g. someone wrote both ``mfg_stage`` and the legacy
    ``@pytest.mark.electrical``) is not re-marked. ``tryfirst=True`` so
    the expansion runs before any plugin that consumes the markers
    (slot_parallel groups by stage marker, the sequential plugin
    uses ``sequential``).
    """
    for item in items:
        compound = item.get_closest_marker("mfg_stage")
        if compound is None:
            continue
        if not compound.args:
            continue  # malformed; corectl validate should have caught it
        stage_name = compound.args[0]
        timeout_value = compound.kwargs.get("timeout")

        existing = {m.name for m in item.iter_markers()}
        if stage_name not in existing:
            item.add_marker(getattr(pytest.mark, stage_name))
        if "sequential" not in existing:
            item.add_marker(pytest.mark.sequential)
        if timeout_value is not None and "timeout" not in existing:
            item.add_marker(pytest.mark.timeout(timeout_value))
