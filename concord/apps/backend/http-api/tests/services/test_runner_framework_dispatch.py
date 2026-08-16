"""Tests for runner framework dispatch.

Verifies that the runner Job entrypoint selection respects the test
package's ``framework`` field:

    - framework=None / missing  → pytest entrypoint (back-compat)
    - framework="pytest"        → pytest entrypoint
    - framework="PYTEST"        → pytest entrypoint (case-insensitive)
    - framework="ztest"         → ztest entrypoint
    - framework="bogus"         → ValueError

These are the smallest possible unit tests — the dispatch module is a
pure function that maps an enum value to a command list. The harder
tests (full K8s Job creation, scheduler hand-off) live in
``test_scheduler.py`` and ``test_manual.py``; the goal here is to lock
the dispatch contract before wiring anything else.
"""

from __future__ import annotations

import pytest

from src.services.kubernetes.runner_dispatch import (
    DEFAULT_FRAMEWORK,
    PYTEST_RUNNER_COMMAND,
    ZTEST_RUNNER_COMMAND,
    framework_env_var,
    normalize_framework,
    runner_command_for_framework,
)


class TestNormalizeFramework:
    def test_none_defaults_to_pytest(self):
        assert normalize_framework(None) == "PYTEST"

    def test_empty_string_defaults_to_pytest(self):
        assert normalize_framework("") == "PYTEST"
        assert normalize_framework("   ") == "PYTEST"

    def test_pytest_lowercase(self):
        assert normalize_framework("pytest") == "PYTEST"

    def test_pytest_uppercase(self):
        assert normalize_framework("PYTEST") == "PYTEST"

    def test_pytest_mixed_case(self):
        assert normalize_framework("PyTest") == "PYTEST"

    def test_ztest_lowercase(self):
        assert normalize_framework("ztest") == "ZTEST"

    def test_ztest_uppercase(self):
        assert normalize_framework("ZTEST") == "ZTEST"

    def test_unknown_framework_raises(self):
        with pytest.raises(ValueError) as exc:
            normalize_framework("rust-test")
        assert "rust-test" in str(exc.value)
        assert "pytest" in str(exc.value).lower()
        assert "ztest" in str(exc.value).lower()

    def test_default_constant_matches_pytest_normalization(self):
        assert DEFAULT_FRAMEWORK == "PYTEST"


class TestRunnerCommandForFramework:
    def test_pytest_command_returned_for_pytest(self):
        cmd = runner_command_for_framework("pytest")
        assert cmd == PYTEST_RUNNER_COMMAND

    def test_pytest_command_returned_for_none(self):
        """Missing framework falls back to pytest (back-compat)."""
        cmd = runner_command_for_framework(None)
        assert cmd == PYTEST_RUNNER_COMMAND

    def test_pytest_command_returned_for_empty_string(self):
        cmd = runner_command_for_framework("")
        assert cmd == PYTEST_RUNNER_COMMAND

    def test_ztest_command_returned_for_ztest(self):
        cmd = runner_command_for_framework("ztest")
        assert cmd == ZTEST_RUNNER_COMMAND

    def test_pytest_and_ztest_commands_differ(self):
        """The whole point of dispatch — they must produce different commands."""
        assert PYTEST_RUNNER_COMMAND != ZTEST_RUNNER_COMMAND

    def test_returned_command_is_a_list(self):
        """Caller passes the result to K8s spec.template.spec.containers[].command,
        which requires a list."""
        assert isinstance(runner_command_for_framework("pytest"), list)
        assert isinstance(runner_command_for_framework("ztest"), list)

    def test_returned_command_is_a_copy(self):
        """Mutating one caller's command must not affect the next call."""
        cmd1 = runner_command_for_framework("pytest")
        cmd1.append("BOGUS")
        cmd2 = runner_command_for_framework("pytest")
        assert "BOGUS" not in cmd2

    def test_unknown_framework_raises(self):
        with pytest.raises(ValueError):
            runner_command_for_framework("rust-test")


class TestFrameworkEnvVar:
    """The runner pod also needs to know its framework via env var.

    The entrypoint scripts read TEST_FRAMEWORK so they can log it and so
    they can verify the dispatched command matches what the backend
    expected (a small belt-and-braces check).
    """

    def test_pytest_env_value(self):
        assert framework_env_var("pytest") == "PYTEST"

    def test_ztest_env_value(self):
        assert framework_env_var("ztest") == "ZTEST"

    def test_none_defaults_to_pytest(self):
        assert framework_env_var(None) == "PYTEST"

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            framework_env_var("rust-test")
