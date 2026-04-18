"""Thread-safety tests for ConcordReporter.

The slot_parallel plugin runs multiple slot parametrizations on threads
inside a single pytest process. The reporter is shared across those
threads, so:
  - session-wide counters (_total/_passed/_failed/_errors) must be
    protected against lost updates
  - per-test state (current test name, current device, current step
    index, step counter, test-start timestamps, captured output) must
    be isolated per thread

These tests hammer the reporter from many threads and assert the
expected invariants. They do NOT hit the API — `_post` is patched out
so the tests are fast and offline.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest

# The reporter is inert unless CONCORD_RUN_ID is set. Set it for all
# tests in this module so ConcordReporter.enabled is True.
os.environ.setdefault("CONCORD_RUN_ID", "test-run-id")
os.environ.setdefault("CONCORD_API_URL", "http://localhost:9001")

from corekinect.test.reporter import ConcordReporter  # noqa: E402


@pytest.fixture
def reporter() -> ConcordReporter:
    """A ConcordReporter with the HTTP side patched out."""
    r = ConcordReporter(config=None)
    # Patch _post to a no-op so we don't touch the network
    with patch.object(r, "_post", return_value=None):
        yield r


# ─────────────────────────────────────────────────────────────────────────────
# Session counters — must be thread-safe
# ─────────────────────────────────────────────────────────────────────────────


def test_counters_exact_totals_under_load(reporter: ConcordReporter) -> None:
    """1000 concurrent increments from 50 threads produce exact totals."""
    N_THREADS = 50
    INCREMENTS_PER_THREAD = 20  # 50 * 20 = 1000 total

    def bump_passed() -> None:
        for _ in range(INCREMENTS_PER_THREAD):
            with reporter._state_lock:
                reporter._total += 1
                reporter._passed += 1

    with ThreadPoolExecutor(max_workers=N_THREADS) as ex:
        futures = [ex.submit(bump_passed) for _ in range(N_THREADS)]
        for f in as_completed(futures):
            f.result()

    assert reporter._total == N_THREADS * INCREMENTS_PER_THREAD
    assert reporter._passed == N_THREADS * INCREMENTS_PER_THREAD


def test_state_lock_is_reentrant(reporter: ConcordReporter) -> None:
    """_state_lock must be an RLock — a thread that holds it may re-acquire."""
    with reporter._state_lock:
        with reporter._state_lock:
            reporter._passed += 1
    assert reporter._passed == 1


# ─────────────────────────────────────────────────────────────────────────────
# Per-test state — must be thread-local
# ─────────────────────────────────────────────────────────────────────────────


def test_current_test_name_is_thread_local(reporter: ConcordReporter) -> None:
    """Setting _current_test_name in thread A must not affect thread B."""
    captured: dict[str, str | None] = {}

    barrier = threading.Barrier(2)

    def worker(name: str) -> None:
        reporter._current_test_name = f"test_{name}"
        barrier.wait(timeout=2.0)
        # Both threads arrive here simultaneously
        captured[name] = reporter._current_test_name

    t1 = threading.Thread(target=worker, args=("alpha",))
    t2 = threading.Thread(target=worker, args=("bravo",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert captured["alpha"] == "test_alpha"
    assert captured["bravo"] == "test_bravo"


def test_current_device_is_thread_local(reporter: ConcordReporter) -> None:
    """Setting _current_device in thread A must not affect thread B."""
    captured: dict[str, str | None] = {}
    barrier = threading.Barrier(2)

    def worker(sn: str) -> None:
        reporter._current_device = sn
        barrier.wait(timeout=2.0)
        captured[sn] = reporter._current_device

    t1 = threading.Thread(target=worker, args=("AAAA",))
    t2 = threading.Thread(target=worker, args=("BBBB",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert captured["AAAA"] == "AAAA"
    assert captured["BBBB"] == "BBBB"


def test_step_counter_is_thread_local(reporter: ConcordReporter) -> None:
    """Two threads stepping simultaneously have independent step indices.

    If the counter were shared, we'd see mixed indices across threads.
    With thread-local storage, each thread sees 0, 1, 2, ... starting fresh.
    """
    captured: dict[str, list[int]] = {"a": [], "b": []}
    barrier = threading.Barrier(2)

    def worker(tag: str) -> None:
        barrier.wait(timeout=2.0)
        for _ in range(5):
            captured[tag].append(reporter._next_step_index())

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert captured["a"] == [0, 1, 2, 3, 4]
    assert captured["b"] == [0, 1, 2, 3, 4]


def test_current_step_index_is_thread_local(reporter: ConcordReporter) -> None:
    """_current_step_index written by thread A is invisible to thread B."""
    captured: dict[str, int | None] = {}
    barrier = threading.Barrier(2)

    def worker(tag: str, value: int) -> None:
        reporter._current_step_index = value
        barrier.wait(timeout=2.0)
        captured[tag] = reporter._current_step_index

    t1 = threading.Thread(target=worker, args=("a", 7))
    t2 = threading.Thread(target=worker, args=("b", 42))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert captured["a"] == 7
    assert captured["b"] == 42


# ─────────────────────────────────────────────────────────────────────────────
# Log buffer — existing lock must still hold under parallel writes
# ─────────────────────────────────────────────────────────────────────────────


def test_log_buffer_no_lost_writes(reporter: ConcordReporter) -> None:
    """Concurrent _on_output appends must all land in the buffer."""
    N_THREADS = 20
    WRITES_PER_THREAD = 50

    def write_some(tag: str) -> None:
        for i in range(WRITES_PER_THREAD):
            reporter._on_output(f"{tag}:{i}\n")

    with ThreadPoolExecutor(max_workers=N_THREADS) as ex:
        futs = [ex.submit(write_some, f"t{i}") for i in range(N_THREADS)]
        for f in as_completed(futs):
            f.result()

    # Buffer should contain exactly N_THREADS * WRITES_PER_THREAD lines.
    lines = [l for l in reporter._log_buffer.split("\n") if l]
    assert len(lines) == N_THREADS * WRITES_PER_THREAD
