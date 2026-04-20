"""Sequential test plugin — fail-fast within a manufacturing slot.

When any test on slot-N fails, every remaining test on slot-N is
skipped. Manufacturing semantics: a panel that fails test 3 is a bad
panel — there is no point burning the next 17 tests on it. Operators
want "panel failed" as the terminal state as soon as it's known.

Scope:
    • Tracking is **per-slot**, keyed off the ``[slot-N]`` nodeid
      parameter. Failures on slot-0 don't poison slot-1; a panel with
      three good DUTs and one bad one still gets full results on the
      three good slots.
    • Tests without a ``[slot-N]`` suffix (inline / session-wide tests)
      are unaffected — failures there don't cascade either way.
    • A designated preflight class (name configurable) blocks ALL
      subsequent tests globally. Preflight checks validate the rack
      before anyone touches hardware; once they fail, nothing else
      should run.

History:
    Earlier versions tracked failures by ``item.cls.__name__``. That
    silently no-op'd the fail-fast for every function-level test
    (``item.cls`` is None), which is how ``test_03_post`` kept running
    after ``test_02_fw_flash`` failed. Slot-keyed tracking works for
    both class- and function-level tests.

Usage:
    In the stage's ``conftest.py`` (or via a product-level plugin):

        pytest_plugins = ["corekinect.test.sequential"]

    No per-test marker is required; the cascade applies to every test
    with a ``[slot-N]`` parameter. Tests that must run even after a
    slot is dead (post-failure telemetry flush, cleanup) should simply
    not use the ``[slot-N]`` parametrization.

Configuration:
    ``SEQUENTIAL_PREFLIGHT_CLASS`` env var sets the preflight class
    name (defaults to ``TestPreflight``).
"""

import os
import re
from typing import Optional, Set

import pytest


# Match ``[slot-N`` followed by either ``]`` (single-axis parametrize)
# or ``-`` (compound parametrize — pytest joins params with ``-``, so
# ``[slot-0-debug]`` is "slot 0, variant debug"). The lookahead keeps
# digits bounded without a trailing greedy match.
_SLOT_RE = re.compile(r"\[slot-(\d+)(?=[-\]])")


def _slot_id(nodeid: str) -> Optional[str]:
    """Extract ``slot-N`` from a pytest nodeid, or None if not slot-parametrized.

    Works for both ``…::test_foo[slot-0]`` and the compound form
    ``…::test_foo[slot-0-variant-debug]`` — we only need the slot
    component, so we match the ``[slot-N]`` prefix even inside a
    longer bracketed parameter list.
    """
    if not nodeid:
        return None
    m = _SLOT_RE.search(nodeid)
    return f"slot-{m.group(1)}" if m else None


class SequentialTestPlugin:
    """Pytest plugin for fail-fast sequential test execution per slot."""

    def __init__(self, preflight_class: str = "TestPreflight"):
        """
        Args:
            preflight_class: Name of the preflight test class whose failure
                blocks all subsequent tests globally.
        """
        # Set of slot ids (e.g. ``{"slot-0", "slot-2"}``) whose panel has
        # already failed. Tests in these slots skip from setup onwards.
        self._failed_slots: Set[str] = set()
        # Classes tracked only because the preflight-class rule still
        # uses the class name. Regular fail-fast is slot-scoped.
        self._preflight_failed: bool = False
        self._preflight_class = preflight_class

    # ── Accessors (used by the tests) ─────────────────────────────────

    @property
    def failed_slots(self) -> Set[str]:
        """Read-only view of which slots have failed so far."""
        return set(self._failed_slots)

    @property
    def preflight_failed(self) -> bool:
        return self._preflight_failed

    # ── Hooks ─────────────────────────────────────────────────────────

    def pytest_runtest_makereport(self, item, call):
        """Record failures by slot (and preflight-class, globally)."""
        if call.when != "call" or call.excinfo is None:
            # Only count real test-call failures. Fixture setup
            # failures still cascade via pytest's own machinery; adding
            # them here would double-count and mask fixture bugs.
            return

        cls = item.cls
        if cls and cls.__name__ == self._preflight_class:
            self._preflight_failed = True
            return

        slot = _slot_id(item.nodeid)
        if slot is not None:
            self._failed_slots.add(slot)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        """Skip subsequent tests on any slot that has already failed.

        Evaluated before fixtures set up, so we avoid booting a DUT
        whose panel is already known-bad.
        """
        cls = item.cls

        # Preflight failure blocks everything that isn't itself preflight.
        if self._preflight_failed and (not cls or cls.__name__ != self._preflight_class):
            pytest.skip("Skipped — preflight failed")

        slot = _slot_id(item.nodeid)
        if slot is not None and slot in self._failed_slots:
            pytest.skip(f"Skipped — {slot} failed an earlier test")

    def pytest_configure(self, config):
        """Amend -k expression to always include preflight tests.

        Preflight checks validate the environment before any hardware
        interaction. They must always run regardless of -k filtering.
        """
        keyword = getattr(config.option, "keyword", None)
        if keyword and "test_00_preflight" not in keyword:
            config.option.keyword = f"(test_00_preflight) or ({keyword})"


def pytest_configure(config):
    """Auto-register the sequential plugin when this module is loaded.

    Called by pytest when this module appears in ``pytest_plugins``.
    Registers a SequentialTestPlugin instance, which then receives its
    own ``pytest_configure`` hook call for -k expression amendment.
    """
    preflight_class = os.environ.get("SEQUENTIAL_PREFLIGHT_CLASS", "TestPreflight")
    plugin = SequentialTestPlugin(preflight_class=preflight_class)
    config.pluginmanager.register(plugin, "sequential_tests")
