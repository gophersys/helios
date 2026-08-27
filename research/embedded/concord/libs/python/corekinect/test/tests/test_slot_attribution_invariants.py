"""Lock the MTIB ↔ slot ↔ SNR alignment that the entire framework rests on.

Every payload the reporter emits, every pytest item parametrization,
and every ``SlotContext.mtib`` returned by the slot fixture must agree
on the same indexing of slots. Contract:

* ``MTIB_HOSTS[N]`` → host for slot N (positional in the env var).
* ``SLOT_SNRS`` is sent by the runner with one entry per slot in
  ``MTIB_HOSTS`` (blanks for slots not in this run); the resolver
  strips blanks and matches the remaining count to the filtered
  slot count, so the surviving SNRs land on the surviving slots in
  order.
* ``SLOT_FILTER`` does NOT renumber — slot-3 stays slot-3 even when
  slot-2 is excluded.

If any parser drifts (the framework historically had three), the
parametrization stops aligning to the fixture context and you get
cross-slot data leaks. These tests pin the invariant so refactors
can't break it silently.

Two parsers must agree on every input env:
  * :func:`corekinect.test.slot_env.resolve_slot_bindings` — canonical
  * :func:`corekinect.test.slot.get_slot_ids_from_env` — used by the
    ``slot`` fixture's ``params=`` argument
"""

from __future__ import annotations

import json
from typing import Tuple

import pytest

from corekinect.test.slot import get_slot_ids_from_env
from corekinect.test.slot_env import (
    resolve_slot_bindings,
    slot_bindings_by_index,
)

pytest_plugins = ["pytester"]


# ────────────────────────────────────────────────────────────────────────
# Env helpers
# ────────────────────────────────────────────────────────────────────────


def _set_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hosts: str = "",
    snrs: str = "",
    device_ids: str = "",
    slot_filter: str = "",
) -> None:
    """Reset the slot-attribution env vars to a known-clean baseline."""
    for var in (
        "MTIB_HOSTS", "MTIB_HOST", "MTIB_ADDRESS",
        "SLOT_SNRS", "SLOT_DEVICE_IDS", "SLOT_FILTER",
        "FIXTURE_CONFIG_PATH",
    ):
        monkeypatch.delenv(var, raising=False)
    if hosts:
        monkeypatch.setenv("MTIB_HOSTS", hosts)
    if snrs:
        monkeypatch.setenv("SLOT_SNRS", snrs)
    if device_ids:
        monkeypatch.setenv("SLOT_DEVICE_IDS", device_ids)
    if slot_filter:
        monkeypatch.setenv("SLOT_FILTER", slot_filter)


# ────────────────────────────────────────────────────────────────────────
# Parser-agreement contract
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hosts, snrs, slot_filter, expected_ids",
    [
        # No env at all → single-slot fallback. Both parsers agree on
        # `["slot-0"]` (used by single-slot validation runs).
        ("", "", "", ["slot-0"]),
        # Single host explicit → still slot-0 only.
        ("10.0.0.1:50053", "", "", ["slot-0"]),
        # 4-slot panel.
        (
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
            "095F,095G,095H,095J",
            "",
            ["slot-0", "slot-1", "slot-2", "slot-3"],
        ),
        # Whitespace tolerance — both parsers must handle the same way.
        (
            "  10.0.0.1:50053  ,  10.0.0.2:50053  ",
            "095F,095G",
            "",
            ["slot-0", "slot-1"],
        ),
        # Trailing comma must NOT phantom-add a slot.
        (
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,",
            "095F,095G,095H",
            "",
            ["slot-0", "slot-1", "slot-2"],
        ),
        # SLOT_FILTER preserves global indices — slot-3 stays slot-3
        # even when slot-2 is excluded.
        (
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
            "095F,095G,095H,095J",
            "0,1,3",
            ["slot-0", "slot-1", "slot-3"],
        ),
        # Single-slot panel via SLOT_FILTER (manufacturing baseline path).
        (
            "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
            "095F,095G,095H,095J",
            "2",
            ["slot-2"],
        ),
    ],
    ids=[
        "no-env",
        "single-host",
        "four-slot-panel",
        "whitespace-tolerant",
        "trailing-comma",
        "slot-filter-skips-middle",
        "slot-filter-single",
    ],
)
def test_get_slot_ids_matches_resolve_slot_bindings(
    monkeypatch: pytest.MonkeyPatch,
    hosts: str,
    snrs: str,
    slot_filter: str,
    expected_ids: list,
) -> None:
    """The slot fixture's parametrizer must produce the same IDs the
    binding resolver does — otherwise the [slot-N] suffix in the
    nodeid stops aligning to the binding stashed on the item.
    """
    _set_env(monkeypatch, hosts=hosts, snrs=snrs, slot_filter=slot_filter)

    fixture_ids = get_slot_ids_from_env()

    bindings = resolve_slot_bindings()
    binding_ids = (
        [f"slot-{b.slot_index}" for b in bindings] if bindings else ["slot-0"]
    )

    assert fixture_ids == expected_ids, (
        f"slot fixture parametrizer drift: expected {expected_ids}, "
        f"got {fixture_ids}"
    )
    assert binding_ids == expected_ids, (
        f"binding resolver drift: expected {expected_ids}, got {binding_ids}"
    )
    assert fixture_ids == binding_ids, (
        f"PARSER DRIFT — fixture says {fixture_ids} but bindings say {binding_ids}. "
        "This breaks MTIB↔slot↔SNR alignment at runtime."
    )


# ────────────────────────────────────────────────────────────────────────
# Positional alignment of MTIB / SNR / device-id to slot_index
# ────────────────────────────────────────────────────────────────────────


def test_binding_mtib_host_matches_positional_mtib_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``binding[N].mtib_host`` must equal ``MTIB_HOSTS.split(',')[N]``."""
    hosts_csv = "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053"
    _set_env(
        monkeypatch,
        hosts=hosts_csv,
        snrs="095F,095G,095H,095J",
    )
    bindings_by_idx = slot_bindings_by_index(resolve_slot_bindings())
    expected_hosts = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]
    for i, expected_host in enumerate(expected_hosts):
        assert bindings_by_idx[i].mtib_host == expected_host, (
            f"slot-{i} mtib_host expected {expected_host!r}, "
            f"got {bindings_by_idx[i].mtib_host!r}"
        )


def test_binding_serial_number_matches_positional_slot_snrs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``binding[N].serial_number`` must equal ``SLOT_SNRS.split(',')[N]``."""
    _set_env(
        monkeypatch,
        hosts="10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
        snrs="095F,095G,095H,095J",
    )
    bindings_by_idx = slot_bindings_by_index(resolve_slot_bindings())
    expected_snrs = ["095F", "095G", "095H", "095J"]
    for i, expected_snr in enumerate(expected_snrs):
        assert bindings_by_idx[i].serial_number == expected_snr, (
            f"slot-{i} serial_number expected {expected_snr!r}, "
            f"got {bindings_by_idx[i].serial_number!r}"
        )


def test_slot_filter_preserves_global_index_in_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SLOT_FILTER=0,1,3`` keeps slot-3 numbered slot-3 (NOT slot-2).

    This is the load-bearing invariant for partial-panel runs:
    when slot-2 is excluded, slot-3 must still hit MTIB_HOSTS[3] —
    never reindexed.

    The production runner (mfg_runner.py) sends SLOT_SNRS with one
    entry per slot in MTIB_HOSTS, with blanks for slots excluded by
    the filter. The resolver strips those blanks before matching to
    the filtered count, so surviving SNRs land on surviving slots in
    order. We model that here.
    """
    _set_env(
        monkeypatch,
        hosts="10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053,10.0.0.4:50053",
        snrs="095F,095G,,095J",  # blank for excluded slot-2
        slot_filter="0,1,3",
    )
    bindings = resolve_slot_bindings()
    indices = [b.slot_index for b in bindings]
    assert indices == [0, 1, 3], (
        f"SLOT_FILTER renumbered indices: expected [0,1,3], got {indices}"
    )
    by_idx = slot_bindings_by_index(bindings)
    # slot-3 must still resolve to host 10.0.0.4 / snr 095J.
    assert by_idx[3].mtib_host == "10.0.0.4"
    assert by_idx[3].serial_number == "095J"
    # slot-0 and slot-1 keep their SNRs.
    assert by_idx[0].serial_number == "095F"
    assert by_idx[1].serial_number == "095G"
    # slot-2 must NOT be present.
    assert 2 not in by_idx


def test_device_ids_align_positionally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``binding[N].device_id`` aligns to ``SLOT_DEVICE_IDS.split(',')[N]``."""
    _set_env(
        monkeypatch,
        hosts="10.0.0.1:50053,10.0.0.2:50053",
        snrs="095F,095G",
        device_ids="dev-aaa,dev-bbb",
    )
    by_idx = slot_bindings_by_index(resolve_slot_bindings())
    assert by_idx[0].device_id == "dev-aaa"
    assert by_idx[1].device_id == "dev-bbb"


# ────────────────────────────────────────────────────────────────────────
# End-to-end via the slot fixture (integration-shaped, in-process)
# ────────────────────────────────────────────────────────────────────────


def test_slot_fixture_returns_slot_for_correct_mtib(
    monkeypatch: pytest.MonkeyPatch, pytester: pytest.Pytester,
) -> None:
    """A pytester run with a 3-slot env produces 3 parametrized items
    whose [slot-N] nodeid suffix lines up with the binding's slot_index
    AND with positional MTIB_HOSTS / SLOT_SNRS.

    This is the proof that an entire pytest collection + parametrization
    cycle preserves the alignment end-to-end, not just at the resolver.
    """
    monkeypatch.setenv(
        "MTIB_HOSTS",
        "10.0.0.1:50053,10.0.0.2:50053,10.0.0.3:50053",
    )
    monkeypatch.setenv("SLOT_SNRS", "AAA,BBB,CCC")

    pytester.makepyfile(test_alignment="""
        import json, os
        from corekinect.test.slot_env import resolve_slot_bindings, slot_bindings_by_index
        from corekinect.test.slot import get_slot_ids_from_env

        OBSERVED_PATH = os.environ['_TEST_OBS']

        def _observe(payload):
            with open(OBSERVED_PATH, 'a') as f:
                f.write(json.dumps(payload) + "\\n")

        import pytest

        @pytest.fixture(params=get_slot_ids_from_env())
        def slot_id(request):
            return request.param

        def test_alignment(slot_id):
            n = int(slot_id.split('-')[1])
            by_idx = slot_bindings_by_index(resolve_slot_bindings())
            b = by_idx.get(n)
            assert b is not None, f"binding missing for {slot_id}"
            _observe({
                'slot_id': slot_id,
                'binding_index': b.slot_index,
                'mtib_host': b.mtib_host,
                'serial_number': b.serial_number,
            })
    """)
    obs_path = str(pytester.path / "observations.jsonl")
    monkeypatch.setenv("_TEST_OBS", obs_path)

    result = pytester.runpytest("-p", "no:cacheprovider", "-p", "no:randomly", "-q")
    result.assert_outcomes(passed=3)

    rows = []
    with open(obs_path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["binding_index"])

    assert [r["slot_id"] for r in rows] == ["slot-0", "slot-1", "slot-2"]
    assert [r["binding_index"] for r in rows] == [0, 1, 2]
    assert [r["mtib_host"] for r in rows] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    assert [r["serial_number"] for r in rows] == ["AAA", "BBB", "CCC"]
