"""Tests for the payload-builder-style :class:`ConcordReporter`.

The reporter is a near-stateless dispatcher: every outgoing payload is
built in one place (:meth:`ConcordReporter._emit`) that reads the
:class:`SlotBinding` stashed on the pytest item by S1's
:func:`attach_binding`, then POSTs via :meth:`_post`. No env sniffing at
test time, no thread-local device/slot propagation, no brittle regex
over nodeids.

These tests fake out :meth:`_post` with a list-capturing stub and
build fake pytest items via :class:`types.SimpleNamespace` plus a real
:class:`pytest.Stash`, so they run offline and parallel-safe.
"""

from __future__ import annotations

import threading
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from corekinect.test.reporter import (
    ConcordReporter,
    NoOpReporter,
    NoOpStepReporter,
    StepReporter,
)
from corekinect.test.slot_binding import SLOT_BINDING_KEY, SlotBinding


# ─────────────────────────────────────────────────────────────────────────────
# Fake-pytest helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_item(
    nodeid: str,
    *,
    binding: "SlotBinding | None" = None,
    name: str | None = None,
    funcargs: Dict[str, Any] | None = None,
) -> types.SimpleNamespace:
    """Build a minimal pytest-item-shaped object for the reporter to read.

    The reporter only touches ``item.nodeid``, ``item.name``,
    ``item.stash`` and ``item.funcargs`` — duplicating the full
    :class:`pytest.Item` surface would pull the whole pluggy graph in.
    """
    stash = pytest.Stash()
    if binding is not None:
        stash[SLOT_BINDING_KEY] = binding
    if name is None:
        name = nodeid.split("::")[-1]
    return types.SimpleNamespace(
        nodeid=nodeid,
        name=name,
        stash=stash,
        funcargs=funcargs or {},
    )


def _binding(
    slot_index: int,
    *,
    serial: str | None = None,
    device_id: str | None = None,
) -> SlotBinding:
    return SlotBinding(
        slot_index=slot_index,
        serial_number=serial,
        device_id=device_id,
        mtib_host=f"10.4.45.{36 + slot_index}",
        mtib_port=50053,
    )


def _fake_report(
    *,
    when: str = "call",
    passed: bool = True,
    failed: bool = False,
    skipped: bool = False,
    longrepr: Any = None,
    capstderr: str = "",
) -> types.SimpleNamespace:
    """Minimal ``TestReport``-shaped object used by ``pytest_runtest_makereport``."""
    return types.SimpleNamespace(
        when=when,
        passed=passed,
        failed=failed,
        skipped=skipped,
        longrepr=longrepr,
        capstderr=capstderr,
        capstdout="",
    )


class _CapturingReporter:
    """Wraps a :class:`ConcordReporter` with a list-capturing ``_post``.

    Threadsafe: every recorded ``(endpoint, payload)`` tuple is appended
    under a lock so the concurrent-slot tests can read the captured list
    after all worker threads have joined.
    """

    def __init__(self, reporter: ConcordReporter) -> None:
        self.reporter = reporter
        self.captured: List[Tuple[str, Dict[str, Any]]] = []
        self._lock = threading.Lock()
        self._patch = patch.object(reporter, "_post", side_effect=self._record)

    def _record(self, path: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            # Strip the ``report/`` prefix so assertions read ``execution-start``,
            # matching the S4 backend endpoints directly.
            endpoint = path[len("report/") :] if path.startswith("report/") else path
            self.captured.append((endpoint, dict(payload)))

    def __enter__(self) -> "_CapturingReporter":
        self._patch.start()
        return self

    def __exit__(self, *exc) -> None:
        self._patch.stop()

    def by_endpoint(self, endpoint: str) -> List[Dict[str, Any]]:
        return [p for e, p in self.captured if e == endpoint]


def _new_reporter(**overrides) -> ConcordReporter:
    kwargs = dict(
        run_id="run-abc",
        api_url="http://localhost:9001",
        api_key=None,
        enabled=True,
    )
    kwargs.update(overrides)
    return ConcordReporter(**kwargs)


# ═════════════════════════════════════════════════════════════════════════════
# Construction: explicit kwargs, no env sniffing
# ═════════════════════════════════════════════════════════════════════════════


def test_reporter_requires_explicit_kwargs() -> None:
    """``__init__`` takes named args and doesn't read the environment."""
    r = ConcordReporter(
        run_id="run-1", api_url="http://api", api_key="k", enabled=True
    )
    assert r.run_id == "run-1"
    assert r.api_url == "http://api"
    assert r.api_key == "k"
    assert r.enabled is True


def test_reporter_api_url_trailing_slash_stripped() -> None:
    r = ConcordReporter(run_id="r", api_url="http://api/", enabled=True)
    assert r.api_url == "http://api"


def test_reporter_defaults_api_key_none_enabled_true() -> None:
    r = ConcordReporter(run_id="r", api_url="http://api")
    assert r.api_key is None
    assert r.enabled is True


def test_reporter_can_be_disabled_via_kwarg() -> None:
    r = ConcordReporter(run_id="r", api_url="http://api", enabled=False)
    assert r.enabled is False


def test_from_env_returns_none_when_run_id_missing(monkeypatch) -> None:
    monkeypatch.delenv("CONCORD_RUN_ID", raising=False)
    monkeypatch.delenv("CONCORD_SESSION_ID", raising=False)
    monkeypatch.setenv("CONCORD_API_URL", "http://api")
    assert ConcordReporter.from_env() is None


def test_from_env_returns_none_when_api_url_missing(monkeypatch) -> None:
    monkeypatch.setenv("CONCORD_RUN_ID", "run-x")
    monkeypatch.delenv("CONCORD_API_URL", raising=False)
    assert ConcordReporter.from_env() is None


def test_from_env_builds_reporter_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CONCORD_RUN_ID", "run-x")
    monkeypatch.setenv("CONCORD_API_URL", "http://api")
    monkeypatch.setenv("CONCORD_API_KEY", "secret")
    r = ConcordReporter.from_env()
    assert r is not None
    assert r.run_id == "run-x"
    assert r.api_url == "http://api"
    assert r.api_key == "secret"


def test_from_env_prefers_session_id_over_run_id(monkeypatch) -> None:
    monkeypatch.setenv("CONCORD_RUN_ID", "legacy")
    monkeypatch.setenv("CONCORD_SESSION_ID", "new")
    monkeypatch.setenv("CONCORD_API_URL", "http://api")
    r = ConcordReporter.from_env()
    assert r is not None
    assert r.run_id == "new"


# ═════════════════════════════════════════════════════════════════════════════
# nodeid parsing
# ═════════════════════════════════════════════════════════════════════════════


def test_parse_nodeid_extracts_module_and_testname() -> None:
    from corekinect.test.reporter import _parse_nodeid

    module, name = _parse_nodeid(
        "tests/manufacturing/test_01_electrical.py::test_uvlo_off_state"
    )
    assert module == "test_01_electrical"
    assert name == "test_uvlo_off_state"


def test_parse_nodeid_handles_parametrized_name() -> None:
    from corekinect.test.reporter import _parse_nodeid

    module, name = _parse_nodeid("tests/x.py::test_boot[slot-2]")
    assert module == "x"
    assert name == "test_boot[slot-2]"


def test_parse_nodeid_handles_no_module_part() -> None:
    from corekinect.test.reporter import _parse_nodeid

    module, name = _parse_nodeid("test_plain")
    assert module is None
    assert name == "test_plain"


# ═════════════════════════════════════════════════════════════════════════════
# _emit reads stash; attribution only when binding is present
# ═════════════════════════════════════════════════════════════════════════════


def test_emit_adds_slot_index_when_binding_present() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t", binding=_binding(2, serial="095H"))
    with _CapturingReporter(r) as cap:
        r._emit(item, "execution-start", testName="t")
    start = cap.by_endpoint("execution-start")[0]
    assert start["slotIndex"] == 2
    assert start["deviceSerial"] == "095H"


def test_emit_omits_device_serial_when_binding_has_none_serial() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t", binding=_binding(4, serial=None))
    with _CapturingReporter(r) as cap:
        r._emit(item, "execution-start", testName="t")
    start = cap.by_endpoint("execution-start")[0]
    assert start["slotIndex"] == 4
    assert "deviceSerial" not in start


def test_emit_omits_attribution_when_stash_empty() -> None:
    """Single-target fallback path: no binding → no slotIndex/deviceSerial."""
    r = _new_reporter()
    item = _make_item("x.py::t_plain")  # no binding
    with _CapturingReporter(r) as cap:
        r._emit(item, "execution-start", testName="t_plain")
    start = cap.by_endpoint("execution-start")[0]
    assert "slotIndex" not in start
    assert "deviceSerial" not in start


def test_emit_is_noop_when_reporter_disabled() -> None:
    r = _new_reporter(enabled=False)
    item = _make_item("x.py::t", binding=_binding(0))
    with _CapturingReporter(r) as cap:
        r._emit(item, "execution-start", testName="t")
    assert cap.captured == []


def test_emit_strips_none_valued_fields() -> None:
    """Backwards compat: backend ignores unknown keys, dislikes explicit nulls."""
    r = _new_reporter()
    item = _make_item("x.py::t")
    with _CapturingReporter(r) as cap:
        r._emit(item, "execution-result", testName="t", errorMessage=None, passed=True)
    res = cap.by_endpoint("execution-result")[0]
    assert "errorMessage" not in res
    assert res["passed"] is True


# ═════════════════════════════════════════════════════════════════════════════
# pytest_runtest_setup → execution-start + target-start
# ═════════════════════════════════════════════════════════════════════════════


def test_setup_hook_fires_execution_start_with_attribution() -> None:
    r = _new_reporter()
    item = _make_item(
        "tests/m/test_boot.py::test_power[slot-2]",
        binding=_binding(2, serial="095H"),
    )
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
    starts = cap.by_endpoint("execution-start")
    assert len(starts) == 1
    assert starts[0]["slotIndex"] == 2
    assert starts[0]["deviceSerial"] == "095H"
    assert starts[0]["testName"] == "test_power[slot-2]"
    assert starts[0]["module"] == "test_boot"


def test_setup_hook_fires_target_start_once_per_slot() -> None:
    r = _new_reporter()
    b = _binding(0, serial="095F")
    with _CapturingReporter(r) as cap:
        for name in ("test_a", "test_b", "test_c"):
            item = _make_item(f"x.py::{name}[slot-0]", binding=b)
            r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, name))
            r.pytest_runtest_setup(item)
    targets = cap.by_endpoint("target-start")
    assert len(targets) == 1
    assert targets[0]["slotIndex"] == 0
    assert targets[0]["serialNumber"] == "095F"


def test_setup_hook_fires_target_start_once_per_distinct_slot() -> None:
    r = _new_reporter()
    with _CapturingReporter(r) as cap:
        for idx, serial in enumerate(("S0", "S1", "S2", "S3")):
            item = _make_item(
                f"x.py::t[slot-{idx}]", binding=_binding(idx, serial=serial)
            )
            r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, "t"))
            r.pytest_runtest_setup(item)
    targets = cap.by_endpoint("target-start")
    assert sorted(p["slotIndex"] for p in targets) == [0, 1, 2, 3]


def test_setup_hook_does_not_fire_target_start_when_binding_absent() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t_plain")
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, "t_plain"))
        r.pytest_runtest_setup(item)
    assert cap.by_endpoint("target-start") == []
    starts = cap.by_endpoint("execution-start")
    assert len(starts) == 1
    assert "slotIndex" not in starts[0]


# ═════════════════════════════════════════════════════════════════════════════
# pytest_runtest_makereport → execution-result
# ═════════════════════════════════════════════════════════════════════════════


def _drive_makereport(r: ConcordReporter, item, report) -> None:
    """Pump the hookwrapper the way pluggy would."""
    gen = r.pytest_runtest_makereport(item, call=types.SimpleNamespace())
    next(gen)  # advance to the ``yield``
    outcome = types.SimpleNamespace(get_result=lambda: report)
    try:
        gen.send(outcome)
    except StopIteration:
        pass


def test_makereport_call_pass_fires_execution_result() -> None:
    r = _new_reporter()
    item = _make_item("x.py::test_ok[slot-1]", binding=_binding(1, serial="S1"))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        _drive_makereport(r, item, _fake_report(when="call", passed=True))
    results = cap.by_endpoint("execution-result")
    assert len(results) == 1
    assert results[0]["slotIndex"] == 1
    assert results[0]["deviceSerial"] == "S1"
    assert results[0]["passed"] is True
    assert results[0]["testName"] == item.name


def test_makereport_call_failed_records_error_message() -> None:
    r = _new_reporter()
    item = _make_item("x.py::test_bad", binding=_binding(0))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        _drive_makereport(
            r,
            item,
            _fake_report(
                when="call",
                passed=False,
                failed=True,
                longrepr="boom traceback",
            ),
        )
    res = cap.by_endpoint("execution-result")[0]
    assert res["passed"] is False
    assert res["errorMessage"] == "boom traceback"


def test_makereport_non_call_phase_emits_nothing() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t", binding=_binding(0))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, "t"))
        r.pytest_runtest_setup(item)
        cap.captured.clear()
        _drive_makereport(r, item, _fake_report(when="teardown", passed=True))
    assert cap.by_endpoint("execution-result") == []


def test_setup_phase_skip_fires_execution_result_with_skipped_true() -> None:
    """Skip-path: setup-phase skip → execution-result ``skipped=True``."""
    r = _new_reporter()
    item = _make_item("x.py::t_skipped[slot-3]", binding=_binding(3, serial="S3"))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        _drive_makereport(
            r, item, _fake_report(when="setup", passed=False, skipped=True)
        )
    results = cap.by_endpoint("execution-result")
    assert len(results) == 1
    assert results[0]["skipped"] is True
    assert results[0]["passed"] is True
    assert results[0]["slotIndex"] == 3


def test_setup_phase_failure_fires_execution_result_with_error_message() -> None:
    """Fixture failure path: setup-phase failure → execution-result ``passed=False`` with error.

    Pytest reports a fixture exception as ``report.failed=True`` with
    ``report.when == "setup"`` and never invokes the call phase. Without
    explicit handling the execution row would never be updated, so the
    operator sees ``SKIPPED`` with no message and no idea why the fixture
    cascade-skipped downstream tests in the same slot.
    """
    r = _new_reporter()
    item = _make_item("x.py::t_boot[slot-2]", binding=_binding(2, serial="S2"))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        _drive_makereport(
            r, item,
            _fake_report(
                when="setup",
                passed=False,
                failed=True,
                longrepr="AssertionError: Failed to boot slot-2 after 3 attempts: shell lock timed out",
            ),
        )
    results = cap.by_endpoint("execution-result")
    assert len(results) == 1, f"expected 1 result, got {results}"
    payload = results[0]
    assert payload["passed"] is False
    assert payload["skipped"] is False
    assert "Failed to boot slot-2" in payload["errorMessage"]
    assert payload["slotIndex"] == 2
    assert payload["deviceSerial"] == "S2"


# ═════════════════════════════════════════════════════════════════════════════
# Concurrent slots — no cross-contamination
# ═════════════════════════════════════════════════════════════════════════════


def test_concurrent_slots_each_report_own_attribution() -> None:
    """Four threads, four slots — every payload carries its own slot index."""
    r = _new_reporter()
    slot_count = 4
    items = [
        _make_item(
            f"tests/x.py::test_boot[slot-{i}]",
            binding=_binding(i, serial=f"SNR-{i}"),
        )
        for i in range(slot_count)
    ]

    def run_one(item) -> None:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        _drive_makereport(r, item, _fake_report(when="call", passed=True))

    with _CapturingReporter(r) as cap:
        with ThreadPoolExecutor(max_workers=slot_count) as pool:
            list(pool.map(run_one, items))

    starts = cap.by_endpoint("execution-start")
    results = cap.by_endpoint("execution-result")
    assert len(starts) == slot_count
    assert len(results) == slot_count
    # Every start/result is self-consistent: slotIndex ↔ deviceSerial.
    for p in starts + results:
        assert p["deviceSerial"] == f"SNR-{p['slotIndex']}"
    # Every slot index saw exactly one target-start.
    targets = cap.by_endpoint("target-start")
    assert sorted(p["slotIndex"] for p in targets) == list(range(slot_count))


# ═════════════════════════════════════════════════════════════════════════════
# Session counters remain thread-safe
# ═════════════════════════════════════════════════════════════════════════════


def test_counters_exact_totals_under_load() -> None:
    r = _new_reporter()
    n_threads = 20
    per = 25

    def bump() -> None:
        for _ in range(per):
            with r._state_lock:
                r._total += 1
                r._passed += 1

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        futs = [pool.submit(bump) for _ in range(n_threads)]
        for f in as_completed(futs):
            f.result()
    assert r._total == n_threads * per
    assert r._passed == n_threads * per


def test_state_lock_is_reentrant() -> None:
    r = _new_reporter()
    with r._state_lock:
        with r._state_lock:
            r._passed += 1
    assert r._passed == 1


def test_makereport_increments_counters() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t", binding=_binding(0))
    with _CapturingReporter(r):
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, "t"))
        r.pytest_runtest_setup(item)
        _drive_makereport(r, item, _fake_report(when="call", passed=True))
    assert r._total == 1
    assert r._passed == 1
    assert r._failed == 0


# ═════════════════════════════════════════════════════════════════════════════
# Step reporting
# ═════════════════════════════════════════════════════════════════════════════


def test_step_emits_start_and_result_with_attribution() -> None:
    r = _new_reporter()
    item = _make_item("x.py::test_boot[slot-1]", binding=_binding(1, serial="S1"))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, item.name))
        r.pytest_runtest_setup(item)
        with r.step_for(item, "Apply voltage") as step:
            step.record("voltage", 3.3, unit="V")
    starts = cap.by_endpoint("step-start")
    results = cap.by_endpoint("step-result")
    assert len(starts) == 1 and starts[0]["slotIndex"] == 1
    assert len(results) == 1 and results[0]["slotIndex"] == 1
    assert starts[0]["stepName"] == "Apply voltage"
    assert results[0]["passed"] is True
    assert results[0]["measurements"]["voltage"] == {"value": 3.3, "unit": "V"}


def test_step_failure_is_recorded_but_not_suppressed() -> None:
    r = _new_reporter()
    item = _make_item("x.py::t", binding=_binding(0))
    with _CapturingReporter(r) as cap:
        r.pytest_runtest_logstart(nodeid=item.nodeid, location=("x", 1, "t"))
        r.pytest_runtest_setup(item)
        with pytest.raises(RuntimeError, match="explode"):
            with r.step_for(item, "bad step"):
                raise RuntimeError("explode")
    result = cap.by_endpoint("step-result")[0]
    assert result["passed"] is False
    assert "explode" in result["errorMessage"]


def test_step_counter_is_thread_local() -> None:
    r = _new_reporter()
    item_a = _make_item("x.py::t", binding=_binding(0))
    captured: Dict[str, List[int]] = {"a": [], "b": []}
    barrier = threading.Barrier(2)

    def worker(tag: str) -> None:
        barrier.wait(timeout=2.0)
        for _ in range(5):
            captured[tag].append(r._next_step_index())

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()
    # Each thread saw its own fresh sequence.
    assert captured["a"] == [0, 1, 2, 3, 4]
    assert captured["b"] == [0, 1, 2, 3, 4]
    del item_a  # keep linter quiet — fixture is just for illustration


# ═════════════════════════════════════════════════════════════════════════════
# Log buffer — thread-safe append + routing
# ═════════════════════════════════════════════════════════════════════════════


def test_log_buffer_no_lost_writes_under_concurrency() -> None:
    r = _new_reporter()
    n_threads = 20
    per = 50

    def write(tag: str) -> None:
        for i in range(per):
            r._on_output(f"{tag}:{i}\n")

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        futs = [pool.submit(write, f"t{i}") for i in range(n_threads)]
        for f in as_completed(futs):
            f.result()
    lines = [ln for ln in r._log_buffer.split("\n") if ln]
    assert len(lines) == n_threads * per


def test_current_test_nodeid_is_thread_local() -> None:
    """Log routing reads TLS to tag chunks with the test they belong to."""
    r = _new_reporter()
    seen: Dict[str, str | None] = {}
    barrier = threading.Barrier(2)

    def worker(tag: str) -> None:
        r._tls.current_test_nodeid = f"node-{tag}"
        barrier.wait(timeout=2.0)
        seen[tag] = r._tls.current_test_nodeid

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert seen == {"a": "node-a", "b": "node-b"}


# ═════════════════════════════════════════════════════════════════════════════
# Session hooks: start / collection-finish / finish
# ═════════════════════════════════════════════════════════════════════════════


def test_sessionstart_posts_start() -> None:
    r = _new_reporter()
    with _CapturingReporter(r) as cap:
        # Disable stream capture so the test doesn't spawn a background thread
        # we'd have to join.
        r._stream_capture_enabled = False
        r.pytest_sessionstart(session=types.SimpleNamespace())
    paths = [e for e, _ in cap.captured]
    assert "start" in paths


def test_collection_finish_posts_test_list_without_attribution() -> None:
    r = _new_reporter()
    items = [
        _make_item("tests/a.py::test_x", binding=_binding(0)),
        _make_item("tests/b.py::test_y"),
    ]
    session = types.SimpleNamespace(items=items)
    with _CapturingReporter(r) as cap:
        r.pytest_collection_finish(session)
    lists = cap.by_endpoint("test-list")
    assert len(lists) == 1
    assert [t["name"] for t in lists[0]["tests"]] == ["test_x", "test_y"]
    # Session-level payload: no attribution even when items had bindings.
    assert "slotIndex" not in lists[0]
    assert "deviceSerial" not in lists[0]


def test_sessionfinish_posts_summary_counters() -> None:
    r = _new_reporter()
    r._total = 10
    r._passed = 8
    r._failed = 2
    r._errors = 0
    with _CapturingReporter(r) as cap:
        r._stream_capture_enabled = False
        r.pytest_sessionfinish(session=types.SimpleNamespace(), exitstatus=0)
    finish = cap.by_endpoint("finish")[0]
    assert finish["total"] == 10
    assert finish["passed"] == 8
    assert finish["failed"] == 2


# ═════════════════════════════════════════════════════════════════════════════
# No-op variants
# ═════════════════════════════════════════════════════════════════════════════


def test_noop_reporter_step_returns_noop_step() -> None:
    r = NoOpReporter()
    s = r.step("anything")
    assert isinstance(s, NoOpStepReporter)
    with s as step:
        step.record("x", 1)
        step.record_dict({"y": {"value": 2}})


