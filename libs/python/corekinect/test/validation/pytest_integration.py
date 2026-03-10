"""Pytest integration for capability-based test skipping.

Provides decorators and fixtures that integrate the capability system
with pytest's skip/xfail mechanisms.

Usage:
    from corekinect.test.validation.pytest_integration import (
        requires_capability,
        requires_feature,
    )

    @requires_capability(Capability.BUTTON)
    def test_button_press(fixture):
        fixture.press_button()
        ...

    @requires_feature(Feature.BIOMETRIC)
    def test_on_skin_detection(fixture, cloud):
        fixture.simulate_on_skin(True)
        ...
"""

import functools
from typing import Callable, List, Union

import pytest

from .profiles import Capability, Feature, FEATURE_REQUIREMENTS, ValidationConfig


def requires_capability(*caps: Capability) -> Callable:
    """Decorator that skips tests if fixture lacks required capabilities.

    Usage:
        @requires_capability(Capability.BUTTON)
        def test_button_press(fixture):
            ...

        @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
        def test_biometric(fixture):
            ...

    The fixture must be provided as a pytest fixture named 'fixture',
    'validation_fixture', or 'fixture_controller', and must have a
    `has_capability()` method.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find fixture in kwargs - check direct fixtures first
            fixture = kwargs.get('fixture') or kwargs.get('validation_fixture') or kwargs.get('fixture_controller')

            # Also check for TestContext (ctx) which has .fixture attribute
            if fixture is None:
                ctx = kwargs.get('ctx')
                if ctx is not None and hasattr(ctx, 'fixture'):
                    fixture = ctx.fixture

            if fixture is None:
                # Try to find in args via inspection
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                for i, param in enumerate(params):
                    if param in ('fixture', 'validation_fixture', 'fixture_controller'):
                        if i < len(args):
                            fixture = args[i]
                            break
                    elif param == 'ctx':
                        if i < len(args):
                            ctx = args[i]
                            if hasattr(ctx, 'fixture'):
                                fixture = ctx.fixture
                            break

            if fixture is None:
                # Can't find fixture, just run the test
                return func(*args, **kwargs)

            # Check capabilities
            missing = []
            for cap in caps:
                if not fixture.has_capability(cap):
                    missing.append(cap)

            if missing:
                missing_str = ", ".join(c.value for c in missing)
                pytest.skip(f"Fixture lacks capabilities: {missing_str}")

            return func(*args, **kwargs)

        # Store capability requirements on the function for introspection
        wrapper._required_capabilities = list(caps)
        return wrapper

    return decorator


def requires_feature(feature: Feature) -> Callable:
    """Decorator that skips tests if feature cannot be tested.

    A feature can be tested if:
    1. The device supports the feature
    2. The fixture has all required capabilities

    Usage:
        @requires_feature(Feature.BIOMETRIC)
        def test_on_skin_detection(validation_config, fixture):
            ...

    The validation_config must be provided as a pytest fixture and must
    be a ValidationConfig instance.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find validation_config in kwargs
            config = kwargs.get('validation_config')

            if config is None:
                # Try to find in args via inspection
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                for i, param in enumerate(params):
                    if param == 'validation_config':
                        if i < len(args):
                            config = args[i]
                            break

            if config is None:
                # Can't find config, fallback to capability check
                required_caps = FEATURE_REQUIREMENTS.get(feature, [])
                if required_caps:
                    # Apply capability check as fallback
                    return requires_capability(*required_caps)(func)(*args, **kwargs)
                return func(*args, **kwargs)

            # Check if feature is testable
            skip_reason = config.skip_reason(feature)
            if skip_reason:
                pytest.skip(skip_reason)

            return func(*args, **kwargs)

        # Store feature requirement on the function for introspection
        wrapper._required_feature = feature
        return wrapper

    return decorator


class CapabilitySkipMarker:
    """Pytest marker for capability requirements.

    Usage with pytest.mark:
        @pytest.mark.requires_capability(Capability.BUTTON)
        def test_button():
            ...

    This requires registering a pytest hook to process the marker.
    For most cases, use the @requires_capability decorator instead.
    """

    @staticmethod
    def pytest_configure(config):
        """Register custom markers."""
        config.addinivalue_line(
            "markers",
            "requires_capability(*caps): skip test if fixture lacks capabilities",
        )
        config.addinivalue_line(
            "markers",
            "requires_feature(feature): skip test if feature cannot be tested",
        )


def get_required_capabilities(func: Callable) -> List[Capability]:
    """Get capability requirements from a decorated function."""
    return getattr(func, '_required_capabilities', [])


def get_required_feature(func: Callable) -> Union[Feature, None]:
    """Get feature requirement from a decorated function."""
    return getattr(func, '_required_feature', None)
