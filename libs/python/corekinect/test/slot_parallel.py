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


# ``PyThreadState_SetAsyncExc`` only accepts a type (not an instance),
# so we can't hand the interpreter a pre-constructed exception with
# a message. Pass the message out-of-band through a per-thread dict;
# ``_TestTimeoutError.__init__`` reads it back when the interpreter
# instantiates the exception on the target worker thread. Clean up
# after the test finishes so a late-firing timer doesn't reuse a
# stale message for the next test on the same persistent worker.
_TIMEOUT_MESSAGES: Dict[int, str] = {}
_TIMEOUT_MESSAGES_LOCK = threading.Lock()


def _set_timeout_message(thread_ident: int, message: str) -> None:
    with _TIMEOUT_MESSAGES_LOCK:
        _TIMEOUT_MESSAGES[thread_ident] = message


def _pop_timeout_message(thread_ident: int) -> Optional[str]:
    with _TIMEOUT_MESSAGES_LOCK:
        return _TIMEOUT_MESSAGES.pop(thread_ident, None)


class _TestTimeoutError(BaseException):
    """Raised in a worker thread when its per-test budget elapses.

    Subclasses ``BaseException`` (not ``Exception``) so user-test
    ``except Exception:`` blocks cannot accidentally swallow the
    timeout signal — pytest's runner protocol still catches it and
    reports the test as failed.

    Pulls a descriptive message from ``_TIMEOUT_MESSAGES`` keyed by
    current thread ident so ``str(exc)`` yields something like
    ``"test_04_bms[slot-1] exceeded 18s budget"`` instead of an empty
    string. The UI reads ``str(exc)`` straight into the per-step error
    panel; without this, timeout failures render as a blank row with
    no clue why the test failed.
    """

    def __init__(self) -> None:
        ident = threading.get_ident()
        with _TIMEOUT_MESSAGES_LOCK:
            msg = _TIMEOUT_MESSAGES.get(ident, "test exceeded timeout budget")
        super().__init__(msg)
        self.message = msg

    def __str__(self) -> str:  # noqa: D401 — stdlib pattern
        return self.message


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


class _SessionPreservingSetupState:
    """Per-thread SetupState that refuses to pop the Session node.

    The original thread-local SetupState let each worker thread do its
    own teardown at end-of-queue (``teardown_exact(None)``), which
    popped *everything* off that thread's stack — including the shared
    session-scoped fixtures.

    In practice this meant: the fastest slot finishes test_11, its
    worker's teardown fires the ``fixture_ctx`` finalizer, which calls
    ``FixtureContext.disconnect_all()`` — closing MTIB channels and
    SlotTestContext UART demuxers that OTHER worker threads were
    actively using to run their remaining tests. The victims saw
    "Stream dead (stream closed by caller)" on whichever test was mid-
    flight when the disconnect happened. That's why failures landed
    randomly on test_07 / test_10 / test_11 depending on who finished
    first.

    Fix: keep ``SetupState`` semantics intact for function / class /
    module scope (the worker must still tear those down), but PIN
    the Session node in place. Session-scope fixtures live until the
    main thread runs them explicitly after the runtestloop finishes —
    at which point all workers are guaranteed done.
    """

    __slots__ = ("_tls", "_tracked_states", "_tracked_lock")

    def __init__(self) -> None:
        object.__setattr__(self, "_tls", threading.local())
        object.__setattr__(self, "_tracked_states", [])
        object.__setattr__(self, "_tracked_lock", threading.Lock())

    def _get(self):
        state = getattr(self._tls, "state", None)
        if state is None:
            from _pytest.runner import SetupState
            state = SetupState()
            _patch_setupstate_preserve_session(state)
            self._tls.state = state
            with self._tracked_lock:
                self._tracked_states.append(state)
        return state

    def all_states(self):
        """Return every SetupState instance created across threads.

        Used by the parallel runtestloop's ``finally`` clause so the
        main thread can tear down session-scope fixtures safely after
        all workers have joined.
        """
        with self._tracked_lock:
            return list(self._tracked_states)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._get(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._get(), name)


def _patch_setupstate_preserve_session(state) -> None:
    """Override ``teardown_exact`` on *state* so it never pops Session.

    The override falls back to the original method for non-terminal
    teardowns (nextitem != None) so function/class/module scopes still
    work exactly as pytest expects. When nextitem is None we only pop
    entries BELOW the root Session entry, preserving session-scope
    fixtures and their finalizers for a single coordinated teardown
    on the main thread after all workers finish.
    """
    from _pytest.nodes import Node  # noqa: F401
    original_teardown = state.teardown_exact

    def teardown_exact(nextitem):
        if nextitem is not None:
            return original_teardown(nextitem)
        # End of this thread's item queue — tear down everything
        # ABOVE the Session node, keep the Session (and its
        # finalizers) for later.
        exceptions: list[BaseException] = []
        while len(state.stack) > 1:
            node, (finalizers, _) = state.stack.popitem()
            these_exceptions = []
            while finalizers:
                fin = finalizers.pop()
                try:
                    fin()
                except BaseException as e:  # noqa: BLE001
                    these_exceptions.append(e)
            if these_exceptions:
                exceptions.extend(these_exceptions)
        if len(exceptions) == 1:
            raise exceptions[0]
        if exceptions:
            raise BaseExceptionGroup("errors during test teardown", exceptions[::-1])

    state.teardown_exact = teardown_exact


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
    timeout_msg = f"{item.nodeid} exceeded {timeout_s:g}s budget"
    _set_timeout_message(worker_ident, timeout_msg)

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
        # Always drop the out-of-band message so a late-firing timer
        # on the NEXT test never picks up this test's nodeid.
        _pop_timeout_message(worker_ident)


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

    nextitem_map = build_per_slot_nextitem(items)

    # Bucket items per slot, preserving collection order within a slot.
    # Items without a ``[slot-N]`` suffix are run inline on the main
    # thread first, in their collected order, where pytest's usual
    # SetupState semantics apply.
    inline_items: List[Any] = []
    items_by_slot: Dict[str, List[Any]] = {}
    for item in items:
        slot_id = _slot_key(item.nodeid)
        if not slot_id:
            inline_items.append(item)
        else:
            items_by_slot.setdefault(slot_id, []).append(item)

    # Nothing to parallelize — let pytest's default loop run.
    if not items_by_slot:
        return None

    slot_ids = sorted(items_by_slot.keys())

    # Single slot: no parallelism to gain. Fall back to pytest's default
    # loop so we keep standard SetupState semantics on the main thread —
    # the patches we install in :func:`pytest_configure` are no-ops here
    # (no concurrent FixtureDef requests, no env-var race) so the
    # default loop is safe and slightly faster.
    if len(slot_ids) == 1 and not inline_items:
        return None
    log.info(
        "slot_parallel: %d item(s) — %d inline + %d slot(s) × ~%d test(s) each",
        len(items),
        len(inline_items),
        len(slot_ids),
        max(len(v) for v in items_by_slot.values()),
    )

    # Run inline (non-parametrized) items first, on the main thread.
    for item in inline_items:
        _run_one_item(item, nextitem_map.get(item.nodeid))
        if session.shouldstop or session.shouldfail:
            return True

    # One single-worker pool per slot. Each slot runs its own ordered
    # sequence sequentially in its own thread; slots run concurrently
    # with NO inter-slot synchronization. The previous group-by-test
    # model added a barrier between every pair of tests, which spent
    # ~3-5 s per group × N tests on reporter flush + thread wakeup
    # (≈ 80 s of avoidable wall-clock on a 19-test panel run). Without
    # the barrier the panel wall-clock collapses to roughly
    # ``max(slot_durations)``.
    slot_pools: Dict[str, ThreadPoolExecutor] = {
        slot_id: ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"slot-parallel-{slot_id}",
        )
        for slot_id in slot_ids
    }

    def _run_slot_sequence(slot_id: str) -> None:
        for item in items_by_slot[slot_id]:
            if session.shouldstop or session.shouldfail:
                return
            _run_one_item(item, nextitem_map.get(item.nodeid))

    # Swap in a session-preserving, thread-local SetupState for the
    # duration of the parallel run. Each worker's terminal teardown
    # keeps Session-scope fixtures alive so the first slot to finish
    # can't disconnect shared MTIB channels out from under the others.
    original_setupstate = session._setupstate
    tls_setupstate = _SessionPreservingSetupState()
    session._setupstate = tls_setupstate
    try:
        futures = [
            slot_pools[slot_id].submit(_run_slot_sequence, slot_id)
            for slot_id in slot_ids
        ]
        done, not_done = wait(futures)
        # ``pytest_runtest_protocol`` catches test exceptions internally,
        # so a slot's future should only raise on plugin bugs or interrupts.
        for f in done:
            exc = f.exception()
            if exc is not None:
                raise exc
        if not_done:
            raise RuntimeError(
                f"slot_parallel: {len(not_done)} slot(s) did not complete"
            )
    finally:
        for pool in slot_pools.values():
            pool.shutdown(wait=True)
        # All workers are done — run the session-scope teardowns we
        # deferred. Finalizers live on the FixtureDef itself (shared
        # across all per-thread SetupStates), so firing any one
        # thread's Session entry is enough to run each finalizer once.
        # Guard against double-fire: the first state to run pops the
        # FixtureDef's ``_finalizers`` list; others become no-ops.
        for state in tls_setupstate.all_states():
            stack = getattr(state, "stack", None)
            if not stack:
                continue
            # Run any remaining finalizers (typically the Session
            # entry) via pytest's normal teardown path.
            try:
                # Nextitem=None + empty needed_collectors tears
                # everything that's left; since we preserved only
                # Session nodes, this is the coordinated session
                # teardown on the main thread.
                from _pytest.runner import SetupState as _OriginalSetupState
                _OriginalSetupState.teardown_exact(state, None)
            except Exception as e:
                log.warning("session teardown raised: %s", e)
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


class _ThreadLocalFinalizers:
    """Per-thread descriptor for ``FixtureDef._finalizers``.

    ``FixtureDef._finalizers`` is a plain list that accumulates
    teardown callbacks from every thread that executes the fixture.
    ``FixtureDef.finish()`` pops ALL entries — so the first thread to
    trigger teardown runs every thread's finalizers, closing UART
    streams and shell objects that other threads are still using.

    This descriptor returns a per-thread list so each worker only
    tears down its own fixture instances. The list supports the same
    interface pytest uses: ``while self._finalizers: fin = self._finalizers.pop()``
    and ``self._finalizers.clear()``.

    A global registry tracks all per-thread lists so the coordinated
    session teardown (running on the main thread after all workers
    finish) can drain finalizers that workers left behind.
    """

    __slots__ = ("_tls", "_all_lists_lock", "_all_lists")

    def __init__(self) -> None:
        self._tls = threading.local()
        self._all_lists_lock = threading.Lock()
        # (obj_id, thread_ident) → list. Kept so the main-thread
        # coordinated teardown can find and drain worker lists.
        self._all_lists: Dict[tuple, list] = {}

    def _bucket(self) -> Dict[int, list]:
        bucket = getattr(self._tls, "finalizers", None)
        if bucket is None:
            bucket = {}
            self._tls.finalizers = bucket
        return bucket

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        bucket = self._bucket()
        obj_id = id(obj)
        if obj_id not in bucket:
            new_list: list = []
            bucket[obj_id] = new_list
            with self._all_lists_lock:
                self._all_lists[(obj_id, threading.get_ident())] = new_list
        return bucket[obj_id]

    def __set__(self, obj, value) -> None:
        obj_id = id(obj)
        self._bucket()[obj_id] = value
        with self._all_lists_lock:
            self._all_lists[(obj_id, threading.get_ident())] = value

    def __delete__(self, obj) -> None:
        obj_id = id(obj)
        self._bucket().pop(obj_id, None)
        with self._all_lists_lock:
            keys_to_remove = [k for k in self._all_lists if k[0] == obj_id]
            for k in keys_to_remove:
                del self._all_lists[k]

    def drain_all_for(self, obj) -> list:
        """Collect and remove ALL finalizers for ``obj`` across all threads.

        Used by the coordinated session teardown on the main thread
        after all workers have joined. Returns the combined list so
        the caller can execute them.
        """
        obj_id = id(obj)
        result = []
        with self._all_lists_lock:
            keys = [k for k in self._all_lists if k[0] == obj_id]
            for k in keys:
                lst = self._all_lists[k]
                result.extend(lst)
                lst.clear()
        return result


def _patch_fixturedef_cached_result_per_thread() -> None:
    """Replace ``FixtureDef.cached_result`` and ``_finalizers`` with per-thread descriptors.

    Idempotent: the descriptors are only installed once per process.
    Existing ``self.cached_result = ...`` and ``self._finalizers``
    access in pytest's fixture machinery transparently route through
    the descriptors.

    Also patches ``FixtureDef.finish()`` so the coordinated session
    teardown (running on the main thread after workers join) can still
    drain finalizers that were registered on worker threads.
    """
    from _pytest.fixtures import FixtureDef

    if getattr(FixtureDef, "_slot_parallel_tls_cached_result", False):
        return

    tls_finalizers = _ThreadLocalFinalizers()
    FixtureDef.cached_result = _ThreadLocalCachedResult()
    FixtureDef._finalizers = tls_finalizers

    # Patch finish() to drain cross-thread finalizers when the current
    # thread's list is empty (happens during coordinated session teardown).
    _original_finish = FixtureDef.finish

    def _finish_with_drain(self, request):
        # If the current thread has no finalizers for this FixtureDef,
        # drain from all threads (coordinated teardown on main thread).
        my_list = tls_finalizers.__get__(self, type(self))
        if not my_list:
            drained = tls_finalizers.drain_all_for(self)
            if drained:
                my_list.extend(drained)
        return _original_finish(self, request)

    FixtureDef.finish = _finish_with_drain
    FixtureDef._slot_parallel_tls_cached_result = True


class _PytestTimeoutNeutralizer:
    """Hookimpls that pre-empt pytest-timeout's per-test timer.

    pytest-timeout's ``thread`` mode (which it auto-selects in any
    worker thread, see ``pytest_timeout.py:307``) hard-kills the
    runner via ``os._exit(1)`` on every per-test timeout
    (``:542``). With slot_parallel that means the first
    ``@pytest.mark.timeout(N)`` to expire takes the whole panel
    down.

    Both ``pytest_timeout_set_timer`` and
    ``pytest_timeout_cancel_timer`` hookspecs are declared
    ``firstresult=True``: returning ``True`` from a ``tryfirst``
    hookimpl preempts the default ``trylast`` ones. We claim
    ownership of the timer (so pytest-timeout doesn't arm
    anything) and install a no-op ``cancel_timeout`` for the
    matching cancel call.

    Per-test budgets remain enforced by the soft Timer in
    :func:`_run_one_item`, which fails the test cleanly instead of
    killing the process.

    Wrapped in a class so we can register/skip the hookimpls only
    when pytest-timeout is actually loaded — pluggy raises
    ``PluginValidationError`` for hookimpls whose hookspecs aren't
    declared, which would break test environments that don't depend
    on pytest-timeout.
    """

    @pytest.hookimpl(tryfirst=True)
    def pytest_timeout_set_timer(self, item, settings):
        item.cancel_timeout = lambda: None
        return True

    @pytest.hookimpl(tryfirst=True)
    def pytest_timeout_cancel_timer(self, item):
        return True


def _maybe_register_pytest_timeout_neutralizer(config: pytest.Config) -> None:
    pm = config.pluginmanager
    # pytest-timeout registers itself under the entry-point name
    # ``timeout`` (not the import name), so check both.
    if not (pm.hasplugin("timeout") or pm.hasplugin("pytest_timeout")):
        return
    if pm.has_plugin("slot_parallel_timeout_neutralizer"):
        return
    pm.register(
        _PytestTimeoutNeutralizer(), name="slot_parallel_timeout_neutralizer",
    )


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
    _maybe_register_pytest_timeout_neutralizer(config)
