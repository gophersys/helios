"""Pytest plugin that streams test results to the Concord HTTP API.

Design
------

The reporter is a near-stateless payload builder:

* Construction takes explicit kwargs (``run_id``, ``api_url``,
  ``api_key``, ``enabled``). The :meth:`ConcordReporter.from_env`
  classmethod is the one production entry point that reads
  ``CONCORD_*`` env vars and returns ``None`` when the reporter should
  stay inert.
* Every outgoing payload flows through a single
  :meth:`ConcordReporter._emit` helper. It reads the
  :class:`~corekinect.test.slot_binding.SlotBinding` stashed on the
  pytest item by the autoconf plugin (see S1:
  :mod:`corekinect.test.slot_binding`) and injects
  ``slotIndex`` / ``deviceSerial`` exactly when the binding says so.
* Thread-local state is limited to two concerns that genuinely need
  per-thread scoping:

    * step counter and current step index — the ``slot_parallel``
      plugin dispatches slot parametrizations to worker threads, so
      each thread owns an independent step sequence.
    * current test nodeid — the background log-flush thread needs to
      know which test is actively producing stdout/stderr on each
      worker so it can tag chunks correctly.

  Device serial, slot index and test name are **not** on the TLS
  anymore; they are read from the item's stash at emit time.

Wire contract (see S4 backend update)
-------------------------------------

Attributed payloads (must carry ``slotIndex``, plus ``deviceSerial``
when known):

* ``report/execution-start``
* ``report/execution-result``
* ``report/step-start``
* ``report/step-result``
* ``report/target-start``

Session- or file-level payloads that do **not** need attribution:

* ``report/start``
* ``report/finish``
* ``report/test-list``
* ``report/log-chunk``
"""

from __future__ import annotations

import base64
import io
import os
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

import pytest

from corekinect.test.env import get_run_id
from corekinect.test.slot_binding import SLOT_BINDING_KEY, SlotBinding, get_binding
from corekinect.utils import Logger

log = Logger(log_name="concord_reporter")

# TLS verification — enabled by default, can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")

# Live log streaming config
_LOG_STREAM_ENABLED = os.environ.get("CONCORD_LOG_STREAM", "true").lower() in ("1", "true", "yes")
_LOG_FLUSH_INTERVAL = float(os.environ.get("CONCORD_LOG_FLUSH_INTERVAL", "1.0"))  # seconds

# Attempt to import requests; if not installed, reporter is disabled.
try:
    import requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ──────────────────────────────────────────────────────────────────────
# nodeid parsing — single source of truth
# ──────────────────────────────────────────────────────────────────────


def _parse_nodeid(nodeid: str) -> Tuple[Optional[str], str]:
    """Return ``(module, test_name)`` for a pytest nodeid.

    ``module`` is the stem of the test file path (``tests/a/test_x.py``
    → ``test_x``); ``None`` when the nodeid has no ``::`` separator.
    ``test_name`` is the last ``::`` component including any
    parametrize suffix.
    """
    parts = nodeid.split("::")
    test_name = parts[-1] if parts else nodeid
    module: Optional[str] = None
    if len(parts) >= 2:
        file_part = parts[0]
        if "/" in file_part:
            file_part = file_part.rsplit("/", 1)[-1]
        if file_part.endswith(".py"):
            module = file_part[:-3]
    return module, test_name


# ──────────────────────────────────────────────────────────────────────
# Stream capture — tees stdout/stderr to a callback
# ──────────────────────────────────────────────────────────────────────


class StreamCapture(io.TextIOBase):
    """Tee stream writes to a callback while passing through to the original."""

    def __init__(self, original_stream, callback):
        self.original = original_stream
        self.callback = callback
        self._lock = threading.Lock()

    def write(self, data):
        if data:
            with self._lock:
                if self.original:
                    self.original.write(data)
                    self.original.flush()
                self.callback(data)
        return len(data) if data else 0

    def flush(self):
        if self.original:
            self.original.flush()

    def fileno(self):
        if self.original:
            return self.original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        return self.original.isatty() if self.original else False


# ──────────────────────────────────────────────────────────────────────
# Step reporter — step-start / step-result with item-derived attribution
# ──────────────────────────────────────────────────────────────────────


class StepReporter:
    """Context manager for sub-step tracking.

    Attribution (slotIndex, deviceSerial) is captured from the parent
    item's stash when the step is opened, so the payload is
    self-contained and doesn't depend on any thread-local at emit time.

    If the ``with`` block raises, the step is marked failed and the
    exception propagates.
    """

    def __init__(self, reporter: "ConcordReporter", item: Any, step_name: str):
        self.reporter = reporter
        self.item = item
        self.step_name = step_name
        self.step_index = reporter._next_step_index()
        self.measurements: Dict[str, Any] = {}
        _, self.test_name = _parse_nodeid(getattr(item, "nodeid", ""))

    def __enter__(self):
        self.reporter._emit(
            self.item,
            "step-start",
            testName=self.test_name,
            stepName=self.step_name,
            stepIndex=self.step_index,
        )
        self.reporter._tls.current_step_index = self.step_index
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        passed = exc_type is None
        self.reporter._emit(
            self.item,
            "step-result",
            testName=self.test_name,
            stepIndex=self.step_index,
            passed=passed,
            errorMessage=str(exc_val) if exc_val else None,
            measurements=self.measurements or None,
        )
        self.reporter._tls.current_step_index = None
        return False  # Don't suppress exceptions

    def record(self, key: str, value, unit: str = None):
        """Record a measurement for this step."""
        entry = {"value": value}
        if unit:
            entry["unit"] = unit
        self.measurements[key] = entry

    def record_dict(self, data: dict):
        """Record multiple measurements at once."""
        self.measurements.update(data)


class NoOpStepReporter:
    """No-op step context manager for offline mode."""

    def __init__(self):
        self.measurements: Dict[str, Any] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def record(self, key: str, value, unit: str = None):
        pass

    def record_dict(self, data: dict):
        pass


class NoOpReporter:
    """No-op reporter for offline/local runs. Same interface as ConcordReporter."""

    def __init__(self):
        self.execution_measurements: Dict[str, Any] = {}

    def step(self, name: str) -> NoOpStepReporter:
        return NoOpStepReporter()

    def step_for(self, item: Any, name: str) -> NoOpStepReporter:
        return NoOpStepReporter()


# ──────────────────────────────────────────────────────────────────────
# ConcordReporter
# ──────────────────────────────────────────────────────────────────────


class ConcordReporter:
    """Pytest plugin that streams test results to the Concord API.

    Construct with explicit kwargs. Use :meth:`from_env` to build from
    the production ``CONCORD_*`` env vars and get ``None`` when the
    reporter should stay inert.
    """

    def __init__(
        self,
        *,
        run_id: str,
        api_url: str,
        api_key: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        """Initialize with explicit connection parameters.

        Parameters
        ----------
        run_id
            Concord run (session) ID. Interpolated into every
            ``/v2/runs/<id>/report/*`` URL.
        api_url
            Base API URL. Trailing slash stripped.
        api_key
            Optional bearer key sent as ``Authorization: ApiKey ...``.
        enabled
            When ``False``, every payload is silently dropped. Useful
            for tests that want to construct the reporter but skip I/O.
        """
        self.run_id = run_id
        self.api_url = (api_url or "").rstrip("/")
        self.api_key = api_key
        self.enabled = bool(enabled)

        # ── Thread-safety primitives ──────────────────────────────────
        # ``_state_lock`` (RLock) guards session-wide counters and
        # per-slot tracking. ``_tls`` carries the short list of values
        # that genuinely need per-thread scoping (step counter, current
        # step index, current test nodeid — see module docstring).
        self._state_lock = threading.RLock()
        self._tls = threading.local()

        # Accumulated session-wide counters — mutate under _state_lock.
        self._total = 0
        self._passed = 0
        self._failed = 0
        self._errors = 0
        self._start_time: Optional[float] = None

        # Per-test tracking dicts — keyed by nodeid; mutate under _state_lock.
        self._test_starts: Dict[str, float] = {}
        self._test_output: Dict[str, str] = {}

        # Track which slot indices have had target-start reported.
        self._started_slots: set = set()

        # Execution-level measurements — test code can attach custom
        # data that gets merged into the execution-result payload.
        self.execution_measurements: Dict[str, Any] = {}

        # Live log streaming state.
        self._log_buffer: str = ""
        self._log_buffer_lock = threading.Lock()
        self._log_offsets: Dict[str, int] = {}
        self._flush_thread: Optional[threading.Thread] = None
        self._flush_stop_event = threading.Event()
        self._original_stdout = None
        self._original_stderr = None
        self._stream_capture_enabled = _LOG_STREAM_ENABLED

        if self.enabled and not _HAS_REQUESTS:
            log.warning(
                "ConcordReporter: enabled but 'requests' package is not "
                "installed; disabling reporter."
            )
            self.enabled = False

        if self.enabled:
            log.info(
                "ConcordReporter: active (run_id=%s, api=%s, stream=%s)",
                self.run_id,
                self.api_url,
                self._stream_capture_enabled,
            )
        else:
            log.debug("ConcordReporter: inactive")

    # ─────────────────────────────────────────────────────────────────
    # Construction from environment
    # ─────────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> Optional["ConcordReporter"]:
        """Build a reporter from ``CONCORD_*`` env vars, or return ``None``.

        The reporter is inert (returns ``None``) unless both
        ``CONCORD_RUN_ID`` / ``CONCORD_SESSION_ID`` and
        ``CONCORD_API_URL`` are set. Callers (``pytest_configure``)
        only register the plugin when this returns an instance.
        """
        run_id = get_run_id()
        api_url = (os.environ.get("CONCORD_API_URL") or "").strip()
        if not run_id or not api_url:
            return None
        api_key = os.environ.get("CONCORD_API_KEY") or None
        return cls(run_id=run_id, api_url=api_url, api_key=api_key, enabled=True)

    # ─────────────────────────────────────────────────────────────────
    # Public API used by tests (``report`` fixture)
    # ─────────────────────────────────────────────────────────────────

    def step(self, name: str) -> "StepReporter | NoOpStepReporter":
        """Context manager for a named sub-step.

        .. note::

           This variant infers the owning pytest item from the caller's
           thread-local state and is kept for backward compatibility
           with the ``report.step("...")`` call sites. For new code and
           tests, prefer :meth:`step_for` which takes the item
           explicitly.
        """
        item = getattr(self._tls, "current_item", None)
        if item is None:
            return NoOpStepReporter()
        return StepReporter(self, item, name)

    def step_for(self, item: Any, name: str) -> StepReporter:
        """Context manager for a sub-step bound to a specific pytest item."""
        return StepReporter(self, item, name)

    # ─────────────────────────────────────────────────────────────────
    # Single-emit payload path
    # ─────────────────────────────────────────────────────────────────

    def _emit(self, item: Any, endpoint: str, **fields: Any) -> None:
        """Build and POST a payload for ``endpoint`` attributed to ``item``.

        Reads the :class:`SlotBinding` from ``item.stash`` (when
        present) and injects ``slotIndex`` / ``deviceSerial``. ``None``
        values in ``fields`` are dropped so the backend doesn't see
        explicit nulls.
        """
        if not self.enabled:
            return
        payload: Dict[str, Any] = {k: v for k, v in fields.items() if v is not None}
        binding = self._binding_for(item)
        if binding is not None:
            payload["slotIndex"] = binding.slot_index
            if binding.serial_number is not None:
                payload["deviceSerial"] = binding.serial_number
        self._post(f"report/{endpoint}", payload)

    @staticmethod
    def _binding_for(item: Any) -> Optional[SlotBinding]:
        """Return the :class:`SlotBinding` stashed on ``item``, or ``None``.

        Tolerant of stub items whose ``stash`` is a plain dict or whose
        ``get_binding`` dispatch would otherwise fail.
        """
        if item is None:
            return None
        stash = getattr(item, "stash", None)
        if stash is None:
            return None
        # Prefer the typed helper when the stash object supports it.
        try:
            return get_binding(item)
        except Exception:  # pragma: no cover — defensive for exotic stubs
            return None

    # ─────────────────────────────────────────────────────────────────
    # Step counter (thread-local)
    # ─────────────────────────────────────────────────────────────────

    def _next_step_index(self) -> int:
        """Increment and return the next step index for the current thread."""
        next_idx = getattr(self._tls, "step_counter", 0)
        self._tls.step_counter = next_idx + 1
        return next_idx

    def _reset_step_counter(self) -> None:
        self._tls.step_counter = 0
        self._tls.current_step_index = None

    # ─────────────────────────────────────────────────────────────────
    # HTTP
    # ─────────────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        host_header = os.environ.get("CONCORD_API_HOST")
        if host_header:
            headers["Host"] = host_header
        return headers

    def _post(self, path: str, json_data: Dict[str, Any]) -> Optional[Dict]:
        """POST to Concord API. Returns JSON or ``None`` on failure.

        Reporter must never fail a test — every network error is
        swallowed and logged.
        """
        url = f"{self.api_url}/v2/runs/{self.run_id}/{path}"
        try:
            resp = requests.post(
                url,
                json=json_data,
                headers=self._headers(),
                timeout=10,
                verify=_TLS_VERIFY,
            )
            if resp.status_code >= 400:
                log.warning(
                    "ConcordReporter: %s returned %d: %s",
                    path,
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            return resp.json()
        except Exception as exc:
            log.warning("ConcordReporter: %s failed: %s", path, exc)
            return None

    # ─────────────────────────────────────────────────────────────────
    # Live log streaming
    # ─────────────────────────────────────────────────────────────────

    def _on_output(self, data: str) -> None:
        """Callback for captured stdout/stderr writes."""
        with self._log_buffer_lock:
            self._log_buffer += data
            nodeid = getattr(self._tls, "current_test_nodeid", None)
            if nodeid:
                prev = self._test_output.get(nodeid, "")
                self._test_output[nodeid] = prev + data

    def _flush_log_buffer(self) -> None:
        """Drain the log buffer and POST a base64 chunk.

        Log chunks are session/file-level: the backend demuxes by
        ``file`` path (per-slot if a device serial is known), not by
        ``slotIndex``. No :meth:`_emit` here.
        """
        with self._log_buffer_lock:
            if not self._log_buffer:
                return
            data = self._log_buffer
            self._log_buffer = ""
            test_name = getattr(self._tls, "current_test_name", None)
            step_index = getattr(self._tls, "current_step_index", None)
            device_serial = getattr(self._tls, "current_device_for_logs", None)

        try:
            encoded = base64.b64encode(
                data.encode("utf-8", errors="replace")
            ).decode("ascii")
            # Per-slot log routing: if a serial is known, file under it;
            # single-slot runs keep the legacy ``output.log`` name.
            log_file = f"{device_serial}/output.log" if device_serial else "output.log"
            offset_key = device_serial or "__default__"
            current_offset = self._log_offsets.get(offset_key, 0)

            payload: Dict[str, Any] = {
                "file": log_file,
                "offset": current_offset,
                "data": encoded,
                "testName": test_name,
                "timestamp": int(time.time() * 1000),
            }
            if step_index is not None:
                payload["stepIndex"] = step_index
            if device_serial is not None:
                payload["deviceSerial"] = device_serial
            self._log_offsets[offset_key] = current_offset + len(
                data.encode("utf-8", errors="replace")
            )
            # Strip None values for the same reason _emit does.
            payload = {k: v for k, v in payload.items() if v is not None}
            if self.enabled:
                self._post("report/log-chunk", payload)
        except Exception as exc:
            log.warning("ConcordReporter: log flush failed: %s", exc)

    def _flush_loop(self) -> None:
        """Background flush thread."""
        while not self._flush_stop_event.wait(_LOG_FLUSH_INTERVAL):
            self._flush_log_buffer()
        # Final flush on stop
        self._flush_log_buffer()

    def _start_stream_capture(self) -> None:
        if not self._stream_capture_enabled:
            return
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = StreamCapture(self._original_stdout, self._on_output)
        sys.stderr = StreamCapture(self._original_stderr, self._on_output)
        self._flush_stop_event.clear()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def _stop_stream_capture(self) -> None:
        if not self._stream_capture_enabled:
            return
        self._flush_stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr

    # ─────────────────────────────────────────────────────────────────
    # pytest hooks
    # ─────────────────────────────────────────────────────────────────

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Fire ``report/start`` and install the stream capture hooks."""
        if not self.enabled:
            return
        self._start_time = time.monotonic()
        self._post("report/start", {"started": True})
        self._start_stream_capture()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Pre-populate the run's test list — session-level, no attribution."""
        if not self.enabled:
            return
        tests = []
        for item in session.items:
            module, test_name = _parse_nodeid(item.nodeid)
            tests.append({"name": test_name, "module": module})
        self._post("report/test-list", {"tests": tests})

    def pytest_runtest_logstart(self, nodeid: str, location: tuple) -> None:
        """Mark test start time, reset per-thread step counter.

        This hook doesn't emit any attributed payload. The actual
        ``execution-start`` fires from :meth:`pytest_runtest_setup`
        where the pytest ``item`` (and its stash) is in scope.
        """
        if not self.enabled:
            return
        with self._state_lock:
            self._test_starts[nodeid] = time.monotonic()
        self._reset_step_counter()
        self.execution_measurements = {}
        # TLS: record the nodeid so the log flush thread can tag chunks.
        _, test_name = _parse_nodeid(nodeid)
        self._tls.current_test_nodeid = nodeid
        self._tls.current_test_name = test_name
        # Flush any pending logs before the new test's output begins.
        self._flush_log_buffer()

    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        """Fire ``target-start`` (once per slot) and ``execution-start``.

        The stash-based attribution is read here — by this point the
        collection phase has already stashed any :class:`SlotBinding`
        on the item.
        """
        if not self.enabled:
            return
        # Stash the item on TLS so the legacy ``report.step("name")``
        # call (which takes no item arg) can find it.
        self._tls.current_item = item

        binding = self._binding_for(item)

        # Update the log router's per-thread device hint so log chunks
        # file under the right serial (independent of _emit attribution).
        if binding is not None and binding.serial_number:
            self._tls.current_device_for_logs = binding.serial_number
        else:
            self._tls.current_device_for_logs = None

        # Fire target-start the first time we see a test for each slot.
        if binding is not None:
            fire_target_start = False
            with self._state_lock:
                if binding.slot_index not in self._started_slots:
                    self._started_slots.add(binding.slot_index)
                    fire_target_start = True
            if fire_target_start:
                self._emit(
                    item,
                    "target-start",
                    serialNumber=binding.serial_number,
                )

        module, test_name = _parse_nodeid(item.nodeid)
        self._emit(item, "execution-start", testName=test_name, module=module)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo):
        """Dispatch to skip/result helpers based on phase and outcome."""
        outcome = yield
        if not self.enabled:
            return
        report = outcome.get_result()
        if report.when == "setup" and report.skipped:
            self._handle_skip_result(item)
            return
        # A setup-phase failure means a fixture raised before the test
        # body ran — pytest reports it as ERROR and never invokes the
        # call phase. Without this branch the execution row stays at
        # its initial state forever and the failure is silent.
        if report.when == "setup" and report.failed:
            self._accumulate_output(item, report)
            self._handle_setup_error(item, report)
            return
        self._accumulate_output(item, report)
        if report.when != "call":
            return
        self._report_test_result(item, report)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Flush logs and fire the session summary."""
        if not self.enabled:
            return
        self._stop_stream_capture()
        duration_s = None
        if self._start_time is not None:
            duration_s = time.monotonic() - self._start_time
        self._post(
            "report/finish",
            {
                "total": self._total,
                "passed": self._passed,
                "failed": self._failed,
                "errors": self._errors,
                "durationS": round(duration_s, 2) if duration_s is not None else None,
            },
        )
        log.info(
            "ConcordReporter: session finished — %d total, %d passed, %d failed, %d errors",
            self._total,
            self._passed,
            self._failed,
            self._errors,
        )

    # ─────────────────────────────────────────────────────────────────
    # makereport helpers
    # ─────────────────────────────────────────────────────────────────

    def _handle_skip_result(self, item: pytest.Item) -> None:
        """Fire ``execution-result`` for a setup-phase skip."""
        with self._state_lock:
            self._total += 1
        module, _ = _parse_nodeid(item.nodeid)
        self._emit(
            item,
            "execution-result",
            testName=item.name,
            module=module,
            passed=True,
            durationS=0,
            skipped=True,
        )

    def _handle_setup_error(self, item: pytest.Item, report) -> None:
        """Fire ``execution-result`` for a setup-phase fixture failure.

        Pytest reports a fixture exception as ``report.failed`` with
        ``report.when == "setup"`` and never invokes the call phase.
        Emit a fail result with the captured traceback so the operator
        sees *why* the fixture cascade-skipped downstream tests.
        """
        with self._state_lock:
            self._total += 1
            self._errors += 1
        module, _ = _parse_nodeid(item.nodeid)
        # ``report.longreprtext`` is pytest's pre-rendered traceback;
        # fall back to ``str(longrepr)`` for older pytest versions.
        err_text = (
            getattr(report, "longreprtext", None)
            or (str(report.longrepr) if report.longrepr else "fixture setup failed")
        )
        # Trim to keep payloads reasonable; the full log is still in MinIO.
        if len(err_text) > 4000:
            err_text = err_text[:4000] + "\n... (truncated)"
        self._emit(
            item,
            "execution-result",
            testName=item.name,
            module=module,
            passed=False,
            durationS=0,
            skipped=False,
            errorMessage=err_text,
        )

    def _accumulate_output(self, item: pytest.Item, report) -> None:
        """Merge captured output from a test phase into the per-test buffer."""
        captured = getattr(report, "capstderr", "") or ""
        if captured.strip():
            with self._state_lock:
                prev = self._test_output.get(item.nodeid, "")
                self._test_output[item.nodeid] = prev + captured

    def _report_test_result(self, item: pytest.Item, report) -> None:
        """Fire ``execution-result`` once per call phase (pass/fail/skipped)."""
        with self._state_lock:
            self._total += 1
            if report.skipped:
                pass
            elif report.passed:
                self._passed += 1
            elif report.failed:
                self._failed += 1
            else:
                self._errors += 1

        duration_s: Optional[float] = None
        with self._state_lock:
            start = self._test_starts.get(item.nodeid)
        if start is not None:
            duration_s = time.monotonic() - start

        error_message: Optional[str] = None
        if report.failed and report.longrepr:
            error_message = str(report.longrepr)[:2000]

        # Drain any pending log buffer so per-test output is complete.
        self._flush_log_buffer()
        with self._state_lock:
            log_output = self._test_output.pop(item.nodeid, None)
        if log_output:
            log_output = log_output.strip()[:10000]

        # Auto-extract power measurements from ctx.power when present.
        measurements: Optional[Dict[str, Any]] = None
        ctx = item.funcargs.get("ctx") if hasattr(item, "funcargs") else None
        if ctx and hasattr(ctx, "power") and hasattr(ctx.power, "last_measurement"):
            meas = ctx.power.last_measurement
            if meas:
                measurements = {
                    "current_ma": getattr(meas, "current_ma", None),
                    "voltage_v": getattr(meas, "voltage_v", None),
                    "power_mw": getattr(meas, "power_mw", None),
                    "duration_s": getattr(meas, "duration_s", None),
                }
        if self.execution_measurements:
            measurements = {**(measurements or {}), **self.execution_measurements}

        module, _ = _parse_nodeid(item.nodeid)
        self._emit(
            item,
            "execution-result",
            testName=item.name,
            module=module,
            passed=bool(report.passed),
            skipped=bool(report.skipped),
            durationS=duration_s,
            errorMessage=error_message,
            measurements=measurements,
            logOutput=log_output,
        )


# ──────────────────────────────────────────────────────────────────────
# Pytest fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def report(request):
    """Active :class:`ConcordReporter` or :class:`NoOpReporter` offline.

    Usage::

        def test_boot(report, dut):
            with report.step("Power on"):
                dut.power_enable(0, 4.5)
    """
    reporter = getattr(request.config, "_concord_reporter", None)
    if reporter is None:
        return NoOpReporter()
    return reporter


# ──────────────────────────────────────────────────────────────────────
# Plugin registration
# ──────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register a :class:`ConcordReporter` when env vars are set.

    Stashes the instance on ``config._concord_reporter`` for the
    ``report`` fixture to find, then registers it with the plugin
    manager so the pytest hooks fire.
    """
    reporter = ConcordReporter.from_env()
    if reporter is None:
        return
    config._concord_reporter = reporter
    config.pluginmanager.register(reporter, "concord_reporter")
