"""Synchronized per-slot parallel test execution.

The multi-slot manufacturing runner parametrizes every test across N
slots (``test_x[slot-0]``, ``test_x[slot-1]``, ...). By default pytest
runs those parametrizations round-robin on a single thread, so a
4-slot panel takes 4× the single-slot time.

This plugin overrides ``pytest_runtestloop`` to:

1. Group collected items by their top-level test (nodeid with
   ``[slot-N]`` suffix stripped) while preserving collection order.
2. For each group, submit every item to the slot's persistent worker
   thread and wait for the whole group to finish — a barrier between
   groups.
3. Advance to the next group only once every slot has completed the
   current top-level test (passed, failed, or skipped).

Per-slot worker affinity is essential. Pytest stores the active
``SetupState`` and the cached values for parametrized fixtures in
process-global state that's only safe under serial execution. To make
that work under per-slot parallelism this plugin:

* Routes each slot's items through its own single-worker
  ``ThreadPoolExecutor``, so the per-thread ``_ThreadLocalSetupState``
  for that slot survives across groups (otherwise module/class-scoped
  fixtures would be torn down between every test).
* Replaces ``FixtureDef.cached_result`` with a thread-local descriptor
  so concurrent requests for different slot params don't invalidate
  each other.
* Wraps pytest's ``_update_current_test_var`` with a lock so its
  unguarded ``os.environ.pop`` cannot race between worker threads.

The ``ConcordReporter``'s thread-local state keeps step indices and
current-device attribution per-worker. Set ``PYTEST_PARALLEL=0`` to
disable: the plugin returns ``None`` from ``pytest_runtestloop`` and
pytest falls back to its default serial implementation.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Dict, Iterable, List, Optional

import pytest

from corekinect.utils import Logger

log = Logger(log_name="slot_parallel")

_SLOT_SUFFIX_RE = re.compile(r"\[slot-\d+\]$")
_SLOT_PARAM_RE = re.compile(r"\[(slot-\d+)\]$")


class _TestTimeoutError(BaseException):
    """Raised in a worker thread when its per-test budget elapses.

    Subclasses ``BaseException`` (not ``Exception``) so user-test
    ``except Exception:`` blocks cannot accidentally swallow the
    timeout signal — pytest's runner protocol still catches it and
    reports the test as failed.
    """


def _get_test_timeout_s(item) -> Optional[float]:
    """Extract the per-test timeout from ``@pytest.mark.timeout(N)``.

    Returns ``None`` if the test has no explicit timeout mark; the
    soft timer is then skipped and the test runs unbounded.
    """
    mark = item.get_closest_marker("timeout")
    if mark is None:
        return None
    if mark.args:
        return float(mark.args[0])
    if mark.kwargs and "timeout" in mark.kwargs:
        return float(mark.kwargs["timeout"])
    return None


def _async_raise_in_thread(thread_ident: int, exc_type: type) -> None:
    """Inject ``exc_type`` into the target Python thread.

    Uses ``PyThreadState_SetAsyncExc``; the exception fires at the
    next interpreter-level checkpoint (typically the next bytecode
    that yields the GIL — including blocking primitives like
    ``Event.wait`` and ``Lock.acquire``). Won't interrupt a thread
    blocked in C code that never returns to Python.
    """
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_ident),
        ctypes.py_object(exc_type),
    )
    if res > 1:
        # If more than one thread was affected, undo. Should never
        # happen with a real ident, but the API requires the cleanup.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread_ident), ctypes.c_long(0)
        )


def _clear_pending_async_exc(thread_ident: int) -> None:
    """Clear any pending async exception we may have scheduled.

    Called after a test completes to ensure a late-firing timer
    doesn't poison the next test running on the same persistent
    worker thread.
    """
    ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_ident), ctypes.c_long(0)
    )


class _ThreadLocalSetupState:
    """Proxy that gives each thread its own ``SetupState`` instance.

    Pytest's ``Session._setupstate`` tracks fixture setup/teardown via a
    single stack. When multiple items execute on threads in parallel,
    they race on that stack and trigger ``AssertionError: previous item
    was not torn down properly``. By proxying attribute access to a
    per-thread ``SetupState`` instance we restore the invariant pytest
    expects — each thread sets up its item, runs it, and tears down in
    isolation.
    """

    __slots__ = ("_tls",)

    def __init__(self) -> None:
        object.__setattr__(self, "_tls", threading.local())

    def _get(self):
        state = getattr(self._tls, "state", None)
        if state is None:
            from _pytest.runner import SetupState
            state = SetupState()
            self._tls.state = state
        return state

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._get(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._get(), name)


def _strip_slot_suffix(nodeid: str) -> str:
    """Return the top-level test key for ``nodeid``.

    Strips only the final ``[slot-N]`` parametrization; other params
    (like ``[debug]`` / ``[release]`` for firmware variants) are left
    intact so we don't collapse distinct tests together.
    """
    return _SLOT_SUFFIX_RE.sub("", nodeid)


def items_to_groups(items: Iterable) -> List[List]:
    """Group items by top-level test, preserving collection order.

    Returns a list of groups; each group is a list of one or more pytest
    items that share the same top-level key. Items without a
    ``[slot-N]`` suffix become singleton groups. Group order matches
    the collection order of each group's first item.
    """
    groups_by_key: dict = {}
    group_keys_in_order: List[str] = []
    for item in items:
        key = _strip_slot_suffix(item.nodeid)
        if key not in groups_by_key:
            groups_by_key[key] = []
            group_keys_in_order.append(key)
        groups_by_key[key].append(item)
    return [groups_by_key[k] for k in group_keys_in_order]


def _slot_key(nodeid: str) -> str:
    """Extract the slot identifier (``slot-0``) from a parametrized nodeid.

    Returns ``""`` for items without a ``[slot-N]`` suffix; those are
    treated as a single virtual "slot" so any module-scoped fixtures on
    them still get correct teardown ordering.
    """
    m = _SLOT_PARAM_RE.search(nodeid)
    return m.group(1) if m else ""


def build_per_slot_nextitem(items: Iterable) -> Dict[str, Optional[Any]]:
    """Map each item's nodeid to the next item in the same slot.

    Pytest's ``pytest_runtest_protocol(item, nextitem=...)`` uses
    ``nextitem`` to decide whether higher-scoped fixtures (module,
    class, package) should be torn down after the current item: if
    ``nextitem`` is None or belongs to a different scope, teardown
    fires; if it's another item that still depends on the same
    fixture, teardown is deferred.

    The default ``nextitem=None`` we used to pass forced full teardown
    after every test, which silently disabled module-scoped fixture
    sharing across slot-parametrized tests. By precomputing per-slot
    sequences and threading the next-in-slot item through, pytest's
    scope cache works as documented even when groups run on threads.
    """
    per_slot: Dict[str, List[Any]] = {}
    for item in items:
        per_slot.setdefault(_slot_key(item.nodeid), []).append(item)
    nextitem_map: Dict[str, Optional[Any]] = {}
    for slot_items in per_slot.values():
        for i, item in enumerate(slot_items):
            nextitem_map[item.nodeid] = (
                slot_items[i + 1] if i + 1 < len(slot_items) else None
            )
    return nextitem_map


def _parallel_disabled() -> bool:
    """Return True if PYTEST_PARALLEL env var disables the plugin."""
    return os.environ.get("PYTEST_PARALLEL", "1") in ("0", "false", "no", "False")


def _run_one_item(item, nextitem) -> None:
    """Execute a single pytest item via the standard runtest protocol.

    ``pytest_runtest_protocol`` handles setup → call → teardown, fires
    all the report hooks (logstart / makereport / logreport), and
    catches test exceptions internally, so one slot's failure never
    raises out of this thread into the pool.

    ``nextitem`` is the next item in the same slot (precomputed by
    :func:`build_per_slot_nextitem`) so module/class-scoped fixtures
    are kept alive across tests that share them.

    If the item carries ``@pytest.mark.timeout(N)`` a soft timer is
    armed for the duration of the protocol; on expiry it injects
    :class:`_TestTimeoutError` into this thread, the test fails, the
    runner reports it normally, and the session continues. This
    replaces pytest-timeout (whose only worker-thread mode hard-kills
    the process via ``os._exit(1)`` on first timeout — see the
    plugin's docstring).
    """
    timeout_s = _get_test_timeout_s(item)
    if timeout_s is None:
        item.ihook.pytest_runtest_protocol(item=item, nextitem=nextitem)
        return

    worker_ident = threading.get_ident()
    timed_out = threading.Event()

    def _on_timeout() -> None:
        timed_out.set()
        _async_raise_in_thread(worker_ident, _TestTimeoutError)

    timer = threading.Timer(timeout_s, _on_timeout)
    timer.daemon = True
    timer.start()
    try:
        item.ihook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    finally:
        timer.cancel()
        # If the timer fired but the test happened to finish at the
        # same instant, an async exception may still be queued for
        # this thread. Clear it so the next test on this persistent
        # worker doesn't inherit it.
        if timed_out.is_set():
            _clear_pending_async_exc(worker_ident)


# ═══════════════════════════════════════════════════════════════════════════
# pytest hooks
# ═══════════════════════════════════════════════════════════════════════════


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session: pytest.Session):
    """Fan out each top-level test's slot parametrizations across threads.

    Returning ``True`` tells pytest we've consumed the test loop and no
    further ``pytest_runtestloop`` implementation should run. Returning
    ``None`` passes control to pytest's default serial loop.
    """
    if session.testsfailed and not session.config.option.continue_on_collection_errors:
        # Collection errors — let pytest's default loop emit the summary
        return None

    if _parallel_disabled():
        log.info("PYTEST_PARALLEL=0 set — falling back to serial execution")
        return None

    items = list(session.items)
    if not items:
        return None

    groups = items_to_groups(items)
    nextitem_map = build_per_slot_nextitem(items)

    # If every group is a singleton, there's nothing to parallelize —
    # defer to pytest's default loop so we keep standard semantics
    # (teardown optimization for same-fixture neighbors, etc.).
    if all(len(g) == 1 for g in groups):
        return None

    # Each slot needs a stable worker thread for the whole session so
    # that pytest's SetupState (held in thread-local storage by
    # _ThreadLocalSetupState) survives across groups. Without per-slot
    # worker affinity a fresh thread per group would observe an empty
    # SetupState and re-instantiate every module/class-scoped fixture
    # before each test — silently turning module scope into function
    # scope and forcing redundant power cycles in the manufacturing
    # POST stage.
    slot_ids = sorted({_slot_key(it.nodeid) for it in items if _slot_key(it.nodeid)})
    log.info(
        "slot_parallel: %d item(s) organized into %d group(s); "
        "%d persistent worker(s) (one per slot)",
        len(items),
        len(groups),
        len(slot_ids),
    )

    # One single-worker pool per slot. Single-worker guarantees FIFO
    # execution on a stable thread; the pools live for the whole
    # session so module-scoped fixture setup/teardown happens at the
    # natural pytest boundary (last item in scope) rather than every
    # group transition.
    slot_pools: Dict[str, ThreadPoolExecutor] = {
        slot_id: ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"slot-parallel-{slot_id}",
        )
        for slot_id in slot_ids
    }

    # Swap in a thread-local SetupState for the duration of the parallel
    # run so concurrent fixture setup/teardown doesn't corrupt each
    # other's stack. Restore the original on exit.
    original_setupstate = session._setupstate
    session._setupstate = _ThreadLocalSetupState()
    try:
        for group_idx, group in enumerate(groups):
            top_level = _strip_slot_suffix(group[0].nodeid)
            if len(group) == 1 and not _slot_key(group[0].nodeid):
                # Genuine singleton (no [slot-N] parametrization) — run
                # inline on the main thread where pytest's usual
                # SetupState semantics apply.
                log.info(
                    "[group %d/%d] %s — running inline",
                    group_idx + 1, len(groups), top_level,
                )
                _run_one_item(group[0], nextitem_map.get(group[0].nodeid))
                continue

            log.info(
                "[group %d/%d] %s — running %d slot(s) in parallel",
                group_idx + 1, len(groups), top_level, len(group),
            )
            futures = [
                slot_pools[_slot_key(item.nodeid)].submit(
                    _run_one_item, item, nextitem_map.get(item.nodeid),
                )
                for item in group
            ]
            done, not_done = wait(futures)
            # All futures should complete because pytest_runtest_protocol
            # catches test exceptions internally. If any escaped (plugin
            # bug, keyboard interrupt, etc.), re-raise so the session aborts.
            for f in done:
                exc = f.exception()
                if exc is not None:
                    raise exc
            if not_done:
                raise RuntimeError(
                    f"slot_parallel: {len(not_done)} item(s) did not complete"
                )

            # Honor session-level stop conditions (--maxfail, etc.) between groups.
            if session.shouldstop or session.shouldfail:
                log.info("slot_parallel: session requested stop — aborting remaining groups")
                break
    finally:
        for pool in slot_pools.values():
            pool.shutdown(wait=True)
        session._setupstate = original_setupstate

    return True


_PYTEST_CURRENT_TEST_LOCK = threading.Lock()


class _ThreadLocalCachedResult:
    """Per-thread descriptor for ``FixtureDef.cached_result``.

    Pytest stores a fixture's cached value in a single instance
    attribute ``FixtureDef.cached_result``. Parametrized fixtures
    treat that slot as the *currently cached* parameter — when a new
    parameter is requested, ``execute`` tears down the old value to
    make room (``self.finish(request)`` at fixtures.py:1096).

    Under slot_parallel, multiple worker threads request different
    parameters of the same ``FixtureDef`` concurrently (one slot per
    thread). Each request invalidates the others, so a module-scoped
    fixture that should run once per ``(module, slot)`` instead runs
    once per ``(module, slot, test)`` — silently turning module scope
    into function scope.

    This descriptor stores ``cached_result`` per-thread so each worker
    sees only its own slot's cache. Pytest's setup/teardown logic
    then behaves as documented.
    """

    __slots__ = ("_tls",)

    def __init__(self) -> None:
        self._tls = threading.local()

    def _bucket(self) -> Dict[int, Any]:
        bucket = getattr(self._tls, "cache", None)
        if bucket is None:
            bucket = {}
            self._tls.cache = bucket
        return bucket

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return self._bucket().get(id(obj))

    def __set__(self, obj, value) -> None:
        self._bucket()[id(obj)] = value

    def __delete__(self, obj) -> None:
        self._bucket().pop(id(obj), None)


def _patch_fixturedef_cached_result_per_thread() -> None:
    """Replace ``FixtureDef.cached_result`` with a per-thread descriptor.

    Idempotent: the descriptor is only installed once per process.
    Existing ``self.cached_result = ...`` assignments in pytest's
    fixture machinery transparently route through the descriptor.
    """
    from _pytest.fixtures import FixtureDef

    if getattr(FixtureDef, "_slot_parallel_tls_cached_result", False):
        return
    FixtureDef.cached_result = _ThreadLocalCachedResult()
    FixtureDef._slot_parallel_tls_cached_result = True


def _patch_update_current_test_var_for_threads() -> None:
    """Make ``_update_current_test_var`` race-safe under concurrent workers.

    Pytest 9 stores the active test as the process-global env var
    ``PYTEST_CURRENT_TEST`` and clears it at teardown with
    ``os.environ.pop(var_name)`` — *without* a default. With
    slot_parallel, multiple worker threads concurrently set and pop
    that single env var; the loser of the pop race raises
    ``KeyError: 'PYTEST_CURRENT_TEST'`` and pytest reports the test
    as ERROR even though it passed.

    Patch the helper to:
      1. Hold a lock across set + pop so two threads can't interleave.
      2. Pop with a default so a duplicate clear is a no-op.

    This is safe to apply once per process: the patched function has
    the same external behaviour, just concurrency-tolerant.
    """
    from _pytest import runner as _pytest_runner

    original = _pytest_runner._update_current_test_var
    if getattr(original, "_slot_parallel_patched", False):
        return

    def _safe(item, when):
        var_name = "PYTEST_CURRENT_TEST"
        with _PYTEST_CURRENT_TEST_LOCK:
            if when:
                value = f"{item.nodeid} ({when})"
                value = value.replace("\x00", "(null)")
                os.environ[var_name] = value
            else:
                os.environ.pop(var_name, None)

    _safe._slot_parallel_patched = True  # type: ignore[attr-defined]
    _pytest_runner._update_current_test_var = _safe


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Register the plugin name so pytest --trace-config shows it."""
    config.addinivalue_line("markers", "slot_parallel: loaded by slot_parallel plugin")
    _patch_update_current_test_var_for_threads()
    _patch_fixturedef_cached_result_per_thread()
