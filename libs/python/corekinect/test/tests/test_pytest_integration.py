"""Tests for pytest integration decorators.

Tests the @requires_capability decorator with string capabilities.
"""

import pytest

from corekinect.test.pytest_integration import (
    requires_capability,
    get_required_capabilities,
    get_required_feature,
)


class _StubFixture:
    """Minimal fixture stub for testing requires_capability."""

    def __init__(self, caps=None):
        self._caps = set(caps or [])

    def has(self, cap: str) -> bool:
        return cap in self._caps

    def has_capability(self, cap) -> bool:
        cap_str = cap.value if hasattr(cap, "value") else str(cap)
        return cap_str in self._caps


class TestRequiresCapabilityDecorator:
    """Tests for @requires_capability decorator."""

    def test_passes_when_capability_present(self):
        """Test runs when fixture has required capability."""
        fixture = _StubFixture(["button"])

        results = []

        @requires_capability("button")
        def test_func(fixture):
            results.append("ran")
            return True

        result = test_func(fixture=fixture)

        assert result is True
        assert results == ["ran"]

    def test_skips_when_capability_missing(self):
        """Test is skipped when fixture lacks capability."""
        fixture = _StubFixture([])

        @requires_capability("button")
        def test_func(fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(fixture=fixture)

        assert "button" in str(exc_info.value).lower()

    def test_multiple_capabilities_all_present(self):
        """Test runs when all required capabilities present."""
        fixture = _StubFixture(["ppg_servo", "ppg_led"])

        ran = []

        @requires_capability("ppg_servo", "ppg_led")
        def test_func(fixture):
            ran.append(True)

        test_func(fixture=fixture)
        assert ran == [True]

    def test_multiple_capabilities_one_missing(self):
        """Test skips when any required capability missing."""
        fixture = _StubFixture(["ppg_servo"])

        @requires_capability("ppg_servo", "ppg_led")
        def test_func(fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(fixture=fixture)

        assert "ppg_led" in str(exc_info.value).lower()

    def test_finds_fixture_in_positional_args(self):
        """Decorator finds fixture when passed positionally."""
        fixture = _StubFixture(["button"])

        ran = []

        @requires_capability("button")
        def test_func(fixture):
            ran.append(True)

        test_func(fixture)  # positional arg
        assert ran == [True]

    def test_stores_requirements_on_function(self):
        """Capability requirements are stored on decorated function."""
        @requires_capability("button", "peltier")
        def test_func(fixture):
            pass

        caps = get_required_capabilities(test_func)
        assert "button" in caps
        assert "peltier" in caps

    def test_runs_without_fixture_arg(self):
        """Test runs if no fixture argument found."""
        ran = []

        @requires_capability("button")
        def test_func():
            ran.append(True)

        test_func()
        assert ran == [True]

    def test_finds_fixture_via_ctx_pattern(self):
        """Decorator finds fixture via ctx.fixture (Stage 4 test pattern)."""
        fixture = _StubFixture(["button"])

        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.fixture = fixture

        ran = []

        @requires_capability("button")
        def test_func(ctx, firmware_build):
            ran.append(True)

        test_func(ctx=ctx, firmware_build="debug")
        assert ran == [True]

    def test_skips_via_ctx_pattern_when_missing(self):
        """Decorator skips via ctx.fixture when capability missing."""
        fixture = _StubFixture([])

        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.fixture = fixture

        @requires_capability("button")
        def test_func(ctx, firmware_build):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception):
            test_func(ctx=ctx, firmware_build="debug")


class TestIntrospectionHelpers:
    """Tests for introspection helper functions."""

    def test_get_required_capabilities_empty(self):
        """Returns empty list for undecorated function."""
        def plain_func():
            pass

        assert get_required_capabilities(plain_func) == []

    def test_get_required_feature_none(self):
        """Returns None for undecorated function."""
        def plain_func():
            pass

        assert get_required_feature(plain_func) is None

    def test_preserves_function_metadata(self):
        """Decorators preserve original function metadata."""
        @requires_capability("button")
        def my_test_function(fixture):
            """My docstring."""
            pass

        assert my_test_function.__name__ == "my_test_function"
        assert my_test_function.__doc__ == "My docstring."
