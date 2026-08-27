"""Unit tests for sequential.py — SequentialTestPlugin.

The plugin's contract changed from class-scoped to slot-scoped: any
test on ``slot-N`` that fails poisons ``slot-N`` for the rest of the
run, without affecting other slots. Tests here cover the failure-
tracking hook + the setup-phase skip + preflight global-block + the
-k keyword amendment.

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest libs/python/corekinect/test/tests/test_sequential.py -v
"""

from unittest.mock import MagicMock

import pytest

from corekinect.test.sequential import SequentialTestPlugin, _slot_id


# =============================================================================
# Helpers
# =============================================================================


def _make_class(name: str):
    """Create a simple class with __name__ set for test mocking."""
    cls = type(name, (), {})
    return cls


def _make_item(cls=None, nodeid="test_module.py::test_func"):
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
# _slot_id helper
# =============================================================================


class TestSlotId:
    """The nodeid → slot extraction is the only way the plugin knows
    which panel DUT a test is hitting, so its quirks deserve coverage."""

    def test_plain_slot_suffix(self):
        assert _slot_id("x.py::test_foo[slot-0]") == "slot-0"
        assert _slot_id("x.py::test_foo[slot-3]") == "slot-3"

    def test_double_digit_slot(self):
        assert _slot_id("x.py::test_foo[slot-12]") == "slot-12"

    def test_no_slot_param_returns_none(self):
        assert _slot_id("x.py::test_foo") is None
        assert _slot_id("x.py::test_foo[debug]") is None

    def test_empty_nodeid_returns_none(self):
        assert _slot_id("") is None
        assert _slot_id(None) is None

    def test_slot_inside_compound_parametrize(self):
        # When a test is parametrized on both slot AND another axis
        # pytest yields e.g. ``test_foo[slot-0-debug]`` — we still want
        # ``slot-0`` out of the front of the bracketed group.
        assert _slot_id("x.py::test_foo[slot-0-debug]") == "slot-0"


# =============================================================================
# pytest_runtest_makereport — failure tracking
# =============================================================================


class TestMakeReport:
    """Failure tracking via pytest_runtest_makereport."""

    def test_call_phase_failure_adds_slot_to_failed_slots(self):
        """A failed call-phase test on slot-N poisons slot-N."""
        plugin = SequentialTestPlugin()
        item = _make_item(nodeid="t.py::test_foo[slot-2]")
        call = _make_call(when="call", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert plugin.failed_slots == {"slot-2"}

    def test_only_the_failing_slot_is_poisoned(self):
        """A failure on slot-2 must not affect slot-0 / slot-1."""
        plugin = SequentialTestPlugin()
        item = _make_item(nodeid="t.py::test_foo[slot-2]")
        plugin.pytest_runtest_makereport(item, _make_call(when="call", excinfo=MagicMock()))

        assert "slot-0" not in plugin.failed_slots
        assert "slot-1" not in plugin.failed_slots
        assert "slot-2" in plugin.failed_slots

    def test_setup_phase_failure_does_not_track(self):
        """TestBed setup failures cascade via pytest's own machinery;
        double-counting them here would mask fixture bugs."""
        plugin = SequentialTestPlugin()
        item = _make_item(nodeid="t.py::test_foo[slot-0]")
        call = _make_call(when="setup", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert plugin.failed_slots == set()

    def test_passing_test_does_not_track(self):
        """No excinfo → test passed → don't poison the slot."""
        plugin = SequentialTestPlugin()
        item = _make_item(nodeid="t.py::test_foo[slot-0]")
        call = _make_call(when="call", excinfo=None)

        plugin.pytest_runtest_makereport(item, call)

        assert plugin.failed_slots == set()

    def test_inline_test_failure_does_not_poison_anything(self):
        """A function without ``[slot-N]`` is session-wide. Its failure
        shouldn't poison any slot — we wouldn't know which one."""
        plugin = SequentialTestPlugin()
        item = _make_item(nodeid="t.py::test_foo")
        call = _make_call(when="call", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert plugin.failed_slots == set()
        assert plugin.preflight_failed is False

    def test_preflight_failure_sets_preflight_failed(self):
        """A failure in the preflight class must set the global flag —
        used for rack-level sanity checks that gate every slot."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        cls = _make_class("TestPreflight")
        item = _make_item(cls=cls, nodeid="t.py::TestPreflight::test_x")
        call = _make_call(when="call", excinfo=MagicMock())

        plugin.pytest_runtest_makereport(item, call)

        assert plugin.preflight_failed is True


# =============================================================================
# pytest_runtest_setup — skip logic
# =============================================================================


class TestRunTestSetup:
    """Setup-phase skip decisions based on what's failed so far."""

    def test_slot_failed_skips_subsequent_tests_on_same_slot(self):
        """If slot-0 failed earlier, the next slot-0 test must skip
        BEFORE fixtures run — we don't want to boot a dead panel."""
        plugin = SequentialTestPlugin()
        plugin._failed_slots.add("slot-0")

        item = _make_item(nodeid="t.py::test_later[slot-0]")

        with pytest.raises(pytest.skip.Exception):
            plugin.pytest_runtest_setup(item)

    def test_slot_failure_does_not_skip_other_slots(self):
        """The core contract: other slots keep running normally."""
        plugin = SequentialTestPlugin()
        plugin._failed_slots.add("slot-0")

        item = _make_item(nodeid="t.py::test_later[slot-1]")

        # No skip — slot-1 is still healthy.
        plugin.pytest_runtest_setup(item)

    def test_inline_test_not_skipped_by_slot_failure(self):
        """Session-wide tests have no slot; they're not on the cascade."""
        plugin = SequentialTestPlugin()
        plugin._failed_slots.update({"slot-0", "slot-1"})

        item = _make_item(nodeid="t.py::test_session_wide")

        plugin.pytest_runtest_setup(item)

    def test_preflight_failed_skips_non_preflight(self):
        """A preflight failure blocks every non-preflight test globally."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        plugin._preflight_failed = True

        other_cls = _make_class("TestOther")
        item = _make_item(cls=other_cls, nodeid="t.py::test_x[slot-0]")

        with pytest.raises(pytest.skip.Exception):
            plugin.pytest_runtest_setup(item)

    def test_preflight_failed_does_not_skip_preflight_class(self):
        """Preflight tests themselves must keep running so they finish
        reporting even after one of them has failed."""
        plugin = SequentialTestPlugin(preflight_class="TestPreflight")
        plugin._preflight_failed = True

        preflight_cls = _make_class("TestPreflight")
        item = _make_item(cls=preflight_cls, nodeid="t.py::TestPreflight::test_later")

        plugin.pytest_runtest_setup(item)

    def test_no_failures_does_not_skip(self):
        plugin = SequentialTestPlugin()

        item = _make_item(nodeid="t.py::test_x[slot-0]")

        plugin.pytest_runtest_setup(item)


# =============================================================================
# pytest_configure — -k keyword amendment
# =============================================================================


class TestPytestConfigure:
    """The plugin rewrites -k to always include preflight so a targeted
    run (e.g. ``-k test_flash``) can't skip the gating preflight."""

    def test_keyword_without_preflight_gets_amended(self):
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = "test_flash"

        plugin.pytest_configure(config)

        assert config.option.keyword == "(test_00_preflight) or (test_flash)"

    def test_keyword_already_containing_preflight_unchanged(self):
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = "test_00_preflight or test_flash"

        plugin.pytest_configure(config)

        assert config.option.keyword == "test_00_preflight or test_flash"

    def test_empty_keyword_leaves_config_unchanged(self):
        plugin = SequentialTestPlugin()
        config = MagicMock()
        config.option.keyword = ""

        plugin.pytest_configure(config)

        # Empty keyword → no filtering → no amendment needed.
        assert config.option.keyword == ""
