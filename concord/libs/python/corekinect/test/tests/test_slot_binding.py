"""Tests for :mod:`corekinect.test.slot_binding` and :mod:`corekinect.test.slot_env`.

These modules replace the four duplicated env-var parsers scattered
across ``autoconf.py`` and ``slot.py`` with a single
:func:`resolve_slot_bindings` function, plus a frozen
:class:`SlotBinding` dataclass that gets stashed on every pytest
item at collection time. Collection-time attribution is the
load-bearing change of the framework refactor.

Design contract exercised here
------------------------------

* ``SlotBinding`` is frozen and hashable — safe to share across
  threads, safe to use as a dict key if needed.
* ``resolve_slot_bindings()`` reads ``MTIB_HOSTS``, ``SLOT_FILTER``,
  ``SLOT_SNRS``, ``SLOT_DEVICE_IDS`` and ``MTIB_PORT`` and produces a
  list ordered by ``slot_index`` with exactly one binding per
  filtered slot.
* Filtering (``SLOT_FILTER``) narrows the set; SNRs/device IDs are
  aligned with the *filtered* sequence, not the raw address list.
* The function is pure: no I/O, no env mutation, no logging side
  effects that affect test outcomes.
* When no MTIB env is configured, returns an empty list rather than
  raising — the caller decides whether that's an error.
* ``SLOT_BINDING_KEY`` is a ``pytest.StashKey`` usable on
  ``item.stash``.

These tests must all pass before touching the autoconf / reporter
code that reads ``SlotBinding`` downstream.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from corekinect.test.slot_binding import SLOT_BINDING_KEY, SlotBinding
from corekinect.test.slot_env import resolve_slot_bindings, slot_bindings_by_index


# ────────────────────────────────────────────────────────────────────────
# TestBeds
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every MTIB/SLOT env var so each test starts from a known state."""
    for var in (
        "MTIB_HOSTS", "MTIB_HOST", "MTIB_ADDRESS", "MTIB_PORT",
        "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
        "FIXTURE_CONFIG_PATH",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# ────────────────────────────────────────────────────────────────────────
# SlotBinding dataclass
# ────────────────────────────────────────────────────────────────────────


def test_slot_binding_is_frozen():
    binding = SlotBinding(
        slot_index=0, serial_number="095F", device_id="abc",
        mtib_host="10.4.45.36", mtib_port=50053,
    )
    with pytest.raises((AttributeError, Exception)):
        binding.slot_index = 5  # frozen dataclass rejects mutation


def test_slot_binding_is_hashable():
    b = SlotBinding(
        slot_index=0, serial_number="095F", device_id="abc",
        mtib_host="10.4.45.36", mtib_port=50053,
    )
    # Usable in a set or as a dict key.
    assert {b} == {b}


def test_slot_binding_allows_missing_optional_fields():
    # serial_number / device_id may be empty if SLOT_SNRS not set.
    b = SlotBinding(
        slot_index=0, serial_number=None, device_id=None,
        mtib_host="10.4.45.36", mtib_port=50053,
    )
    assert b.serial_number is None
    assert b.device_id is None


def test_slot_binding_key_is_a_pytest_stash_key():
    assert isinstance(SLOT_BINDING_KEY, pytest.StashKey)


# ────────────────────────────────────────────────────────────────────────
# resolve_slot_bindings — happy paths
# ────────────────────────────────────────────────────────────────────────


def test_resolve_no_env_returns_empty_list(clean_env):
    assert resolve_slot_bindings() == []


def test_resolve_single_host_no_port(clean_env):
    clean_env.setenv("MTIB_HOSTS", "10.4.45.36")
    bindings = resolve_slot_bindings()
    assert len(bindings) == 1
    assert bindings[0].slot_index == 0
    assert bindings[0].mtib_host == "10.4.45.36"
    assert bindings[0].mtib_port == 50053
    assert bindings[0].serial_number is None
    assert bindings[0].device_id is None


def test_resolve_host_with_port(clean_env):
    clean_env.setenv("MTIB_HOSTS", "10.4.45.36:12345")
    bindings = resolve_slot_bindings()
    assert bindings[0].mtib_port == 12345


def test_resolve_mtib_port_env_overrides_default(clean_env):
    clean_env.setenv("MTIB_HOSTS", "10.4.45.36")
    clean_env.setenv("MTIB_PORT", "50054")
    bindings = resolve_slot_bindings()
    assert bindings[0].mtib_port == 50054


def test_resolve_multi_host_preserves_order_and_indexes(clean_env):
    clean_env.setenv(
        "MTIB_HOSTS",
        "10.4.45.36,10.4.45.39,10.4.45.37,10.4.45.34,10.4.45.33",
    )
    bindings = resolve_slot_bindings()
    assert [b.slot_index for b in bindings] == [0, 1, 2, 3, 4]
    assert [b.mtib_host for b in bindings] == [
        "10.4.45.36", "10.4.45.39", "10.4.45.37", "10.4.45.34", "10.4.45.33",
    ]


def test_resolve_snrs_align_with_hosts(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h1,h2,h3,h4")
    clean_env.setenv("SLOT_SNRS", "095F,095G,095H,095J")
    bindings = resolve_slot_bindings()
    assert [b.serial_number for b in bindings] == ["095F", "095G", "095H", "095J"]


def test_resolve_device_ids_align_with_hosts(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h1,h2,h3,h4")
    clean_env.setenv("SLOT_DEVICE_IDS", "id1,id2,id3,id4")
    bindings = resolve_slot_bindings()
    assert [b.device_id for b in bindings] == ["id1", "id2", "id3", "id4"]


# ────────────────────────────────────────────────────────────────────────
# SLOT_FILTER — narrowing
# ────────────────────────────────────────────────────────────────────────


def test_resolve_slot_filter_selects_subset(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h0,h1,h2,h3,h4")
    clean_env.setenv("SLOT_FILTER", "0,1,2,3")
    bindings = resolve_slot_bindings()
    # Filtered out slot 4 (the standalone).
    assert [b.slot_index for b in bindings] == [0, 1, 2, 3]
    assert [b.mtib_host for b in bindings] == ["h0", "h1", "h2", "h3"]


def test_resolve_slot_filter_preserves_global_slot_index(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h0,h1,h2,h3,h4")
    clean_env.setenv("SLOT_FILTER", "4")
    bindings = resolve_slot_bindings()
    # Standalone-only run — the remaining binding is still slot_index=4,
    # matching the address position in MTIB_HOSTS. This is critical for
    # backend attribution: the RunTarget's slotIndex must match.
    assert len(bindings) == 1
    assert bindings[0].slot_index == 4
    assert bindings[0].mtib_host == "h4"


def test_resolve_snrs_align_with_filtered_slots_not_all_hosts(clean_env):
    """SLOT_SNRS should provide one entry per *filtered* slot, not per raw host.

    This matches how the manufacturing runner ships SNRs — it knows
    which slots the panel scan targeted and sends exactly that many.
    """
    clean_env.setenv("MTIB_HOSTS", "h0,h1,h2,h3,h4")
    clean_env.setenv("SLOT_FILTER", "0,1,2,3")
    clean_env.setenv("SLOT_SNRS", "095F,095G,095H,095J")
    bindings = resolve_slot_bindings()
    assert len(bindings) == 4
    # Filtered slot indices 0..3 get the 4 provided SNRs in order.
    assert [b.serial_number for b in bindings] == ["095F", "095G", "095H", "095J"]


def test_resolve_ignores_snr_count_mismatch(clean_env):
    """If SLOT_SNRS count doesn't match the filtered slot count, silently drop them.

    Matches legacy ``_split_env`` behaviour — log a warning, proceed
    with serial_number=None. Mismatches happen when a panel has blank
    slots; we prefer "run without serials" over hard failure.
    """
    clean_env.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    clean_env.setenv("SLOT_SNRS", "only,two,values")  # 3 values for 4 slots
    bindings = resolve_slot_bindings()
    assert len(bindings) == 4
    assert all(b.serial_number is None for b in bindings)


# ────────────────────────────────────────────────────────────────────────
# Robustness — whitespace, empty items
# ────────────────────────────────────────────────────────────────────────


def test_resolve_strips_whitespace(clean_env):
    clean_env.setenv("MTIB_HOSTS", "  h0 , h1  , h2  ")
    clean_env.setenv("SLOT_SNRS", "  s0, s1, s2 ")
    bindings = resolve_slot_bindings()
    assert [b.mtib_host for b in bindings] == ["h0", "h1", "h2"]
    assert [b.serial_number for b in bindings] == ["s0", "s1", "s2"]


def test_resolve_drops_empty_fields(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h0,,h1,")
    bindings = resolve_slot_bindings()
    assert len(bindings) == 2
    assert [b.mtib_host for b in bindings] == ["h0", "h1"]
    # Even though we dropped empties, the preserved slots keep their
    # ORIGINAL indexes (0, 2) — not (0, 1) — so a later binding lookup
    # from an item parametrized as [slot-2] lands on h1.
    assert [b.slot_index for b in bindings] == [0, 2]


# ────────────────────────────────────────────────────────────────────────
# Lookup helper
# ────────────────────────────────────────────────────────────────────────


def test_slot_bindings_by_index_is_a_dict(clean_env):
    """Convenience helper: bindings keyed by slot_index for O(1) lookup by autoconf."""
    clean_env.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    clean_env.setenv("SLOT_FILTER", "1,3")
    m = slot_bindings_by_index(resolve_slot_bindings())
    assert set(m.keys()) == {1, 3}
    assert m[1].mtib_host == "h1"
    assert m[3].mtib_host == "h3"


def test_slot_bindings_by_index_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate slot_index"):
        slot_bindings_by_index([
            SlotBinding(slot_index=0, serial_number=None, device_id=None,
                        mtib_host="h", mtib_port=1),
            SlotBinding(slot_index=0, serial_number=None, device_id=None,
                        mtib_host="h2", mtib_port=1),
        ])


# ────────────────────────────────────────────────────────────────────────
# Purity — no side effects
# ────────────────────────────────────────────────────────────────────────


def test_resolve_does_not_mutate_env(clean_env):
    clean_env.setenv("MTIB_HOSTS", "h0,h1")
    clean_env.setenv("SLOT_SNRS", "s0,s1")
    before = {k: os.environ.get(k) for k in ("MTIB_HOSTS", "SLOT_SNRS")}
    resolve_slot_bindings()
    after = {k: os.environ.get(k) for k in ("MTIB_HOSTS", "SLOT_SNRS")}
    assert before == after


def test_resolve_returns_independent_copies(clean_env):
    """Two calls must return independent lists — mutating one shouldn't affect the other."""
    clean_env.setenv("MTIB_HOSTS", "h0,h1")
    a = resolve_slot_bindings()
    b = resolve_slot_bindings()
    assert a == b
    a.clear()
    assert len(b) == 2  # b is not affected
