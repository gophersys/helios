"""Pytest integration for capability-based test skipping.

Provides decorators that integrate the capability system with pytest's
skip mechanism. Tests decorated with @requires_capability will skip
gracefully when the fixture lacks required hardware — never crash.

The decorators work with ALL test patterns:
  - Function-based: def test_foo(fixture): ...
  - Class-based with fixture param: def test_foo(self, fixture): ...
  - Class-based with ctx: def test_foo(self, ctx): ...
  - Class-based with self.ctx: def test_foo(self): ... (ctx set by autouse fixture)

Capabilities are plain strings (e.g., "button", "ppg_servo"). This decouples
product test apps from the Capability enum — products define their own
capability strings in fixture YAML.

Usage:
    from corekinect.test.pytest_integration import requires_capability

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
    """Find the fixture controller from test arguments.

    Searches in order:
    1. kwargs: fixture, validation_fixture, fixture_controller
    2. kwargs: ctx.fixture
    3. args[0].ctx.fixture (class-based test with self.ctx)
    4. args positional match by parameter name

    Returns:
        Fixture controller instance, or None if not found.
    """
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
    """Decorator that skips tests if fixture lacks required capabilities.

    Works with function-based tests, class-based tests with fixture/ctx
    parameters, and class-based tests with self.ctx (set by autouse fixture).

    Args:
        *caps: One or more capability strings (e.g., "button", "ppg_servo").
            Also accepts Capability enum values for backward compatibility.

    Usage:
        @requires_capability("button")
        def test_button_press(fixture):
            fixture.press_button()

        class TestSomething:
            @requires_capability("ppg_servo")
            def test_on_skin(self):
                self.ctx.fixture.simulate_on_skin(True)
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
    """Decorator that skips tests if feature cannot be tested.

    .. deprecated:: Use @requires_capability with string capabilities instead.
    """
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
    """Get capability requirements from a decorated function.

    Returns:
        List of required capability strings, or empty list.
    """
    return getattr(func, "_required_capabilities", [])


def get_required_feature(func: Callable) -> Optional[str]:
    """Get feature requirement from a decorated function.

    Returns:
        Required feature string, or None.
    """
    return getattr(func, "_required_feature", None)
