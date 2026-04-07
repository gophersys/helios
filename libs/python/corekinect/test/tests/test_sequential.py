"""Unit tests for sequential.py — SequentialTestPlugin.

Tests the plugin class directly using MagicMock objects for pytest items
and call results. No subprocess pytest runs needed.

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest libs/python/corekinect/test/tests/test_sequential.py -v
"""

from unittest.mock import MagicMock

import pytest

from corekinect.test.sequential import SequentialTestPlugin


# =============================================================================
# Helpers
# =============================================================================


def _make_class(name: str):
    """Create a simple class with __name__ set for test mocking."""
    cls = type(name, (), {})
    return cls


def _make_item(cls=None, nodeid="test_module.py::TestClass::test_func"):
    """Create a mock pytest Item with a .cls attribute."""
    item = MagicMock()
    item.cls = cls
    item.nodeid = nodeid
    return item


def _make_call(when="call", excinfo=None):
    """Create a mock pytest CallInfo."""
    call = MagicMock()
    call.when = when
    call.excinfo = excinfo
    return call


# =============================================================================
# pytest_runtest_makereport tests
# =============================================================================


class TestMakeReport:
    """Tests for failure tracking via pytest_runtest_makereport."""

    def test_failure_adds_class_to_failed_classes(self):
        """Test failure adds class to failed classes."""
        plugin = SequentialTestPlugin()
        cls = _make_class("TestSomething")
        item = _make_item(cls=cls)
        call = _make_call(when="call", excinfo=MagicMock())  # non-None excinfo = failure

        plugin.pytest_runtest_makereport(item, call)

        assert "TestSomething" in plugin._failed_classes

    def test_preflight_failure_sets_preflight_failed(self):
        """Test preflight failure sets preflight failed."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        cls = _make_class("TestPreflight")
        item = _make_item(cls=cls)
        call = _make_call(when="call", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert plugin._preflight_failed is True
        assert "TestPreflight" in plugin._failed_classes

    def test_setup_phase_failure_does_not_track(self):
        """Failures during setup (not call) should not be tracked."""
        plugin = SequentialTestPlugin()
        cls = _make_class("TestSetup")
        item = _make_item(cls=cls)
        call = _make_call(when="setup", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert "TestSetup" not in plugin._failed_classes

    def test_passing_test_does_not_track(self):
        """No excinfo means the test passed — should not be tracked."""
        plugin = SequentialTestPlugin()
        cls = _make_class("TestPass")
        item = _make_item(cls=cls)
        call = _make_call(when="call", excinfo=None)

        plugin.pytest_runtest_makereport(item, call)

        assert "TestPass" not in plugin._failed_classes

    def test_no_cls_does_not_track(self):
        """Module-level tests (no class) should not cause errors."""
        plugin = SequentialTestPlugin()
        item = _make_item(cls=None)
        call = _make_call(when="call", excinfo=MagicMock())

        # Should not raise
        plugin.pytest_runtest_makereport(item, call)
        assert len(plugin._failed_classes) == 0


# =============================================================================
# pytest_runtest_setup tests
# =============================================================================


class TestRunTestSetup:
    """Tests for skip logic in pytest_runtest_setup."""

    def test_preflight_failed_skips_non_preflight(self):
        """Test preflight failed skips non preflight."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        plugin._preflight_failed = True

        other_cls = _make_class("TestOther")
        item = _make_item(cls=other_cls)

        with pytest.raises(pytest.skip.Exception):
            plugin.pytest_runtest_setup(item)

    def test_preflight_failed_does_not_skip_preflight_class(self):
        """Test preflight failed does not skip preflight class."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        plugin._preflight_failed = True

        preflight_cls = _make_class("TestPreflight")
        item = _make_item(cls=preflight_cls)

        # Should NOT skip — preflight tests need to keep running
        # (they themselves triggered the failure, remaining tests in class
        #  are skipped by the class-level logic below, not preflight logic)
        # If it doesn't raise pytest.skip, we're good. But the class-level
        # check will catch it. Let's verify no skip from preflight logic.
        # The class IS in _failed_classes, so it WILL skip from class logic.
        # To isolate: only set _preflight_failed, don't add to _failed_classes.
        plugin._failed_classes.clear()

        # Now the only skip trigger is preflight_failed,
        # and this item IS the preflight class — should not skip.
        plugin.pytest_runtest_setup(item)  # no exception expected

    def test_class_failure_skips_same_class(self):
        """Test class failure skips same class."""
        plugin = SequentialTestPlugin()
        plugin._failed_classes.add("TestFlash")

        cls = _make_class("TestFlash")
        item = _make_item(cls=cls)

        with pytest.raises(pytest.skip.Exception):
            plugin.pytest_runtest_setup(item)

    def test_class_failure_does_not_skip_different_class(self):
        """Test class failure does not skip different class."""
        plugin = SequentialTestPlugin()
        plugin._failed_classes.add("TestFlash")

        other_cls = _make_class("TestBoot")
        item = _make_item(cls=other_cls)

        # Should not skip — different class
        plugin.pytest_runtest_setup(item)

    def test_no_failures_does_not_skip(self):
        """Test no failures does not skip."""
        plugin = SequentialTestPlugin()

        cls = _make_class("TestAnything")
        item = _make_item(cls=cls)

        # No failures recorded, should not skip
        plugin.pytest_runtest_setup(item)

    def test_module_level_test_not_skipped_by_class_failure(self):
        """Module-level tests (cls=None) should not be affected by class failures."""
        plugin = SequentialTestPlugin()
        plugin._failed_classes.add("TestSomething")

        item = _make_item(cls=None)

        # cls is None, so class check won't match
        plugin.pytest_runtest_setup(item)


# =============================================================================
# pytest_configure tests
# =============================================================================


class TestPytestConfigure:
    """Tests for keyword amendment in pytest_configure."""

    def test_keyword_without_preflight_gets_amended(self):
        """Test keyword without preflight gets amended."""
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = "test_flash"

        plugin.pytest_configure(config)

        assert config.option.keyword == "(test_00_preflight) or (test_flash)"

    def test_keyword_already_containing_preflight_unchanged(self):
        """Test keyword already containing preflight unchanged."""
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = "test_00_preflight or test_flash"

        plugin.pytest_configure(config)

        # Should not be modified since it already contains preflight
        assert config.option.keyword == "test_00_preflight or test_flash"

    def test_no_keyword_leaves_config_unchanged(self):
        """Test no keyword leaves config unchanged."""
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = None

        plugin.pytest_configure(config)

        assert config.option.keyword is None

    def test_empty_keyword_leaves_config_unchanged(self):
        """Test empty keyword leaves config unchanged."""
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = ""

        plugin.pytest_configure(config)

        # Empty string is falsy, so no amendment
        assert config.option.keyword == ""
