"""Tests for pytest integration decorators.

Tests the @requires_capability and @requires_feature decorators.
"""

import pytest

from corekinect.test.profiles import (
    Capability,
    Feature,
    DeviceProfile,
    ValidationConfig,
)
from corekinect.test.programmable_fixture import (
    ProgrammableFixture,
    FixtureBuilder,
)
from corekinect.test.pytest_integration import (
    requires_capability,
    requires_feature,
    get_required_capabilities,
    get_required_feature,
)


class TestRequiresCapabilityDecorator:
    """Tests for @requires_capability decorator."""

    def test_passes_when_capability_present(self):
        """Test runs when fixture has required capability."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .build()
        )

        results = []

        @requires_capability(Capability.BUTTON)
        def test_func(fixture):
            results.append("ran")
            return True

        result = test_func(fixture=fixture)

        assert result is True
        assert results == ["ran"]

    def test_skips_when_capability_missing(self):
        """Test is skipped when fixture lacks capability."""
        fixture = FixtureBuilder().build()  # No capabilities

        @requires_capability(Capability.BUTTON)
        def test_func(fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(fixture=fixture)

        assert "button" in str(exc_info.value).lower()

    def test_multiple_capabilities_all_present(self):
        """Test runs when all required capabilities present."""
        fixture = (
            FixtureBuilder()
            .with_capabilities(Capability.PPG_SERVO, Capability.PPG_LED)
            .build()
        )

        ran = []

        @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
        def test_func(fixture):
            ran.append(True)

        test_func(fixture=fixture)
        assert ran == [True]

    def test_multiple_capabilities_one_missing(self):
        """Test skips when any required capability missing."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.PPG_SERVO)
            .build()
        )

        @requires_capability(Capability.PPG_SERVO, Capability.PPG_LED)
        def test_func(fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(fixture=fixture)

        assert "ppg_led" in str(exc_info.value).lower()

    def test_finds_fixture_in_positional_args(self):
        """Decorator finds fixture when passed positionally."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .build()
        )

        ran = []

        @requires_capability(Capability.BUTTON)
        def test_func(fixture):
            ran.append(True)

        test_func(fixture)  # positional arg
        assert ran == [True]

    def test_stores_requirements_on_function(self):
        """Capability requirements are stored on decorated function."""
        @requires_capability(Capability.BUTTON, Capability.PELTIER)
        def test_func(fixture):
            pass

        caps = get_required_capabilities(test_func)
        assert Capability.BUTTON in caps
        assert Capability.PELTIER in caps

    def test_runs_without_fixture_arg(self):
        """Test runs if no fixture argument found."""
        ran = []

        @requires_capability(Capability.BUTTON)
        def test_func():
            ran.append(True)

        test_func()
        assert ran == [True]

    def test_finds_fixture_via_ctx_pattern(self):
        """Decorator finds fixture via ctx.fixture (Stage 4 test pattern)."""
        fixture = (
            FixtureBuilder()
            .with_capability(Capability.BUTTON)
            .build()
        )

        # Simulate TestContext with .fixture attribute
        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.fixture = fixture

        ran = []

        @requires_capability(Capability.BUTTON)
        def test_func(ctx, firmware_build):
            ran.append(True)

        test_func(ctx=ctx, firmware_build="debug")
        assert ran == [True]

    def test_skips_via_ctx_pattern_when_missing(self):
        """Decorator skips via ctx.fixture when capability missing."""
        fixture = FixtureBuilder().build()  # No capabilities

        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.fixture = fixture

        @requires_capability(Capability.BUTTON)
        def test_func(ctx, firmware_build):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception):
            test_func(ctx=ctx, firmware_build="debug")


class TestRequiresFeatureDecorator:
    """Tests for @requires_feature decorator."""

    @pytest.fixture
    def full_device(self) -> DeviceProfile:
        """Device with all features."""
        return DeviceProfile(
            product="alpha",
            revision="b0",
            features={
                Feature.POWER,
                Feature.BUTTON,
                Feature.BIOMETRIC,
                Feature.MOTION,
            },
        )

    @pytest.fixture
    def limited_device(self) -> DeviceProfile:
        """Device with limited features."""
        return DeviceProfile(
            product="alpha",
            revision="a0",
            features={Feature.POWER, Feature.BUTTON},
        )

    def test_passes_when_feature_testable(self, full_device):
        """Test runs when feature is testable."""
        fixture = (
            FixtureBuilder()
            .with_capabilities(Capability.PPG_SERVO, Capability.PPG_LED)
            .build()
        )
        config = ValidationConfig(device=full_device, fixture=fixture.profile)

        ran = []

        @requires_feature(Feature.BIOMETRIC)
        def test_func(validation_config, fixture):
            ran.append(True)

        test_func(validation_config=config, fixture=fixture)
        assert ran == [True]

    def test_skips_when_device_lacks_feature(self, limited_device):
        """Test skips when device doesn't support feature."""
        fixture = (
            FixtureBuilder()
            .with_capabilities(Capability.PPG_SERVO, Capability.PPG_LED)
            .build()
        )
        config = ValidationConfig(device=limited_device, fixture=fixture.profile)

        @requires_feature(Feature.BIOMETRIC)
        def test_func(validation_config, fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(validation_config=config, fixture=fixture)

        assert "does not support" in str(exc_info.value).lower()

    def test_skips_when_fixture_lacks_capability(self, full_device):
        """Test skips when fixture lacks required capability for feature."""
        fixture = FixtureBuilder().build()  # No PPG capabilities
        config = ValidationConfig(device=full_device, fixture=fixture.profile)

        @requires_feature(Feature.BIOMETRIC)
        def test_func(validation_config, fixture):
            pytest.fail("Should not run")

        with pytest.raises(pytest.skip.Exception) as exc_info:
            test_func(validation_config=config, fixture=fixture)

        assert "lacks capabilities" in str(exc_info.value).lower()

    def test_stores_feature_on_function(self):
        """Feature requirement is stored on decorated function."""
        @requires_feature(Feature.BIOMETRIC)
        def test_func(validation_config):
            pass

        feature = get_required_feature(test_func)
        assert feature == Feature.BIOMETRIC

    def test_fallback_to_capability_check(self, full_device):
        """Falls back to capability check if no config provided."""
        fixture = (
            FixtureBuilder()
            .with_capabilities(Capability.PPG_SERVO, Capability.PPG_LED)
            .build()
        )

        ran = []

        @requires_feature(Feature.BIOMETRIC)
        def test_func(fixture):
            ran.append(True)

        # No validation_config provided, should fall back to capability check
        test_func(fixture=fixture)
        assert ran == [True]


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
        @requires_capability(Capability.BUTTON)
        def my_test_function(fixture):
            """My docstring."""
            pass

        assert my_test_function.__name__ == "my_test_function"
        assert my_test_function.__doc__ == "My docstring."
