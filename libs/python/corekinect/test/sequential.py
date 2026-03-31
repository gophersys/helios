"""Sequential test plugin — fail-fast within test classes.

When a test in a class fails, all subsequent tests in that same class
are skipped. A designated 'preflight' class can block ALL tests globally.

This is useful for stages like FUOTA where tests within a class represent
sequential steps (flash → boot → personalize → FUOTA → verify) and later
steps depend on earlier ones succeeding.

Usage:
    In your stage's conftest.py:

        pytest_plugins = ["corekinect.test.sequential"]

    Then mark classes as sequential via naming convention:
    - Tests within a class run in order (test_01, test_02, ...)
    - If test_02 fails, test_03+ in the same class are skipped
    - Different classes continue independently
    - TestPreflight (configurable) failure blocks ALL subsequent tests

Configuration:
    The preflight class name defaults to "TestPreflight". To change it,
    set the ``--sequential-preflight`` CLI option or the
    ``SEQUENTIAL_PREFLIGHT_CLASS`` environment variable.
"""

import os
from typing import Set

import pytest


class SequentialTestPlugin:
    """Pytest plugin for fail-fast sequential test execution within classes."""

    def __init__(self, preflight_class: str = "TestPreflight"):
        """
        Args:
            preflight_class: Name of the preflight test class whose failure
                blocks all subsequent tests globally.
        """
        self._failed_classes: Set[str] = set()
        self._preflight_failed: bool = False
        self._preflight_class = preflight_class

    def pytest_runtest_makereport(self, item, call):
        """Track test failures per class for sequential dependency skipping."""
        if call.when == "call" and call.excinfo is not None:
            cls = item.cls
            if cls:
                self._failed_classes.add(cls.__name__)
                if cls.__name__ == self._preflight_class:
                    self._preflight_failed = True

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        """Skip tests based on failure hierarchy:

        1. If preflight failed -> skip ALL remaining tests
        2. If a class has a failure -> skip remaining tests in that class
        """
        cls = item.cls

        # Preflight failure blocks everything
        if self._preflight_failed and cls and cls.__name__ != self._preflight_class:
            pytest.skip("Skipped — preflight failed")

        # Class-level fail-fast
        if cls and cls.__name__ in self._failed_classes:
            pytest.skip(f"Skipped — earlier step in {cls.__name__} failed")

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
