"""Synchronized per-slot parallel test execution.

The multi-slot manufacturing runner parametrizes every test across N
slots (``test_x[slot-0]``, ``test_x[slot-1]``, ...). By default pytest
runs those parametrizations round-robin on a single thread, so a
4-slot panel takes 4× the single-slot time.

This plugin overrides ``pytest_runtestloop`` to:

1. Group collected items by their top-level test (nodeid with
   ``[slot-N]`` suffix stripped) while preserving collection order.
2. For each group, submit every item to a ``ThreadPoolExecutor`` sized
   to the group's cardinality and wait for all of them to finish — a
   barrier between groups.
3. Advance to the next group only once every slot has completed the
   current top-level test (passed, failed, or skipped).

Running in a single Python process means per-slot fixture state lives
in that process's ``FixtureContext.slots`` dict and each slot's
``SlotContext.shared_data`` dict — independent per slot, preserved
across the test sequence. The ``ConcordReporter``'s thread-local state
keeps step indices and current-device attribution per-worker.

Set ``PYTEST_PARALLEL=0`` to disable: the plugin returns ``None`` from
``pytest_runtestloop`` and pytest falls back to its default serial
implementation.
"""

from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Iterable, List

import pytest

from corekinect.utils import Logger

log = Logger(log_name="slot_parallel")

_SLOT_SUFFIX_RE = re.compile(r"\[slot-\d+\]$")


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


def _parallel_disabled() -> bool:
    """Return True if PYTEST_PARALLEL env var disables the plugin."""
    return os.environ.get("PYTEST_PARALLEL", "1") in ("0", "false", "no", "False")


def _run_one_item(item) -> None:
    """Execute a single pytest item via the standard runtest protocol.

    ``pytest_runtest_protocol`` handles setup → call → teardown, fires
    all the report hooks (logstart / makereport / logreport), and
    catches test exceptions internally, so one slot's failure never
    raises out of this thread into the pool.
    """
    item.ihook.pytest_runtest_protocol(item=item, nextitem=None)


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

    # If every group is a singleton, there's nothing to parallelize —
    # defer to pytest's default loop so we keep standard semantics
    # (teardown optimization for same-fixture neighbors, etc.).
    if all(len(g) == 1 for g in groups):
        return None

    log.info(
        "slot_parallel: %d item(s) organized into %d group(s); "
        "max concurrency = %d",
        len(items),
        len(groups),
        max(len(g) for g in groups),
    )

    # Swap in a thread-local SetupState for the duration of the parallel
    # run so concurrent fixture setup/teardown doesn't corrupt each
    # other's stack. Restore the original on exit.
    original_setupstate = session._setupstate
    session._setupstate = _ThreadLocalSetupState()
    try:
        for group_idx, group in enumerate(groups):
            top_level = _strip_slot_suffix(group[0].nodeid)
            if len(group) == 1:
                # Singleton — run inline on the main thread where pytest's
                # usual SetupState semantics apply.
                log.info(
                    "[group %d/%d] %s — running inline",
                    group_idx + 1, len(groups), top_level,
                )
                _run_one_item(group[0])
                continue

            log.info(
                "[group %d/%d] %s — running %d slot(s) in parallel",
                group_idx + 1, len(groups), top_level, len(group),
            )
            with ThreadPoolExecutor(
                max_workers=len(group),
                thread_name_prefix=f"slot-parallel-g{group_idx}",
            ) as pool:
                futures = [pool.submit(_run_one_item, item) for item in group]
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
        session._setupstate = original_setupstate

    return True


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Register the plugin name so pytest --trace-config shows it."""
    config.addinivalue_line("markers", "slot_parallel: loaded by slot_parallel plugin")
