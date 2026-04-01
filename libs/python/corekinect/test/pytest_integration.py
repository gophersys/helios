"""Pytest integration for capability-based test skipping.

Provides decorators that integrate the capability system with pytest's
skip mechanism. Tests decorated with @requires_capability will skip
gracefully when the fixture lacks required hardware — never crash.

The decorators work with ALL test patterns:
  - Function-based: def test_foo(fixture): ...
  - Class-based with fixture param: def test_foo(self, fixture): ...
  - Class-based with ctx: def test_foo(self, ctx): ...
  - Class-based with self.ctx: def test_foo(self): ... (ctx set by autouse fixture)

Usage:
    from corekinect.test.pytest_integration import requires_capability
    from corekinect.test.profiles import Capability

    @requires_capability(Capability.BUTTON)
    def test_button_press(fixture):
        fixture.press_button()

    class TestBiometric:
        @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
        def test_on_skin(self):
            self.ctx.fixture.simulate_on_skin(True)
"""

import functools
from typing import Callable, List, Optional

import pytest

from .profiles import Capability, Feature, FEATURE_REQUIREMENTS, ValidationConfig


def _find_fixture(func: Callable, args: tuple, kwargs: dict):
    """Find the FixtureController from test arguments.

    Searches in order:
    1. kwargs: fixture, validation_fixture, fixture_controller
    2. kwargs: ctx.fixture
    3. args[0].ctx.fixture (class-based test with self.ctx)
    4. args positional match by parameter name

    Returns:
        FixtureController instance, or None if not found.
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


def requires_capability(*caps: Capability) -> Callable:
    """Decorator that skips tests if fixture lacks required capabilities.

    Works with function-based tests, class-based tests with fixture/ctx
    parameters, and class-based tests with self.ctx (set by autouse fixture).

    Args:
        *caps: One or more Capability enum values required by the test.

    Usage:
        @requires_capability(Capability.BUTTON)
        def test_button_press(fixture):
            fixture.press_button()

        class TestSomething:
            @requires_capability(Capability.PPG_SERVO)
            def test_on_skin(self):
                self.ctx.fixture.simulate_on_skin(True)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            fixture = _find_fixture(func, args, kwargs)

            if fixture is None:
                # Can't find fixture — run the test and let it fail naturally
                # if it needs fixture access
                return func(*args, **kwargs)

            # Check capabilities
            missing = [
                cap for cap in caps
                if not fixture.has_capability(cap)
            ]

            if missing:
                missing_str = ", ".join(c.value for c in missing)
                pytest.skip(f"Fixture lacks capabilities: {missing_str}")

            return func(*args, **kwargs)

        # Store requirements for introspection by backend/catalog
        wrapper._required_capabilities = list(caps)
        return wrapper

    return decorator


def requires_feature(feature: Feature) -> Callable:
    """Decorator that skips tests if feature cannot be tested.

    A feature requires:
    1. The device supports it (DeviceProfile)
    2. The fixture has all required capabilities (FEATURE_REQUIREMENTS)

    Falls back to capability check if validation_config is not available.

    Args:
        feature: Feature enum value.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find validation_config
            config = kwargs.get("validation_config")

            if config is None and args:
                # Check self.validation_config for class tests
                if hasattr(args[0], "validation_config"):
                    config = args[0].validation_config

            if config is not None:
                skip_reason = config.skip_reason(feature)
                if skip_reason:
                    pytest.skip(skip_reason)
                return func(*args, **kwargs)

            # Fallback: check capabilities directly
            required_caps = FEATURE_REQUIREMENTS.get(feature, [])
            if required_caps:
                return requires_capability(*required_caps)(func)(*args, **kwargs)

            return func(*args, **kwargs)

        wrapper._required_feature = feature
        return wrapper

    return decorator


def get_required_capabilities(func: Callable) -> List[Capability]:
    """Get capability requirements from a decorated function.

    Returns:
        List of required capabilities, or empty list.
    """
    return getattr(func, "_required_capabilities", [])


def get_required_feature(func: Callable) -> Optional[Feature]:
    """Get feature requirement from a decorated function.

    Returns:
        Required feature, or None.
    """
    return getattr(func, "_required_feature", None)
