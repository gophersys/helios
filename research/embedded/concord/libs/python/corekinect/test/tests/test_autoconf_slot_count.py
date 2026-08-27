"""Tests for ``autoconf._maybe_register_slot_parallel`` slot counting.

Before Phase 2 the helper hand-rolled its own MTIB_HOSTS / SLOT_FILTER
parser, drifting from the canonical ``slot_env.resolve_slot_bindings``
on edge cases (empty hosts, whitespace, trailing commas). Phase 2
delegates the count to ``resolve_slot_bindings()`` so the two never
disagree.

These tests pin the contract: under any env-var combination, the
plugin's "should I activate?" decision matches the bindings the rest
of the framework will see at fixture time.
"""

from __future__ import annotations

import os
from typing import Dict
from unittest.mock import MagicMock

import pytest

from corekinect.test.autoconf import _maybe_register_slot_parallel
from corekinect.test.slot_env import resolve_slot_bindings


def _fake_config(plugin_already_loaded: bool = False) -> MagicMock:
    """Return a Config-shaped object that records plugin registration calls.

    The helper only touches ``config.pluginmanager.has_plugin`` and
    ``import_plugin`` — those are the surfaces the test asserts on.
    """
    config = MagicMock()
    config.pluginmanager.has_plugin.return_value = plugin_already_loaded
    return config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch):
    """Each test starts from a clean MTIB env so order doesn't leak."""
    for var in ("MTIB_HOSTS", "MTIB_HOST", "MTIB_ADDRESS",
                "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
                "PYTEST_PARALLEL", "FIXTURE_CONFIG_PATH"):
        monkeypatch.delenv(var, raising=False)


class TestSlotCountAgreesWithCanonicalResolver:
    """The helper's count must match ``len(resolve_slot_bindings())``."""

    def test_no_mtib_hosts_means_no_registration(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_not_called()
        # Sanity: canonical resolver agrees there's nothing to register.
        assert resolve_slot_bindings() == []

    def test_single_mtib_host_means_no_registration(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1:50053")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_not_called()
        assert len(resolve_slot_bindings()) == 1

    def test_two_mtib_hosts_registers_plugin(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1:50053,10.0.0.2:50053")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_called_once_with(
            "corekinect.test.slot_parallel"
        )
        assert len(resolve_slot_bindings()) == 2

    def test_slot_filter_narrows_registration_decision(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SLOT_FILTER=0 with 4 hosts → 1 effective slot, no registration."""
        monkeypatch.setenv(
            "MTIB_HOSTS",
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
        )
        monkeypatch.setenv("SLOT_FILTER", "0")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_not_called()
        assert len(resolve_slot_bindings()) == 1

    def test_slot_filter_with_three_slots_registers(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(
            "MTIB_HOSTS",
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
        )
        monkeypatch.setenv("SLOT_FILTER", "0,1,3")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_called_once()
        assert len(resolve_slot_bindings()) == 3

    def test_whitespace_in_hosts_is_tolerated_consistently(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Drift case from before: hand-rolled split treated `' '` as a host."""
        monkeypatch.setenv("MTIB_HOSTS", "  10.0.0.1:50053  ,  10.0.0.2:50053  ")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_called_once()
        assert len(resolve_slot_bindings()) == 2

    def test_trailing_comma_does_not_inflate_count(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Trailing comma must not phantom-register a 4th slot."""
        monkeypatch.setenv(
            "MTIB_HOSTS", "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,",
        )
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        # 3 real slots, both helper and resolver agree.
        assert len(resolve_slot_bindings()) == 3
        config.pluginmanager.import_plugin.assert_called_once()


class TestExplicitOptOut:
    """``PYTEST_PARALLEL=0`` short-circuits regardless of slot count."""

    @pytest.mark.parametrize("flag", ["0", "false", "no", "False"])
    def test_opt_out_is_respected(
        self, flag: str, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PYTEST_PARALLEL", flag)
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1:50053,10.0.0.2:50053")
        config = _fake_config()
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_not_called()


class TestIdempotentRegistration:
    """The plugin should only be registered once even on repeat calls."""

    def test_already_loaded_plugin_is_not_reregistered(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1:50053,10.0.0.2:50053")
        config = _fake_config(plugin_already_loaded=True)
        _maybe_register_slot_parallel(config)
        config.pluginmanager.import_plugin.assert_not_called()
