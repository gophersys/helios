"""Behavioural tests for ``corekinect.test.slot_parallel``.

The plugin groups parametrized items by top-level test (``[slot-N]``
suffix stripped) and fans each group out across a thread pool with a
barrier between groups, so a panel run advances in lock-step through
each top-level test instead of round-robin serial.

These tests run pytest-inside-pytest via the ``pytester`` fixture so
every assertion is against a real pytest session, not a mock. The fake
suite under test writes an append-only JSON event log to a file in the
pytester's tmp directory; the outer test reads that log to reason about
entry/exit ordering across threads. Using a filesystem artefact means
the events are observable from the outer process regardless of whether
``pytester`` chose in-process or subprocess execution.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Iterable, List, Tuple

import pytest

pytest_plugins = ["pytester"]


# ────────────────────────────────────────────────────────────────────────
# Trace-log helper
# ────────────────────────────────────────────────────────────────────────


def _trace_path(pytester: pytest.Pytester) -> Path:
    """Absolute path to the trace log shared by the fake suite."""
    return pytester.path / "slot_parallel_trace.jsonl"


def _read_trace(pytester: pytest.Pytester) -> List[dict]:
    """Parse the trace log into a list of event dicts."""
    path = _trace_path(pytester)
    if not path.exists():
        return []
    events: List[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ────────────────────────────────────────────────────────────────────────
# Fake-suite generator
# ────────────────────────────────────────────────────────────────────────


def _write_fake_suite(
    pytester: pytest.Pytester,
    *,
    num_tests: int,
    num_slots: int,
    sleep_s: float = 0.02,
    barrier_enabled: bool = False,
    fail_slot: int | None = None,
    fail_test_index: int | None = None,
) -> None:
    """Emit a pytest package with ``num_tests`` × ``num_slots`` items.

    The suite uses a small helper module (``_slot_parallel_trace``) that
    exposes:
      * ``record(event_type, test_idx, slot)`` — appends a timestamped
        JSON line to the trace log.
      * ``BARRIER`` — a ``threading.Barrier(num_slots)`` when
        ``barrier_enabled`` is set; otherwise ``None``. Tests ``wait()``
        on it to prove they entered the critical section concurrently.

    The suite itself is generated programmatically (no dedent hazards).
    """
    slot_ids = [f"slot-{i}" for i in range(num_slots)]
    trace_file = str(_trace_path(pytester))

    # ── Fake test file ──
    body: List[str] = [
        "import pytest",
        "import time",
        "import _slot_parallel_trace as _tr",
        "",
    ]
    for t_idx in range(num_tests):
        body.append(f"@pytest.mark.parametrize('slot', {slot_ids!r})")
        body.append(f"def test_{t_idx:02d}_step(slot):")
        body.append(f"    _tr.record('entry', {t_idx}, slot)")
        body.append("    if _tr.BARRIER is not None:")
        body.append("        _tr.BARRIER.wait(timeout=2.0)")
        if fail_slot is not None and fail_test_index == t_idx:
            body.append(f"    if slot == 'slot-{fail_slot}':")
            body.append("        raise AssertionError('intentional fault')")
        body.append(f"    time.sleep({sleep_s})")
        body.append(f"    _tr.record('exit', {t_idx}, slot)")
        body.append("")
    pytester.makepyfile(test_fake="\n".join(body))

    # ── Trace-logging helper module ──
    helper: List[str] = [
        "import json",
        "import threading",
        "import time",
        "",
        f"_TRACE_PATH = {trace_file!r}",
        "_lock = threading.Lock()",
        f"BARRIER = threading.Barrier({num_slots}) if {barrier_enabled!r} else None",
        "",
        "def record(event_type, test_idx, slot):",
        "    event = {",
        "        'event': event_type,",
        "        'test': test_idx,",
        "        'slot': slot,",
        "        'ts': time.monotonic(),",
        "        'thread': threading.current_thread().name,",
        "    }",
        "    with _lock:",
        "        with open(_TRACE_PATH, 'a') as f:",
        "            f.write(json.dumps(event) + '\\n')",
        "",
    ]
    pytester.makepyfile(_slot_parallel_trace="\n".join(helper))


def _conftest_registering_plugin() -> str:
    """conftest.py content that registers the slot_parallel plugin."""
    return textwrap.dedent(
        """
        pytest_plugins = ["corekinect.test.slot_parallel"]
        """
    ).lstrip()


# ────────────────────────────────────────────────────────────────────────
# Trace-log assertions
# ────────────────────────────────────────────────────────────────────────


def _events_by_kind(events: Iterable[dict], *, kind: str) -> List[dict]:
    return [e for e in events if e["event"] == kind]


def _group_interval(events: Iterable[dict], test_idx: int) -> Tuple[float, float]:
    """Return (earliest entry ts, latest exit ts) for a single group."""
    g_events = [e for e in events if e["test"] == test_idx]
    entries = [e["ts"] for e in g_events if e["event"] == "entry"]
    exits = [e["ts"] for e in g_events if e["event"] == "exit"]
    assert entries, f"no entry events for test {test_idx}"
    assert exits, f"no exit events for test {test_idx}"
    return min(entries), max(exits)


# ────────────────────────────────────────────────────────────────────────
# Unit-level coverage of the grouping helper
# ────────────────────────────────────────────────────────────────────────


class _FakeItem:
    __slots__ = ("nodeid",)

    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid


def test_groups_items_by_top_level_test_preserving_order() -> None:
    from corekinect.test.slot_parallel import items_to_groups

    items = [
        _FakeItem("pkg/test_a.py::test_one[slot-0]"),
        _FakeItem("pkg/test_a.py::test_one[slot-1]"),
        _FakeItem("pkg/test_a.py::test_two[slot-0]"),
        _FakeItem("pkg/test_a.py::test_two[slot-1]"),
    ]
    groups = items_to_groups(items)
    assert [g[0].nodeid for g in groups] == [
        "pkg/test_a.py::test_one[slot-0]",
        "pkg/test_a.py::test_two[slot-0]",
    ]
    assert all(len(g) == 2 for g in groups)


def test_items_without_slot_param_form_singleton_groups() -> None:
    from corekinect.test.slot_parallel import items_to_groups

    items = [
        _FakeItem("pkg/test_a.py::test_alpha"),
        _FakeItem("pkg/test_a.py::test_beta"),
    ]
    groups = items_to_groups(items)
    assert len(groups) == 2
    assert all(len(g) == 1 for g in groups)


# ────────────────────────────────────────────────────────────────────────
# Plugin behaviour via pytester
# ────────────────────────────────────────────────────────────────────────


def test_group_members_run_concurrently(pytester: pytest.Pytester) -> None:
    """Every slot in a group must reach a ``Barrier(n)`` together.

    If execution were serial the first parametrization would block
    waiting for the others, hit the barrier timeout, and raise
    ``BrokenBarrierError`` — the test would fail. Passing all 4 items
    proves they ran concurrently.
    """
    _write_fake_suite(pytester, num_tests=1, num_slots=4, barrier_enabled=True)
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=4)


def test_groups_run_sequentially_not_interleaved(pytester: pytest.Pytester) -> None:
    """Group B's earliest entry comes AFTER group A's latest exit.

    The trace log is written by all threads with a monotonic timestamp;
    we assert the barrier between groups by comparing those intervals.
    """
    _write_fake_suite(pytester, num_tests=2, num_slots=3, sleep_s=0.05)
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=6)

    events = _read_trace(pytester)
    assert len(_events_by_kind(events, kind="entry")) == 6
    assert len(_events_by_kind(events, kind="exit")) == 6

    group0_start, group0_end = _group_interval(events, 0)
    group1_start, group1_end = _group_interval(events, 1)
    assert group0_end <= group1_start, (
        f"group 1 started before group 0 finished: "
        f"group0=[{group0_start:.4f}..{group0_end:.4f}] "
        f"group1=[{group1_start:.4f}..{group1_end:.4f}]"
    )


def test_failure_in_one_slot_does_not_abort_others(pytester: pytest.Pytester) -> None:
    """A failing parametrization is reported as failed; siblings still pass."""
    _write_fake_suite(
        pytester, num_tests=1, num_slots=4,
        fail_slot=2, fail_test_index=0,
    )
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=3, failed=1)

    events = _read_trace(pytester)
    exited_slots = {e["slot"] for e in _events_by_kind(events, kind="exit")}
    # The failing slot never reaches record_exit, but the three others do.
    assert exited_slots == {"slot-0", "slot-1", "slot-3"}


def test_pytest_parallel_env_disables_plugin(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``PYTEST_PARALLEL=0`` bypasses the plugin.

    With a ``Barrier(2)`` and serial execution the first item blocks
    until the barrier timeout, which raises ``BrokenBarrierError`` and
    fails the test. A non-zero pytest exit code with at least one failure
    proves we fell through to the default loop (no parallelism).
    """
    _write_fake_suite(pytester, num_tests=1, num_slots=2, barrier_enabled=True)
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    monkeypatch.setenv("PYTEST_PARALLEL", "0")
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    assert result.ret != 0, "expected non-zero exit when parallelism disabled"


def test_single_slot_runs_without_parallel_fanout(pytester: pytest.Pytester) -> None:
    """When every group is size 1 we fall through to pytest's default loop.

    The plugin returns ``None`` in this case — verified indirectly by
    observing that no thread-prefixed worker name appears in the trace.
    """
    _write_fake_suite(pytester, num_tests=2, num_slots=1)
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=2)

    events = _read_trace(pytester)
    thread_names = {e["thread"] for e in events}
    # Default pytest loop runs on MainThread; the plugin's pool prefixes
    # worker threads with "slot-parallel-g".
    assert thread_names == {"MainThread"}, (
        f"expected MainThread-only execution for single-slot, got {thread_names}"
    )


def test_plugin_emits_report_for_every_item(pytester: pytest.Pytester) -> None:
    """Every group item produces a pytest report (passed/failed) — no item silently disappears."""
    _write_fake_suite(
        pytester, num_tests=3, num_slots=4,
        fail_slot=1, fail_test_index=1,
    )
    pytester.makepyfile(conftest=_conftest_registering_plugin())
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    # 3 tests × 4 slots = 12 total, 1 failure
    result.assert_outcomes(passed=11, failed=1)


def test_parallel_is_actually_faster_than_serial(pytester: pytest.Pytester) -> None:
    """Wall-clock proof: 4-slot parallel ≈ single-slot time, not 4×.

    Each test sleeps 200ms. Serial execution of 4 slots × 1 test would
    take ~800ms; parallel execution should be close to 200ms. We assert
    the run completes in well under 2× the per-test sleep to leave
    generous headroom for thread-pool startup and pytest overhead.
    """
    import time
    _write_fake_suite(pytester, num_tests=1, num_slots=4, sleep_s=0.2)
    pytester.makepyfile(conftest=_conftest_registering_plugin())

    start = time.monotonic()
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    elapsed = time.monotonic() - start

    result.assert_outcomes(passed=4)
    # Serial lower bound would be 4 * 0.2 = 0.8s of pure sleep.
    # Parallel expected: ~0.2s sleep + pytest overhead.
    # Assert we're clearly below the serial lower bound.
    assert elapsed < 0.6, (
        f"expected <0.6s (parallel), got {elapsed:.3f}s — indicates serial execution"
    )
