"""Tests for module-level helpers in :mod:`corekinect.test.slot`.

Specifically :func:`get_slot_ids_from_env`, the function consumed by
the pytest slot fixture's ``params=`` to derive its parametrization.
The resolution order is:

  1. ``resolve_slot_bindings()`` — the multi-slot, MTIB_HOSTS-driven path.
  2. ``FIXTURE_CONFIG_PATH`` JSON ``slots`` count — the validation
     fixture-config path.
  3. ``["slot-0"]`` — the single-slot fallback that keeps validation
     runs without any slot-env config from going untested.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from corekinect.test.slot import get_slot_ids_from_env
from corekinect.test.slot_binding import SlotBinding


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Don't let host env vars leak into the resolution order."""
    for v in (
        "FIXTURE_CONFIG_PATH", "MTIB_HOSTS", "MTIB_ADDRESS", "MTIB_HOST",
        "MTIB_PORT", "DEVICE_ID", "DEVICE_SNR", "SLOT_FILTER",
        "SLOT_SNRS", "SLOT_DEVICE_IDS",
    ):
        monkeypatch.delenv(v, raising=False)


class TestGetSlotIdsFromEnv:
    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_uses_bindings_when_non_empty(self, mock_resolve):
        mock_resolve.return_value = [
            SlotBinding(slot_index=0, serial_number=None, device_id=None,
                        mtib_host="h0", mtib_port=50053),
            SlotBinding(slot_index=1, serial_number=None, device_id=None,
                        mtib_host="h1", mtib_port=50053),
        ]
        assert get_slot_ids_from_env() == ["slot-0", "slot-1"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_preserves_non_contiguous_indices(self, mock_resolve):
        """SLOT_FILTER may yield non-contiguous indices (e.g., only slot
        4 from a 6-slot panel). Those must be preserved in the
        parametrization ids so the reporter's per-slot routing stays
        keyed correctly.
        """
        mock_resolve.return_value = [
            SlotBinding(slot_index=4, serial_number=None, device_id=None,
                        mtib_host="h4", mtib_port=50053),
        ]
        assert get_slot_ids_from_env() == ["slot-4"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_falls_back_to_fixture_config_file(self, mock_resolve, tmp_path, monkeypatch):
        """No bindings + FIXTURE_CONFIG_PATH set → slot ids derived from
        the JSON ``slots`` array length.
        """
        mock_resolve.return_value = []
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({
            "slots": [
                {"mtib_address": "1.1.1.1"},
                {"mtib_address": "2.2.2.2"},
                {"mtib_address": "3.3.3.3"},
            ],
        }))
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", str(cfg))
        assert get_slot_ids_from_env() == ["slot-0", "slot-1", "slot-2"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_config_file_with_zero_slots_falls_back_to_slot_0(
        self, mock_resolve, tmp_path, monkeypatch,
    ):
        """An empty ``slots`` array should not collapse to no slots —
        the test fixture still needs *some* parametrization to drive
        the single-slot validation path.
        """
        mock_resolve.return_value = []
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": []}))
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", str(cfg))
        assert get_slot_ids_from_env() == ["slot-0"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_no_bindings_no_config_returns_single_slot_default(
        self, mock_resolve, monkeypatch,
    ):
        """Nothing configured → the single-slot validation default.
        This is the path taken by ``MTIB_HOST=10.0.0.1 pytest`` runs.
        """
        mock_resolve.return_value = []
        monkeypatch.delenv("FIXTURE_CONFIG_PATH", raising=False)
        assert get_slot_ids_from_env() == ["slot-0"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_fixture_config_path_set_but_file_missing_falls_back(
        self, mock_resolve, tmp_path, monkeypatch,
    ):
        """``FIXTURE_CONFIG_PATH`` pointing at a nonexistent file is
        treated as "no config" — the single-slot fallback kicks in
        rather than raising. The fixture-config path is opt-in; a stale
        env var shouldn't brick collection.
        """
        mock_resolve.return_value = []
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", str(tmp_path / "nope.json"))
        assert get_slot_ids_from_env() == ["slot-0"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_fixture_config_path_whitespace_falls_back(
        self, mock_resolve, monkeypatch,
    ):
        """An accidentally-blank FIXTURE_CONFIG_PATH (``FIXTURE_CONFIG_PATH=`` or
        whitespace) should be treated as unset.
        """
        mock_resolve.return_value = []
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", "   ")
        assert get_slot_ids_from_env() == ["slot-0"]

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_bindings_win_over_fixture_config_path(
        self, mock_resolve, tmp_path, monkeypatch,
    ):
        """Bindings (MTIB_HOSTS path) take precedence over a fixture
        config file — the resolver is the source of truth, FIXTURE_CONFIG_PATH
        is only consulted on the bindings-empty fallback.
        """
        mock_resolve.return_value = [
            SlotBinding(slot_index=0, serial_number=None, device_id=None,
                        mtib_host="h0", mtib_port=50053),
        ]
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": [
            {"mtib_address": "1.1.1.1"},
            {"mtib_address": "2.2.2.2"},
        ]}))
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", str(cfg))
        # Bindings won → exactly one id, ignoring the 2-slot config file.
        assert get_slot_ids_from_env() == ["slot-0"]
