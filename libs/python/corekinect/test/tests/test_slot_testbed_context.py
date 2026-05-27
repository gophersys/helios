"""Tests for :class:`corekinect.test.slot.TestBedContext`.

Covers the dataclass surface (properties, dunders), the three
``from_env`` resolution paths, and the multi-slot lifecycle
(``connect_all`` / ``connect_available`` / ``ensure_all_connected`` /
``disconnect_all`` / ``build_slot_test_contexts``).

The MtibV1Client is mocked end-to-end here — see
``test_slot_integration.py`` for live-gRPC coverage.
"""

from __future__ import annotations

import json
from typing import List
from unittest.mock import MagicMock, patch

import pytest

import corekinect.test.slot as slot_mod
from corekinect.test.slot import SlotContext, TestBedContext
from corekinect.test.slot_binding import SlotBinding


# ────────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """from_env / _from_single_env / _from_slot_bindings consult lots of
    env vars. Clear them so individual tests can set what they need
    without leakage from the host environment.
    """
    for v in (
        "FIXTURE_CONFIG_PATH", "MTIB_HOSTS", "MTIB_ADDRESS", "MTIB_HOST",
        "MTIB_PORT", "DEVICE_ID", "DEVICE_SNR", "SLOT_FILTER",
        "SLOT_SNRS", "SLOT_DEVICE_IDS",
    ):
        monkeypatch.delenv(v, raising=False)


def _slot(slot_id: str = "slot-0", **kw) -> SlotContext:
    defaults = dict(slot_id=slot_id, slot_index=0, mtib_address="10.0.0.1")
    defaults.update(kw)
    return SlotContext(**defaults)


# ────────────────────────────────────────────────────────────────────────
# Properties + dunders
# ────────────────────────────────────────────────────────────────────────


class TestTestBedContextProperties:
    def test_slot_count_empty(self):
        assert TestBedContext().slot_count == 0

    def test_slot_count_one(self):
        ctx = TestBedContext(slots={"slot-0": _slot()})
        assert ctx.slot_count == 1

    def test_slot_count_many(self):
        ctx = TestBedContext(slots={
            f"slot-{i}": _slot(slot_id=f"slot-{i}", slot_index=i) for i in range(5)
        })
        assert ctx.slot_count == 5

    def test_slot_ids_sorted(self):
        """Insertion order does not survive — slot_ids returns sorted IDs."""
        ctx = TestBedContext(slots={
            "slot-2": _slot(slot_id="slot-2", slot_index=2),
            "slot-0": _slot(slot_id="slot-0", slot_index=0),
            "slot-1": _slot(slot_id="slot-1", slot_index=1),
        })
        assert ctx.slot_ids == ["slot-0", "slot-1", "slot-2"]

    def test_getitem_returns_slot(self):
        s = _slot(slot_id="slot-7", slot_index=7)
        ctx = TestBedContext(slots={"slot-7": s})
        assert ctx["slot-7"] is s

    def test_getitem_missing_raises_keyerror(self):
        ctx = TestBedContext(slots={"slot-0": _slot()})
        with pytest.raises(KeyError):
            _ = ctx["does-not-exist"]

    def test_len_matches_slot_count(self):
        ctx = TestBedContext(slots={
            f"slot-{i}": _slot(slot_id=f"slot-{i}", slot_index=i) for i in range(3)
        })
        assert len(ctx) == 3
        assert len(ctx) == ctx.slot_count

    def test_iter_yields_slot_values_in_dict_order(self):
        """``__iter__`` yields the SlotContext values (not keys) in
        dict-insertion order. The reporter relies on this ordering for
        per-slot setup.
        """
        s0 = _slot(slot_id="slot-0", slot_index=0)
        s1 = _slot(slot_id="slot-1", slot_index=1)
        ctx = TestBedContext(slots={"slot-1": s1, "slot-0": s0})
        # Iteration is dict-order (insertion-order), not sorted-order.
        assert list(ctx) == [s1, s0]


# ────────────────────────────────────────────────────────────────────────
# from_env — resolution priority
# ────────────────────────────────────────────────────────────────────────


class TestFromEnvPriority:
    """from_env picks the first of: FIXTURE_CONFIG_PATH > MTIB_HOSTS > MTIB_ADDRESS/HOST."""

    def test_fixture_config_path_wins(self, monkeypatch, tmp_path):
        cfg = tmp_path / "fixture.json"
        cfg.write_text(json.dumps({"slots": [{"mtib_address": "1.2.3.4"}]}))
        monkeypatch.setenv("FIXTURE_CONFIG_PATH", str(cfg))
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1,10.0.0.2")
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")

        ctx = TestBedContext.from_env()
        # Config file path used → exactly one slot from the JSON.
        assert ctx.slot_count == 1
        assert ctx.slots["slot-0"].mtib_address == "1.2.3.4"

    def test_mtib_hosts_wins_over_single(self, monkeypatch):
        monkeypatch.setenv("MTIB_HOSTS", "10.0.0.1,10.0.0.2")
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")

        ctx = TestBedContext.from_env()
        # MTIB_HOSTS path used → two slots, not the single MTIB_ADDRESS.
        assert ctx.slot_count == 2
        assert {s.mtib_address for s in ctx.slots.values()} == {"10.0.0.1", "10.0.0.2"}

    def test_mtib_hosts_empty_string_falls_through(self, monkeypatch):
        """Empty MTIB_HOSTS is treated as "unset" so single-slot fallback
        kicks in. Otherwise a stray ``MTIB_HOSTS=`` would brick the
        single-slot validation default.
        """
        monkeypatch.setenv("MTIB_HOSTS", "")
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")

        ctx = TestBedContext.from_env()
        assert ctx.slot_count == 1
        assert ctx.slots["slot-0"].mtib_address == "10.0.0.99"

    def test_mtib_hosts_whitespace_only_falls_through(self, monkeypatch):
        monkeypatch.setenv("MTIB_HOSTS", "   ")
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")

        ctx = TestBedContext.from_env()
        assert ctx.slot_count == 1
        assert ctx.slots["slot-0"].mtib_address == "10.0.0.99"

    def test_only_mtib_address(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")
        ctx = TestBedContext.from_env()
        assert ctx.slot_count == 1
        assert ctx.slots["slot-0"].mtib_address == "10.0.0.99"

    def test_only_mtib_host(self, monkeypatch):
        monkeypatch.setenv("MTIB_HOST", "10.0.0.50")
        ctx = TestBedContext.from_env()
        assert ctx.slot_count == 1
        assert ctx.slots["slot-0"].mtib_address == "10.0.0.50"

    def test_mtib_address_wins_over_mtib_host(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.99")
        monkeypatch.setenv("MTIB_HOST", "10.0.0.50")
        ctx = TestBedContext.from_env()
        assert ctx.slots["slot-0"].mtib_address == "10.0.0.99"

    def test_nothing_set_raises(self, monkeypatch):
        with pytest.raises(ValueError) as exc_info:
            TestBedContext.from_env()
        assert "MTIB_ADDRESS" in str(exc_info.value)


# ────────────────────────────────────────────────────────────────────────
# _from_slot_bindings — MTIB_HOSTS path
# ────────────────────────────────────────────────────────────────────────


class TestFromSlotBindings:
    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_empty_bindings_yields_empty_slots(self, mock_resolve):
        mock_resolve.return_value = []
        ctx = TestBedContext._from_slot_bindings()
        assert ctx.slot_count == 0

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_single_binding_all_fields(self, mock_resolve):
        mock_resolve.return_value = [
            SlotBinding(
                slot_index=0, serial_number="ABC123", device_id="deadbeef",
                mtib_host="10.0.0.1", mtib_port=50100,
            )
        ]
        ctx = TestBedContext._from_slot_bindings()
        assert ctx.slot_count == 1
        s = ctx["slot-0"]
        assert s.slot_id == "slot-0"
        assert s.slot_index == 0
        assert s.mtib_address == "10.0.0.1"
        assert s.mtib_port == 50100
        assert s.serial_number == "ABC123"
        assert s.device_id == "deadbeef"

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_noncontiguous_indices_are_preserved(self, mock_resolve):
        """SLOT_FILTER may admit only slot 0 and slot 4 — the slot ids
        must keep the global indices so the reporter's RunTarget keying
        ``(runId, slotIndex)`` doesn't drift.
        """
        mock_resolve.return_value = [
            SlotBinding(
                slot_index=0, serial_number=None, device_id=None,
                mtib_host="10.0.0.1", mtib_port=50053,
            ),
            SlotBinding(
                slot_index=4, serial_number=None, device_id=None,
                mtib_host="10.0.0.5", mtib_port=50053,
            ),
        ]
        ctx = TestBedContext._from_slot_bindings()
        assert set(ctx.slot_ids) == {"slot-0", "slot-4"}
        assert ctx["slot-4"].slot_index == 4
        assert ctx["slot-4"].mtib_address == "10.0.0.5"

    @patch("corekinect.test.slot.resolve_slot_bindings")
    def test_missing_metadata_becomes_empty_strings(self, mock_resolve):
        """SlotBinding allows None for SNR/device_id — but SlotContext
        stores them as empty strings because the legacy contract
        downstream (reporter payloads, env injection) expects strings.
        """
        mock_resolve.return_value = [
            SlotBinding(
                slot_index=0, serial_number=None, device_id=None,
                mtib_host="10.0.0.1", mtib_port=50053,
            )
        ]
        ctx = TestBedContext._from_slot_bindings()
        s = ctx["slot-0"]
        assert s.serial_number == ""
        assert s.device_id == ""


# ────────────────────────────────────────────────────────────────────────
# _from_config_file — FIXTURE_CONFIG_PATH path
# ────────────────────────────────────────────────────────────────────────


class TestFromConfigFile:
    def test_empty_slots_yields_empty(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": []}))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx.slot_count == 0

    def test_single_slot(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({
            "slots": [{"mtib_address": "1.1.1.1", "serial_number": "A", "device_id": "B"}],
        }))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx.slot_count == 1
        s = ctx["slot-0"]
        assert s.mtib_address == "1.1.1.1"
        assert s.serial_number == "A"
        assert s.device_id == "B"

    def test_multiple_slots_get_consecutive_ids(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({
            "slots": [
                {"mtib_address": "1.1.1.1"},
                {"mtib_address": "2.2.2.2"},
                {"mtib_address": "3.3.3.3"},
            ],
        }))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert set(ctx.slot_ids) == {"slot-0", "slot-1", "slot-2"}
        assert ctx["slot-2"].slot_index == 2

    def test_missing_port_uses_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MTIB_PORT", raising=False)
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": [{"mtib_address": "1.1.1.1"}]}))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx["slot-0"].mtib_port == 50053

    def test_missing_port_uses_mtib_port_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MTIB_PORT", "60000")
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": [{"mtib_address": "1.1.1.1"}]}))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx["slot-0"].mtib_port == 60000

    def test_per_slot_port_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MTIB_PORT", "60000")
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({
            "slots": [
                {"mtib_address": "1.1.1.1", "mtib_port": 51000},  # explicit
                {"mtib_address": "2.2.2.2"},                       # falls back to env
            ],
        }))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx["slot-0"].mtib_port == 51000
        assert ctx["slot-1"].mtib_port == 60000

    def test_config_dict_propagated(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({
            "slots": [{"mtib_address": "1.1.1.1"}],
            "config": {"product": "alpha", "panel_count": 4},
        }))
        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx.config == {"product": "alpha", "panel_count": 4}

    def test_missing_mtib_address_raises_keyerror(self, tmp_path):
        """A slot dict missing the required ``mtib_address`` is a fixture
        bug — fail loudly at load time, not at first connect.
        """
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": [{"serial_number": "no-addr"}]}))
        with pytest.raises(KeyError) as exc_info:
            TestBedContext._from_config_file(str(cfg))
        assert "mtib_address" in str(exc_info.value)

    def test_invalid_json_raises(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            TestBedContext._from_config_file(str(cfg))

    def test_missing_file_raises(self, tmp_path):
        missing = tmp_path / "does-not-exist.json"
        with pytest.raises(FileNotFoundError):
            TestBedContext._from_config_file(str(missing))

    def test_optional_fields_default_to_empty_strings(self, tmp_path):
        cfg = tmp_path / "f.json"
        cfg.write_text(json.dumps({"slots": [{"mtib_address": "1.1.1.1"}]}))
        ctx = TestBedContext._from_config_file(str(cfg))
        s = ctx["slot-0"]
        assert s.serial_number == ""
        assert s.device_id == ""


# ────────────────────────────────────────────────────────────────────────
# _from_single_env
# ────────────────────────────────────────────────────────────────────────


class TestFromSingleEnv:
    def test_mtib_address_only(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        ctx = TestBedContext._from_single_env()
        assert ctx.slot_count == 1
        assert ctx["slot-0"].mtib_address == "10.0.0.1"
        assert ctx["slot-0"].mtib_port == 50053

    def test_mtib_host_only(self, monkeypatch):
        monkeypatch.setenv("MTIB_HOST", "10.0.0.2")
        ctx = TestBedContext._from_single_env()
        assert ctx["slot-0"].mtib_address == "10.0.0.2"

    def test_mtib_address_wins_over_mtib_host(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        monkeypatch.setenv("MTIB_HOST", "10.0.0.2")
        ctx = TestBedContext._from_single_env()
        assert ctx["slot-0"].mtib_address == "10.0.0.1"

    def test_address_with_explicit_port_parsed(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1:51234")
        ctx = TestBedContext._from_single_env()
        s = ctx["slot-0"]
        assert s.mtib_address == "10.0.0.1"
        assert s.mtib_port == 51234

    def test_address_no_port_uses_mtib_port_env(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        monkeypatch.setenv("MTIB_PORT", "60123")
        ctx = TestBedContext._from_single_env()
        assert ctx["slot-0"].mtib_port == 60123

    def test_address_no_port_no_env_defaults_50053(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        ctx = TestBedContext._from_single_env()
        assert ctx["slot-0"].mtib_port == 50053

    def test_device_id_and_snr_forwarded(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        monkeypatch.setenv("DEVICE_ID", "deadbeef")
        monkeypatch.setenv("DEVICE_SNR", "ABC123")
        ctx = TestBedContext._from_single_env()
        s = ctx["slot-0"]
        assert s.device_id == "deadbeef"
        assert s.serial_number == "ABC123"

    def test_missing_device_id_and_snr_default_to_empty(self, monkeypatch):
        monkeypatch.setenv("MTIB_ADDRESS", "10.0.0.1")
        ctx = TestBedContext._from_single_env()
        assert ctx["slot-0"].device_id == ""
        assert ctx["slot-0"].serial_number == ""

    def test_neither_set_raises(self, monkeypatch):
        with pytest.raises(ValueError) as exc_info:
            TestBedContext._from_single_env()
        # The error message must name every var the operator could set.
        msg = str(exc_info.value)
        assert "MTIB_ADDRESS" in msg
        assert "MTIB_HOST" in msg
        assert "MTIB_HOSTS" in msg
        assert "FIXTURE_CONFIG_PATH" in msg


# ────────────────────────────────────────────────────────────────────────
# Multi-slot lifecycle — connect_all
# ────────────────────────────────────────────────────────────────────────


class TestConnectAll:
    def test_empty_slots_is_noop(self):
        ctx = TestBedContext()
        # Must not raise even with zero slots.
        ctx.connect_all()

    def test_all_succeed_no_raise(self):
        s0 = MagicMock(spec=SlotContext)
        s1 = MagicMock(spec=SlotContext)
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1})

        ctx.connect_all()
        s0.connect.assert_called_once_with(testbed_factory=None)
        s1.connect.assert_called_once_with(testbed_factory=None)

    def test_first_failure_propagates_remaining_not_called(self):
        s0 = MagicMock(spec=SlotContext)
        s0.connect.side_effect = ConnectionError("slot 0 dead")
        s1 = MagicMock(spec=SlotContext)
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1})

        with pytest.raises(ConnectionError):
            ctx.connect_all()
        s0.connect.assert_called_once()
        # The second slot must not be touched after the first raised.
        s1.connect.assert_not_called()

    def test_forwards_testbed_factory(self):
        s0 = MagicMock(spec=SlotContext)
        ctx = TestBedContext(slots={"slot-0": s0})
        factory = object()
        ctx.connect_all(testbed_factory=factory)
        s0.connect.assert_called_once_with(testbed_factory=factory)


# ────────────────────────────────────────────────────────────────────────
# connect_available — best-effort
# ────────────────────────────────────────────────────────────────────────


class TestConnectAvailable:
    def test_empty_returns_zero(self):
        assert TestBedContext().connect_available() == 0

    def test_all_succeed_returns_n(self):
        slots = {f"slot-{i}": MagicMock(spec=SlotContext) for i in range(3)}
        for s in slots.values():
            # MagicMock's slot_id needs to be a real string for log formatting.
            s.slot_id = "slot-x"
        ctx = TestBedContext(slots=slots)
        assert ctx.connect_available() == 3

    def test_partial_failures_returns_success_count(self):
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s1 = MagicMock(spec=SlotContext); s1.slot_id = "slot-1"
        s1.connect.side_effect = ConnectionError("dead")
        s2 = MagicMock(spec=SlotContext); s2.slot_id = "slot-2"
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1, "slot-2": s2})
        # 2 of 3 succeed.
        assert ctx.connect_available() == 2
        # All three were attempted (best-effort).
        s0.connect.assert_called_once()
        s1.connect.assert_called_once()
        s2.connect.assert_called_once()

    def test_all_fail_returns_zero(self):
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s0.connect.side_effect = ConnectionError("dead")
        s1 = MagicMock(spec=SlotContext); s1.slot_id = "slot-1"
        s1.connect.side_effect = ConnectionError("dead")
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1})
        assert ctx.connect_available() == 0


# ────────────────────────────────────────────────────────────────────────
# ensure_all_connected
# ────────────────────────────────────────────────────────────────────────


class TestEnsureAllConnected:
    def test_empty_returns_zero(self):
        assert TestBedContext().ensure_all_connected() == 0

    def test_all_healthy_returns_n(self):
        slots = {}
        for i in range(3):
            s = MagicMock(spec=SlotContext)
            s.slot_id = f"slot-{i}"
            s.ensure_connected.return_value = True
            slots[s.slot_id] = s
        ctx = TestBedContext(slots=slots)
        assert ctx.ensure_all_connected() == 3

    def test_partial_healthy_returns_count(self):
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s0.ensure_connected.return_value = True
        s1 = MagicMock(spec=SlotContext); s1.slot_id = "slot-1"
        s1.ensure_connected.return_value = False
        s2 = MagicMock(spec=SlotContext); s2.slot_id = "slot-2"
        s2.ensure_connected.return_value = True
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1, "slot-2": s2})
        assert ctx.ensure_all_connected() == 2

    def test_forwards_testbed_factory(self):
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s0.ensure_connected.return_value = True
        ctx = TestBedContext(slots={"slot-0": s0})
        factory = object()
        ctx.ensure_all_connected(testbed_factory=factory)
        s0.ensure_connected.assert_called_once_with(testbed_factory=factory)


# ────────────────────────────────────────────────────────────────────────
# disconnect_all
# ────────────────────────────────────────────────────────────────────────


class TestDisconnectAll:
    def test_empty_is_noop(self):
        TestBedContext().disconnect_all()  # must not raise

    def test_all_succeed(self):
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s1 = MagicMock(spec=SlotContext); s1.slot_id = "slot-1"
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1})
        ctx.disconnect_all()
        s0.disconnect.assert_called_once()
        s1.disconnect.assert_called_once()

    def test_one_raise_others_still_called(self):
        """``disconnect_all`` is best-effort. A single slot raising must
        not skip the rest, otherwise a wedged slot strands the others."""
        s0 = MagicMock(spec=SlotContext); s0.slot_id = "slot-0"
        s0.disconnect.side_effect = RuntimeError("boom")
        s1 = MagicMock(spec=SlotContext); s1.slot_id = "slot-1"
        s2 = MagicMock(spec=SlotContext); s2.slot_id = "slot-2"
        ctx = TestBedContext(slots={"slot-0": s0, "slot-1": s1, "slot-2": s2})

        ctx.disconnect_all()  # must not raise
        s0.disconnect.assert_called_once()
        s1.disconnect.assert_called_once()
        s2.disconnect.assert_called_once()


# ────────────────────────────────────────────────────────────────────────
# build_slot_test_contexts
# ────────────────────────────────────────────────────────────────────────


class TestBuildSlotTestContexts:
    @patch("corekinect.test.slot.SlotTestContext")
    def test_only_connected_slots_are_wrapped(self, mock_stc_cls):
        """Slots without ``slot.mtib`` are skipped — the wrapper has
        nothing to drive without a connected client.
        """
        wrapper_a = MagicMock()
        wrapper_b = MagicMock()
        mock_stc_cls.from_slot.side_effect = [wrapper_a, wrapper_b]

        connected = _slot(slot_id="slot-0", slot_index=0)
        connected.mtib = MagicMock()  # marked connected
        also_connected = _slot(slot_id="slot-2", slot_index=2)
        also_connected.mtib = MagicMock()
        disconnected = _slot(slot_id="slot-1", slot_index=1)
        disconnected.mtib = None

        ctx = TestBedContext(slots={
            "slot-0": connected,
            "slot-1": disconnected,
            "slot-2": also_connected,
        })

        result = ctx.build_slot_test_contexts()
        # Only the two connected slots are wrapped.
        assert set(result.keys()) == {"slot-0", "slot-2"}
        assert result["slot-0"] is wrapper_a
        assert result["slot-2"] is wrapper_b
        assert mock_stc_cls.from_slot.call_count == 2

    @patch("corekinect.test.slot.SlotTestContext")
    def test_target_ids_none_defaults_to_none_arg(self, mock_stc_cls):
        s = _slot(); s.mtib = MagicMock()
        ctx = TestBedContext(slots={"slot-0": s})
        ctx.build_slot_test_contexts()

        # The wrapper factory was called with target_id=None.
        _args, kwargs = mock_stc_cls.from_slot.call_args
        assert kwargs["target_id"] is None

    @patch("corekinect.test.slot.SlotTestContext")
    def test_target_ids_entry_forwarded(self, mock_stc_cls):
        s = _slot(); s.mtib = MagicMock()
        ctx = TestBedContext(slots={"slot-0": s})
        ctx.build_slot_test_contexts(target_ids={"slot-0": "target-abc"})

        _args, kwargs = mock_stc_cls.from_slot.call_args
        assert kwargs["target_id"] == "target-abc"

    @patch("corekinect.test.slot.SlotTestContext")
    def test_target_ids_missing_entry_becomes_none(self, mock_stc_cls):
        """If the caller supplies ``target_ids`` but not for *this* slot,
        the wrapper still gets ``target_id=None`` rather than raising
        KeyError.
        """
        s = _slot(); s.mtib = MagicMock()
        ctx = TestBedContext(slots={"slot-0": s})
        ctx.build_slot_test_contexts(target_ids={"slot-99": "irrelevant"})

        _args, kwargs = mock_stc_cls.from_slot.call_args
        assert kwargs["target_id"] is None

    @patch("corekinect.test.slot.SlotTestContext")
    def test_telemetry_forwarded(self, mock_stc_cls):
        s = _slot(); s.mtib = MagicMock()
        ctx = TestBedContext(slots={"slot-0": s})
        sentinel = MagicMock(name="telemetry")
        ctx.build_slot_test_contexts(telemetry=sentinel)

        _args, kwargs = mock_stc_cls.from_slot.call_args
        assert kwargs["telemetry"] is sentinel
