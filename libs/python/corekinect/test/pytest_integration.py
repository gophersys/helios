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
import warnings
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
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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


def requires_feature(feature) -> Callable:
    """Deprecated. Use @requires_capability with string capabilities instead."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                "requires_feature is deprecated. Use @requires_capability with strings.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        wrapper._required_feature = feature
        return wrapper

    return decorator


def get_required_capabilities(func: Callable) -> List[str]:
    """Return list of required capability strings from a decorated function."""
    return getattr(func, "_required_capabilities", [])


def get_required_feature(func: Callable) -> Optional[str]:
    """Return required feature string from a decorated function, or None."""
    return getattr(func, "_required_feature", None)
