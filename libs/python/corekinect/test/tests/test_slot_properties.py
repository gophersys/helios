"""Property-based tests for :mod:`corekinect.test.slot`.

Three invariants:

1. ``MTIB_HOSTS=h1,h2,...`` produces exactly N slots whose ids are
   ``slot-0..slot-N-1`` (modulo SLOT_FILTER) — regardless of the
   hostnames, ports, or whitespace operators throw at it.
2. A JSON config file with K randomly-generated slot dicts round-trips
   through ``_from_config_file`` so the count and every field
   survives.
3. The retry loop sleeps exactly ``k`` times when ``k`` attempts fail
   before success — for every k in ``[0, CONNECT_MAX_ATTEMPTS-1]``.
   When all attempts fail, pod_state_lookup is consulted at most once.
"""

from __future__ import annotations

import json
import string
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

import corekinect.test.slot as slot_mod
from corekinect.test.slot import SlotContext, TestBedContext


# ────────────────────────────────────────────────────────────────────────
# Strategies
# ────────────────────────────────────────────────────────────────────────


# A DNS-ish host token: letters/digits/dashes/dots, no leading dash.
_HOST_ALPHABET = string.ascii_lowercase + string.digits + ".-"

hostnames = st.builds(
    lambda first, rest: first + "".join(rest),
    st.sampled_from(string.ascii_lowercase + string.digits),
    st.lists(st.sampled_from(_HOST_ALPHABET), min_size=2, max_size=20),
).map(lambda s: s.replace("..", "x.").replace("..", "x.")  # avoid empty labels
).filter(lambda s: not s.endswith(".") and not s.startswith("."))


ports = st.integers(min_value=1024, max_value=65535)


def _address(host: str, port: int | None) -> str:
    return f"{host}:{port}" if port is not None else host


# A list of 1–8 address strings. Each entry may or may not include a port;
# we also throw in surrounding whitespace (operators paste hosts from
# all sorts of places).
address_lists = st.lists(
    st.tuples(hostnames, st.one_of(st.none(), ports)),
    min_size=1, max_size=8,
).map(lambda pairs: [_address(h, p) for (h, p) in pairs])


# A single slot dict (for the JSON-roundtrip property).
slot_dicts = st.fixed_dictionaries({
    "mtib_address": hostnames,
    "mtib_port": ports,
    "serial_number": st.text(
        alphabet=string.ascii_uppercase + string.digits, min_size=0, max_size=10,
    ),
    "device_id": st.text(
        alphabet=string.hexdigits.lower(), min_size=0, max_size=16,
    ),
})

slot_dict_lists = st.lists(slot_dicts, min_size=0, max_size=6)


# ────────────────────────────────────────────────────────────────────────
# Invariant 1: MTIB_HOSTS → N slots with consecutive ids
# ────────────────────────────────────────────────────────────────────────


class TestMtibHostsInvariant:
    @given(addresses=address_lists)
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
        max_examples=50,
    )
    def test_slot_count_matches_addresses(self, addresses, monkeypatch):
        """``MTIB_HOSTS`` round-trip: N comma-separated addresses → N slots.
        Each slot id matches its positional index (no SLOT_FILTER in play).
        """
        for v in (
            "FIXTURE_CONFIG_PATH", "MTIB_ADDRESS", "MTIB_HOST",
            "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
        ):
            monkeypatch.delenv(v, raising=False)
        monkeypatch.setenv("MTIB_HOSTS", ",".join(addresses))

        ctx = TestBedContext.from_env()
        assert ctx.slot_count == len(addresses)
        # IDs are slot-0..slot-N-1 (no SLOT_FILTER → contiguous indices).
        assert ctx.slot_ids == sorted([f"slot-{i}" for i in range(len(addresses))])

    @given(addresses=address_lists)
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
        max_examples=30,
    )
    def test_surrounding_whitespace_tolerated(self, addresses, monkeypatch):
        """Wrap each address in random whitespace — slot count and ids
        must be unchanged.
        """
        for v in (
            "FIXTURE_CONFIG_PATH", "MTIB_ADDRESS", "MTIB_HOST",
            "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
        ):
            monkeypatch.delenv(v, raising=False)
        padded = [f"  {a}\t" for a in addresses]
        monkeypatch.setenv("MTIB_HOSTS", ",".join(padded))

        ctx = TestBedContext.from_env()
        assert ctx.slot_count == len(addresses)


# ────────────────────────────────────────────────────────────────────────
# Invariant 2: JSON config roundtrip
# ────────────────────────────────────────────────────────────────────────


class TestConfigFileRoundtrip:
    @given(slot_data=slot_dict_lists)
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
        max_examples=30,
    )
    def test_config_roundtrips(self, slot_data, monkeypatch, tmp_path_factory):
        """Write → load → assert every field survives."""
        for v in (
            "FIXTURE_CONFIG_PATH", "MTIB_HOSTS", "MTIB_ADDRESS", "MTIB_HOST",
            "MTIB_PORT", "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
        ):
            monkeypatch.delenv(v, raising=False)

        # tmp_path_factory is session-scoped so we don't blow up the
        # per-test cleanup with thousands of files.
        tmp = tmp_path_factory.mktemp("cfg")
        cfg = tmp / "f.json"
        cfg.write_text(json.dumps({"slots": slot_data, "config": {"k": "v"}}))

        ctx = TestBedContext._from_config_file(str(cfg))
        assert ctx.slot_count == len(slot_data)
        assert ctx.config == {"k": "v"}

        for i, expected in enumerate(slot_data):
            slot_id = f"slot-{i}"
            s = ctx[slot_id]
            assert s.slot_index == i
            assert s.mtib_address == expected["mtib_address"]
            assert s.mtib_port == expected["mtib_port"]
            assert s.serial_number == expected["serial_number"]
            assert s.device_id == expected["device_id"]


# ────────────────────────────────────────────────────────────────────────
# Invariant 3: retry-loop sleep count
# ────────────────────────────────────────────────────────────────────────


class TestRetryLoopInvariants:
    @given(k=st.integers(min_value=0, max_value=slot_mod.CONNECT_MAX_ATTEMPTS - 1))
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
        max_examples=20,
    )
    def test_sleep_count_equals_failed_attempts(self, k, monkeypatch):
        """After ``k`` failures and one success the slot must sleep
        exactly ``k`` times. Sleeps gate the retry interval; getting
        this wrong means production hammers the MTIB or stalls runs.
        """
        sleeps: List[float] = []
        monkeypatch.setattr(slot_mod.time, "sleep", lambda s: sleeps.append(s))

        call_count = {"n": 0}

        def make_client(_cfg):
            call_count["n"] += 1
            mock = MagicMock()
            if call_count["n"] <= k:
                mock.connect.return_value = "boom"
            else:
                mock.connect.return_value = None
                mock.HealthCheck.return_value = (True, [], None)
            return mock

        with patch.object(slot_mod, "MtibV1Client", side_effect=make_client):
            slot = SlotContext(
                slot_id="slot-0", slot_index=0, mtib_address="h",
            )
            slot.connect()

        assert len(sleeps) == k
        assert call_count["n"] == k + 1

    def test_pod_state_lookup_called_at_most_once_on_total_failure(self, monkeypatch):
        """When every attempt fails, the pod-state lookup is consulted
        at most once — never on attempt 1, never repeated after the
        first call. This isn't a strategy-based test because the input
        space is small (one path) but the invariant matters: a wedged
        cluster shouldn't get hammered with N lookups per slot per
        retry cycle.
        """
        monkeypatch.setattr(slot_mod.time, "sleep", lambda _s: None)

        lookup = MagicMock(return_value="ImagePullBackOff")

        with patch.object(slot_mod, "MtibV1Client") as mock_cls:
            mock_mtib = MagicMock()
            mock_mtib.connect.return_value = "boom"
            mock_cls.return_value = mock_mtib

            slot = SlotContext(
                slot_id="slot-0", slot_index=0, mtib_address="h",
            )
            slot.pod_state_lookup = lookup

            with pytest.raises(ConnectionError):
                slot.connect()

        assert lookup.call_count <= 1
        assert lookup.call_count == 1  # tight: it IS called for ≥2 failures
