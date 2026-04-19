"""Tests for collection-time ``SlotBinding`` attachment in ``autoconf``.

The ``autoconf`` plugin owns the single pytest hook that reads the
environment at collection time and stashes a :class:`SlotBinding` on
every item parametrized as ``[slot-N]``. Downstream consumers
(reporter, telemetry, backend attribution) read the stash instead of
re-deriving attribution at each hook.

These tests run pytest-inside-pytest via the ``pytester`` fixture so
the behaviour under test is the real ``pytest_collection_modifyitems``
hook registered by the plugin, not a mocked reimplementation.

Contracts exercised
-------------------

* Every ``[slot-N]`` item gets a ``SlotBinding`` whose ``slot_index``
  matches the nodeid suffix.
* Items without ``[slot-N]`` (single-slot validation) get NO stash
  entry — unparametrized tests stay untouched.
* Bindings reflect ``MTIB_HOSTS`` / ``SLOT_SNRS`` / ``SLOT_DEVICE_IDS``
  / ``MTIB_PORT`` exactly — collection-time attribution is the single
  source of truth.
* Running the hook twice (e.g. during test reruns or plugin
  composition) is idempotent — :func:`attach_binding` already rejects
  divergence but accepts identical bindings.
* ``SLOT_FILTER`` narrows the items that collect at all via the
  ``slot`` fixture's ``params=_get_slot_ids()``; the plugin does not
  need to reject filtered items — pytest never produces them.
* When ``MTIB_HOSTS`` is unset the plugin is a no-op: no stash
  attachment, no errors, and items that happen to contain a
  ``[slot-N]`` literal still have no binding.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import List

import pytest

pytest_plugins = ["pytester"]


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _dump_path(pytester: pytest.Pytester) -> Path:
    """Path where the fake conftest dumps collected binding info."""
    return pytester.path / "stash_dump.json"


def _write_binding_collector_conftest(pytester: pytest.Pytester) -> None:
    """Write a conftest.py that runs after autoconf and dumps every item's stash.

    The conftest uses ``pytest_collection_modifyitems(tryfirst=False,
    trylast=True)`` so it observes stashes attached by autoconf. It
    writes a JSON list of ``{nodeid, slot_index?, serial?, ...}``
    entries into the pytester tmp dir for the outer test to read.
    """
    dump_path = str(_dump_path(pytester))
    body = f'''
import json

import pytest

from corekinect.test.slot_binding import SLOT_BINDING_KEY

pytest_plugins = ["corekinect.test.autoconf"]


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    entries = []
    for item in items:
        binding = item.stash.get(SLOT_BINDING_KEY, None)
        entry = {{"nodeid": item.nodeid, "has_binding": binding is not None}}
        if binding is not None:
            entry.update({{
                "slot_index": binding.slot_index,
                "serial_number": binding.serial_number,
                "device_id": binding.device_id,
                "mtib_host": binding.mtib_host,
                "mtib_port": binding.mtib_port,
            }})
        entries.append(entry)
    with open({dump_path!r}, "w") as fh:
        json.dump(entries, fh)
'''
    pytester.makeconftest(textwrap.dedent(body))


def _write_manifest(pytester: pytest.Pytester) -> None:
    """Write a minimal manifest so autoconf registers itself.

    Without a ``concord.yaml`` file, autoconf is a silent no-op — it
    doesn't even register the collection hook. The test app we are
    pretending to be needs a bare-minimum multi_slot manifest.
    """
    pytester.makefile(
        ".yaml",
        **{"concord": textwrap.dedent("""
            schema: "2.0"

            package:
              type: manufacturing
              version: "1.0.0"
              framework: ">=0.2.0"

            product:
              slug: test_b0
              board: b0
              device:
                type_id: 99
                variant_id: 1

            fixture:
              design: Test Fixture
              revision: "1.0"
              controller: tests.common._harness.NoopFixture
              profile: fixtures/test.yaml
              multi_slot: true

            stages: {}
        """).lstrip()},
    )


def _write_slot_parametrized_tests(
    pytester: pytest.Pytester, *, test_names: List[str]
) -> None:
    """Write a test module whose tests are parametrized by ``[slot-N]``.

    We can't rely on the real ``slot`` fixture (requires MTIB config),
    so we synthesize the same nodeid shape with a plain ``parametrize``.
    The stash attachment looks at the nodeid, not the fixture source.
    """
    lines = ["import pytest", ""]
    for name in test_names:
        lines.append(
            "@pytest.mark.parametrize('slot', "
            "['slot-0', 'slot-1', 'slot-2', 'slot-3'])"
        )
        lines.append(f"def {name}(slot):")
        lines.append("    assert slot")
        lines.append("")
    pytester.makepyfile(test_fake="\n".join(lines))


def _write_unparametrized_tests(
    pytester: pytest.Pytester, *, test_names: List[str]
) -> None:
    """Write plain tests with no ``[slot-N]`` parametrization."""
    lines = ["def _noop():", "    return True", ""]
    for name in test_names:
        lines.append(f"def {name}():")
        lines.append("    assert _noop()")
        lines.append("")
    pytester.makepyfile(test_plain="\n".join(lines))


def _read_dump(pytester: pytest.Pytester) -> List[dict]:
    """Read the JSON dump produced by the collector conftest."""
    path = _dump_path(pytester)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every MTIB/SLOT env var so each case starts clean."""
    for var in (
        "MTIB_HOSTS", "MTIB_HOST", "MTIB_ADDRESS", "MTIB_PORT",
        "SLOT_FILTER", "SLOT_SNRS", "SLOT_DEVICE_IDS",
        "FIXTURE_CONFIG_PATH", "PYTEST_PARALLEL",
    ):
        monkeypatch.delenv(var, raising=False)


# ────────────────────────────────────────────────────────────────────────
# Multi-slot runs — every [slot-N] item gets a binding
# ────────────────────────────────────────────────────────────────────────


def test_every_slot_item_gets_a_binding(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha", "test_beta"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    assert entries, "collector conftest never wrote its dump"

    # 2 tests x 4 slots = 8 parametrized items, all stashed.
    parametrized = [e for e in entries if "[slot-" in e["nodeid"]]
    assert len(parametrized) == 8
    assert all(e["has_binding"] for e in parametrized)


def test_binding_slot_index_matches_nodeid(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    by_slot = {e["nodeid"]: e for e in entries if e["has_binding"]}

    for nodeid, entry in by_slot.items():
        # nodeid is ``...::test_alpha[slot-N]`` — extract N.
        suffix = nodeid.split("[slot-", 1)[1].rstrip("]")
        assert entry["slot_index"] == int(suffix), (
            f"item {nodeid} has slot_index={entry['slot_index']}, "
            f"expected {suffix}"
        )


def test_binding_carries_host_and_port(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "10.4.45.36:50099,10.4.45.39")
    monkeypatch.setenv("MTIB_PORT", "50053")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    # Only collect two items (slot-0, slot-1) because only 2 hosts in MTIB_HOSTS.
    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
        "-k", "slot-0 or slot-1",
    )
    assert result.ret == 0, result.stdout.str()

    entries = [e for e in _read_dump(pytester) if e["has_binding"]]
    by_idx = {e["slot_index"]: e for e in entries}
    assert by_idx[0]["mtib_host"] == "10.4.45.36"
    assert by_idx[0]["mtib_port"] == 50099  # per-address override wins
    assert by_idx[1]["mtib_host"] == "10.4.45.39"
    assert by_idx[1]["mtib_port"] == 50053  # MTIB_PORT default


def test_binding_reflects_slot_snrs(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    monkeypatch.setenv("SLOT_SNRS", "095F,095G,095H,095J")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = [e for e in _read_dump(pytester) if e["has_binding"]]
    by_idx = {e["slot_index"]: e for e in entries}
    assert by_idx[0]["serial_number"] == "095F"
    assert by_idx[1]["serial_number"] == "095G"
    assert by_idx[2]["serial_number"] == "095H"
    assert by_idx[3]["serial_number"] == "095J"


def test_binding_reflects_device_ids(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1")
    monkeypatch.setenv("SLOT_DEVICE_IDS", "0001,0002")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = [e for e in _read_dump(pytester) if e["has_binding"]]
    by_idx = {e["slot_index"]: e for e in entries}
    assert by_idx[0]["device_id"] == "0001"
    assert by_idx[1]["device_id"] == "0002"


# ────────────────────────────────────────────────────────────────────────
# Single-slot / unparametrized — no stash entry
# ────────────────────────────────────────────────────────────────────────


def test_unparametrized_tests_have_no_binding(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Items without ``[slot-N]`` in the nodeid get no stash entry.

    Single-slot validation runs never parametrize by slot. The plugin
    must leave those items alone so the reporter's no-binding fallback
    kicks in (single-target backend resolution).
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1")  # still multi-slot env
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_unparametrized_tests(pytester, test_names=["test_alpha", "test_beta"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    assert len(entries) == 2
    assert all(not e["has_binding"] for e in entries)


def test_plugin_is_noop_when_mtib_hosts_unset(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``MTIB_HOSTS`` unset → no bindings attached, no errors.

    This is the normal single-slot validation path. We still
    synthesize ``[slot-N]`` nodeids to prove that even tests whose
    names happen to contain that suffix don't get stashed when the
    environment has no attribution info.
    """
    _clean_env(monkeypatch)
    # Deliberately do NOT set MTIB_HOSTS.
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    # Tests still collected (parametrize only needs the id strings),
    # but NO binding attached because resolve_slot_bindings() returned [].
    assert all(not e["has_binding"] for e in entries), entries


# ────────────────────────────────────────────────────────────────────────
# SLOT_FILTER narrowing
# ────────────────────────────────────────────────────────────────────────


def test_slot_filter_still_attaches_binding_to_filtered_items(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``SLOT_FILTER=4`` the one remaining item (slot-4) gets a binding.

    We exercise only the filter's effect on binding resolution — the
    pytest ``params`` list is a separate concern covered by
    ``_get_slot_ids()`` and the ``slot`` fixture (tested in
    ``test_slot_binding.py``). Here we manually parametrize to
    ``slot-0..slot-4`` and use ``-k`` to narrow to slot-4 so the
    assertion is about *our* item receiving a binding with
    ``slot_index=4``, the *global* index.
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3,h4")
    monkeypatch.setenv("SLOT_FILTER", "4")
    monkeypatch.setenv("SLOT_SNRS", "standalone-snr")
    _write_manifest(pytester)
    _write_binding_collector_conftest(pytester)

    # Parametrize 0..4 ourselves.
    pytester.makepyfile(test_fake=textwrap.dedent('''
        import pytest

        @pytest.mark.parametrize(
            "slot",
            ["slot-0", "slot-1", "slot-2", "slot-3", "slot-4"],
        )
        def test_alpha(slot):
            assert slot
    '''))

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    # Only slot-4 has a binding because SLOT_FILTER=4 filtered the rest.
    bindings = [e for e in entries if e["has_binding"]]
    assert len(bindings) == 1, bindings
    b = bindings[0]
    assert b["slot_index"] == 4  # GLOBAL slot index, not filtered position
    assert b["mtib_host"] == "h4"
    assert b["serial_number"] == "standalone-snr"

    # slot-0..slot-3 have nodeids that look like [slot-N] but get no binding,
    # because resolve_slot_bindings() excluded those indices.
    unbound = [e for e in entries if not e["has_binding"]]
    assert len(unbound) == 4
    assert {
        int(e["nodeid"].split("[slot-", 1)[1].rstrip("]"))
        for e in unbound
    } == {0, 1, 2, 3}


# ────────────────────────────────────────────────────────────────────────
# Idempotency
# ────────────────────────────────────────────────────────────────────────


def test_running_collection_hook_twice_is_idempotent(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling ``attach_binding`` twice with the same binding is a no-op.

    Stream S1 already unit-tests this contract on
    :func:`attach_binding`; here we assert the autoconf hook actually
    relies on that semantic by re-invoking it and checking no
    ``ValueError`` escapes.
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    _write_manifest(pytester)

    # Collector conftest that invokes autoconf's hook a second time.
    dump_path = str(_dump_path(pytester))
    body = f'''
import json

import pytest

from corekinect.test import autoconf as _autoconf
from corekinect.test.slot_binding import SLOT_BINDING_KEY

pytest_plugins = ["corekinect.test.autoconf"]


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    # Re-run the autoconf hook by hand. This must not raise.
    _autoconf.pytest_collection_modifyitems(config, items)
    entries = []
    for item in items:
        binding = item.stash.get(SLOT_BINDING_KEY, None)
        entry = {{"nodeid": item.nodeid, "has_binding": binding is not None}}
        if binding is not None:
            entry["slot_index"] = binding.slot_index
        entries.append(entry)
    with open({dump_path!r}, "w") as fh:
        json.dump(entries, fh)
'''
    pytester.makeconftest(textwrap.dedent(body))
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    # All 4 items still carry one (and only one) binding.
    parametrized = [e for e in entries if "[slot-" in e["nodeid"]]
    assert len(parametrized) == 4
    assert all(e["has_binding"] for e in parametrized)


# ────────────────────────────────────────────────────────────────────────
# get_binding helper parity
# ────────────────────────────────────────────────────────────────────────


def test_get_binding_matches_direct_stash_read(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_binding(item)`` returns the same object as reading the stash.

    Stream S1 promises callers can use either API interchangeably; we
    assert that's still true after autoconf attaches the binding via
    the helper rather than a bare ``item.stash[...] = ...`` assignment.
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("MTIB_HOSTS", "h0,h1,h2,h3")
    _write_manifest(pytester)

    dump_path = str(_dump_path(pytester))
    body = f'''
import json

import pytest

from corekinect.test.slot_binding import SLOT_BINDING_KEY, get_binding

pytest_plugins = ["corekinect.test.autoconf"]


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    entries = []
    for item in items:
        via_stash = item.stash.get(SLOT_BINDING_KEY, None)
        via_helper = get_binding(item)
        entries.append({{
            "nodeid": item.nodeid,
            "match": (via_stash is via_helper),
            "has_binding": via_helper is not None,
        }})
    with open({dump_path!r}, "w") as fh:
        json.dump(entries, fh)
'''
    pytester.makeconftest(textwrap.dedent(body))
    _write_slot_parametrized_tests(pytester, test_names=["test_alpha"])

    result = pytester.runpytest(
        "--collect-only", "-q", "-p", "no:cacheprovider",
    )
    assert result.ret == 0, result.stdout.str()

    entries = _read_dump(pytester)
    assert entries
    # Every parametrized item's stash read matches the helper read.
    assert all(e["match"] for e in entries if e["has_binding"])
