"""Capability-based test skipping for pytest.

Tests skip gracefully when the fixture lacks required hardware.
Capabilities are plain strings (e.g., "button", "ppg_servo") defined
in product fixture YAML.

    @requires_capability("button")
    def test_button_press(fixture):
        fixture.press_button()

    class TestBiometric:
        @requires_capability("ppg_servo", "ppg_led")
        def test_on_skin(self):
            self.ctx.fixture.simulate_on_skin(True)
"""

import functools
from typing import Callable, List, Optional

import pytest


def _find_fixture(func: Callable, args: tuple, kwargs: dict):
    """Find fixture controller from test args/kwargs. Returns None if not found."""
    # Direct fixture kwargs
    fixture = (
        kwargs.get("fixture")
        or kwargs.get("validation_fixture")
        or kwargs.get("fixture_controller")
    )
    if fixture is not None:
        return fixture

    # ctx kwarg
    ctx = kwargs.get("ctx")
    if ctx is not None and hasattr(ctx, "fixture"):
        return ctx.fixture

    # Class-based test: self is args[0], may have self.ctx
    if args and hasattr(args[0], "ctx"):
        ctx = args[0].ctx
        if ctx is not None and hasattr(ctx, "fixture"):
            return ctx.fixture

    # Positional args by parameter name (fallback)
    try:
        import inspect
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        for i, param in enumerate(params):
            if param in ("fixture", "validation_fixture", "fixture_controller"):
                if i < len(args):
                    return args[i]
            elif param == "ctx" and i < len(args):
                obj = args[i]
                if hasattr(obj, "fixture"):
                    return obj.fixture
    except (ValueError, TypeError):
        pass

    return None


def _cap_to_str(cap) -> str:
    """Convert a capability to a string. Accepts str or Capability enum."""
    return cap.value if hasattr(cap, "value") else str(cap)


def requires_capability(*caps: str) -> Callable:
    """Skip test if fixture lacks any of the listed capabilities.

    Works with function-based tests, class-based tests with fixture/ctx
    params, and class-based tests with self.ctx.

    Args:
        *caps: Capability strings (e.g., "button", "ppg_servo").
    """
    cap_strings = [_cap_to_str(c) for c in caps]

    def decorator(func: Callable) -> Callable:
        """Wrap func to skip if fixture lacks required capabilities."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Invoke the wrapped test, skipping if capabilities are missing."""
            fixture = _find_fixture(func, args, kwargs)

            if fixture is None:
                return func(*args, **kwargs)

            # Check capabilities — try has() first (new API), fall back to has_capability()
            missing = []
            for cap_str in cap_strings:
                if hasattr(fixture, "has"):
                    if not fixture.has(cap_str):
                        missing.append(cap_str)
                elif hasattr(fixture, "has_capability"):
                    if not fixture.has_capability(cap_str):
                        missing.append(cap_str)

            if missing:
                missing_str = ", ".join(missing)
                pytest.skip(f"Fixture lacks capabilities: {missing_str}")

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
