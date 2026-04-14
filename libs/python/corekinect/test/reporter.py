"""Pytest plugin that reports test results to the Concord HTTP API.

Activated by env vars: CONCORD_SESSION_ID (or legacy CONCORD_RUN_ID),
CONCORD_API_URL, CONCORD_API_KEY.
When not set, the plugin is inert -- tests run normally with zero overhead.

All HTTP calls are fire-and-forget. The reporter never causes a test to fail.

Features:
  - Test start/result/finish callbacks to /v2/runs/<id>/report/*
  - Live stdout/stderr streaming via log-chunk endpoint
  - Sub-step reporting via ``report.step("name")`` context manager
  - Multi-device support via ``reporter.set_device(serial)``

Registration (in conftest.py):
    pytest_plugins = ["corekinect.test.reporter"]
"""

import base64
import io
import os
import sys
import threading
import time
from typing import Any, Dict, Optional

import pytest

from corekinect.test.env import get_run_id
from corekinect.utils import EnvConfig, Logger

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


class StreamCapture(io.TextIOBase):
    """Tee stream writes to a callback while passing through to the original stream."""

    def __init__(self, original_stream, callback):
        """  init  ."""
        self.original = original_stream
        self.callback = callback
        self._lock = threading.Lock()

    def write(self, data):
        """Write."""
        if data:
            with self._lock:
                # Write to original stream
                if self.original:
                    self.original.write(data)
                    self.original.flush()
                # Notify callback
                self.callback(data)
        return len(data) if data else 0

    def flush(self):
        """Flush."""
        if self.original:
            self.original.flush()

    def fileno(self):
        """Fileno."""
        if self.original:
            return self.original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        """Isatty."""
        return self.original.isatty() if self.original else False


class StepReporter:
    """Context manager for sub-step tracking. Fires step-start/step-result callbacks.

    If the block raises, the step is marked failed and the exception propagates.
    """

    def __init__(self, reporter: "ConcordReporter", step_name: str):
        """  init  ."""
        self.reporter = reporter
        self.step_name = step_name
        self.step_index = reporter._next_step_index()
        self.measurements = {}

    def __enter__(self):
        """  enter  ."""
        self.reporter._fire_callback("step-start", {
            "testName": self.reporter._current_test_name,
            "deviceSerial": self.reporter._current_device,
            "stepName": self.step_name,
            "stepIndex": self.step_index,
        })
        self.reporter._current_step_index = self.step_index
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """  exit  ."""
        passed = exc_type is None
        payload = {
            "testName": self.reporter._current_test_name,
            "deviceSerial": self.reporter._current_device,
            "stepIndex": self.step_index,
            "passed": passed,
            "errorMessage": str(exc_val) if exc_val else None,
        }
        if self.measurements:
            payload["measurements"] = self.measurements
        self.reporter._fire_callback("step-result", payload)
        self.reporter._current_step_index = None
        return False  # Don't suppress exceptions

    def record(self, key: str, value, unit: str = None):
        """Record a measurement for this step.

        Usage::

            with report.step("Verify voltage") as step:
                voltage = read_voltage()
                step.record("voltage_3v3", voltage, unit="V")
                step.record("current", current, unit="mA")
                assert voltage > 3.0
        """
        entry = {"value": value}
        if unit:
            entry["unit"] = unit
        self.measurements[key] = entry

    def record_dict(self, data: dict):
        """Record multiple measurements at once.

        Usage::

            with report.step("Electrical state") as step:
                step.record_dict({
                    "batt_sys_voltage": {"value": 3.7, "unit": "V"},
                    "current_a": {"value": 0.015, "unit": "A"},
                    "voltage_3v3": {"value": 3.31, "unit": "V"},
                })
                assert ...
        """
        self.measurements.update(data)


class NoOpStepReporter:
    """No-op step context manager for offline mode."""

    def __init__(self):
        """  init  ."""
        self.measurements = {}

    def __enter__(self):
        """  enter  ."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """  exit  ."""
        return False

    def record(self, key: str, value, unit: str = None):
        """No-op measurement recording."""
        pass

    def record_dict(self, data: dict):
        """No-op batch measurement recording."""
        pass


class NoOpReporter:
    """No-op reporter for offline/local runs. Same interface as ConcordReporter."""

    def __init__(self):
        """  init  ."""
        self.execution_measurements: Dict[str, Any] = {}

    def step(self, name: str) -> NoOpStepReporter:
        """Return a no-op step context manager."""
        return NoOpStepReporter()

    def set_device(self, serial: str) -> None:
        """No-op device setter."""
        pass


class ConcordReporter:
    """Pytest plugin that streams test results to the Concord API.

    Inert when CONCORD_SESSION_ID / CONCORD_RUN_ID is not set. All HTTP calls
    are fire-and-forget.
    """

    def __init__(self, config: Optional[Any] = None):
        """Initialize from CONCORD_* env vars. Inert if run ID not set."""
        self.run_id = get_run_id()
        self.api_url = (os.environ.get("CONCORD_API_URL") or "").rstrip("/")
        self.api_key = os.environ.get("CONCORD_API_KEY") or ""
        self.enabled = bool(self.run_id and self.api_url)

        # Accumulated counters
        self._total = 0
        self._passed = 0
        self._failed = 0
        self._errors = 0
        self._start_time: Optional[float] = None

        # Per-test tracking: nodeid -> start time
        self._test_starts: Dict[str, float] = {}
        # Per-test captured output: nodeid -> log lines
        self._test_output: Dict[str, str] = {}

        # Multi-device support: serial of the currently active DUT
        self._current_device: Optional[str] = None

        # Sub-step tracking (reset per test)
        self._step_counter: int = 0
        self._current_step_index: Optional[int] = None

        # Execution-level measurements — test code can attach custom data
        # that gets merged into the execution-result payload alongside
        # auto-extracted power measurements. Reset per test.
        self.execution_measurements: Dict[str, Any] = {}

        # Live log streaming state
        self._current_test_name: Optional[str] = None
        self._current_test_nodeid: Optional[str] = None
        self._log_buffer: str = ""
        self._log_buffer_lock = threading.Lock()
        self._log_offsets: Dict[str, int] = {}  # per-device log offsets
        self._flush_thread: Optional[threading.Thread] = None
        self._flush_stop_event = threading.Event()
        self._original_stdout = None
        self._original_stderr = None
        self._stream_capture_enabled = _LOG_STREAM_ENABLED

        # Store reference on config for the report fixture to find
        if config is not None:
            config._concord_reporter = self

        if self.enabled and not _HAS_REQUESTS:
            log.warning(
                "ConcordReporter: CONCORD_RUN_ID is set but 'requests' "
                "package is not installed. Reporter disabled."
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
            log.debug("ConcordReporter: inactive (CONCORD_SESSION_ID / CONCORD_RUN_ID not set)")

    # -- Multi-device support -----------------------------------------

    def set_device(self, serial: str) -> None:
        """Set the active device serial for subsequent callbacks."""
        self._current_device = serial

    # -- Sub-step support ---------------------------------------------

    def step(self, name: str) -> StepReporter:
        """Return a sub-step context manager that fires step-start/step-result."""
        return StepReporter(self, name)

    def _next_step_index(self) -> int:
        """Increment and return the next step index for the current test."""
        self._step_counter += 1
        return self._step_counter

    # -- HTTP helpers -------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        """ headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        # Allow Host header override for ingress routing when using IP address
        host_header = os.environ.get("CONCORD_API_HOST")
        if host_header:
            headers["Host"] = host_header
        return headers

    def _post(self, path: str, json_data: Dict[str, Any]) -> Optional[Dict]:
        """POST to Concord API. Returns JSON or None on failure."""
        url = f"{self.api_url}/v2/runs/{self.run_id}/{path}"
        try:
            resp = requests.post(url, json=json_data, headers=self._headers(), timeout=10, verify=_TLS_VERIFY)
            if resp.status_code >= 400:
                log.warning(
                    "ConcordReporter: %s returned %d: %s",
                    path, resp.status_code, resp.text[:200],
                )
                return None
            return resp.json()
        except Exception as e:
            # Reporter must never fail tests — log and continue
            log.warning("ConcordReporter: %s failed: %s", path, e)
            return None

    def _fire_callback(self, endpoint: str, payload: Dict[str, Any]) -> None:
        """Fire-and-forget POST. Strips None keys for backward compat."""
        if not self.enabled:
            return
        # Remove None values so the backend doesn't receive explicit nulls
        # for fields it doesn't expect yet (backwards compat)
        clean = {k: v for k, v in payload.items() if v is not None}
        self._post(f"report/{endpoint}", clean)

    # -- Live log streaming -------------------------------------------

    def _on_output(self, data: str) -> None:
        """Callback for captured stdout/stderr data."""
        with self._log_buffer_lock:
            self._log_buffer += data
            # Also accumulate per-test output for the test-result logOutput field.
            # This ensures logOutput is populated even with -s (no pytest capture).
            nodeid = self._current_test_nodeid
            if nodeid:
                prev = self._test_output.get(nodeid, "")
                self._test_output[nodeid] = prev + data

    def _flush_log_buffer(self) -> None:
        """Drain log buffer and POST base64-encoded content to log-chunk."""
        with self._log_buffer_lock:
            if not self._log_buffer:
                return
            data = self._log_buffer
            self._log_buffer = ""
            test_name = self._current_test_name
            step_index = self._current_step_index
            device_serial = self._current_device

        # Build payload (outside lock to avoid blocking)
        try:
            encoded = base64.b64encode(data.encode("utf-8", errors="replace")).decode("ascii")
            # Per-slot log isolation: if device_serial is set (multi-slot),
            # prefix the file with the serial so each DUT gets its own log.
            # Single-slot runs keep "output.log" for backward compat.
            if device_serial:
                log_file = f"{device_serial}/output.log"
            else:
                log_file = "output.log"

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

            self._post("report/log-chunk", payload)
            self._log_offsets[offset_key] = current_offset + len(data.encode("utf-8", errors="replace"))
        except Exception as e:
            # Reporter must never fail tests — log and continue
            log.warning("ConcordReporter: log flush failed: %s", e)

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes log buffer."""
        while not self._flush_stop_event.wait(_LOG_FLUSH_INTERVAL):
            self._flush_log_buffer()
        # Final flush on stop
        self._flush_log_buffer()

    def _start_stream_capture(self) -> None:
        """Install stream capture and start flush thread."""
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
        """Restore original streams and stop flush thread."""
        if not self._stream_capture_enabled:
            return

        # Stop flush thread
        self._flush_stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

        # Restore streams
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr

    # -- pytest hooks -------------------------------------------------

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Called after Session object created, before collection."""
        if not self.enabled:
            return
        self._start_time = time.monotonic()
        self._post("report/start", {"started": True})
        # Start live log streaming
        self._start_stream_capture()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Called after collection is complete — send full test list for pre-population."""
        if not self.enabled:
            return

        tests = []
        for item in session.items:
            parts = item.nodeid.split("::")
            test_name = parts[-1] if parts else item.nodeid
            module = None
            if len(parts) >= 2:
                file_part = parts[0]
                if "/" in file_part:
                    file_part = file_part.rsplit("/", 1)[-1]
                if file_part.endswith(".py"):
                    module = file_part[:-3]
            tests.append({"name": test_name, "module": module})

        self._post("report/test-list", {"tests": tests})

    def pytest_runtest_logstart(self, nodeid: str, location: tuple) -> None:
        """Called at the start of running a test item."""
        if not self.enabled:
            return

        self._test_starts[nodeid] = time.monotonic()

        # Reset step counter and execution measurements for each new test
        self._step_counter = 0
        self._current_step_index = None
        self.execution_measurements = {}

        # Extract module and test name from nodeid
        # e.g., "tests/stage4/test_boot.py::test_power_cycle" -> module=test_boot, name=test_power_cycle
        parts = nodeid.split("::")
        test_name = parts[-1] if parts else nodeid
        module = None
        if len(parts) >= 2:
            # Extract module name from file path
            file_part = parts[0]
            if "/" in file_part:
                file_part = file_part.rsplit("/", 1)[-1]
            if file_part.endswith(".py"):
                module = file_part[:-3]

        # Set current test for log streaming + per-test output accumulation
        self._current_test_name = test_name
        self._current_test_nodeid = nodeid
        # Flush any pending logs before starting new test
        self._flush_log_buffer()

        # Multi-slot: extract slot index from nodeid (e.g., "test_01[slot-2]")
        # and set deviceSerial BEFORE sending execution-start. This is critical
        # because pytest_runtest_logstart fires before fixture setup, so the
        # _test_lifecycle fixture's set_device() call hasn't happened yet.
        import re as _re
        slot_match = _re.search(r"\[slot-(\d+)\]", nodeid)
        if slot_match and hasattr(self, "_slot_serials"):
            slot_idx = int(slot_match.group(1))
            serial = self._slot_serials.get(slot_idx)
            if serial:
                self._current_device = serial

        payload: Dict[str, Any] = {
            "testName": test_name,
            "module": module,
        }
        # Include device serial when set
        if self._current_device is not None:
            payload["deviceSerial"] = self._current_device

        self._post("report/execution-start", payload)

    # -- Report helpers (extracted from pytest_runtest_makereport) -------

    def _handle_skip_result(self, item: pytest.Item) -> None:
        """Report a skipped test (setup-phase skip, no call phase follows)."""
        self._total += 1

        # Extract module from nodeid so skipped tests get grouped correctly
        parts = item.nodeid.split("::")
        module = None
        if len(parts) >= 2:
            file_part = parts[0]
            if "/" in file_part:
                file_part = file_part.rsplit("/", 1)[-1]
            if file_part.endswith(".py"):
                module = file_part[:-3]

        payload: Dict[str, Any] = {
            "testName": item.name,
            "module": module,
            "passed": True,
            "durationS": 0,
            "errorMessage": None,
            "measurements": None,
            "skipped": True,
        }
        if self._current_device is not None:
            payload["deviceSerial"] = self._current_device
        self._post("report/execution-result", payload)

    def _accumulate_output(self, item: pytest.Item, report) -> None:
        """Accumulate captured output from a test phase (setup/call/teardown).

        Only captures stderr (the primary log stream) to avoid duplicate
        output from pytest's section capture (which repeats the same lines
        under different headers like 'Captured stderr call', 'Captured log call').
        """
        captured = ""
        if report.capstderr:
            captured += report.capstderr

        if captured.strip():
            prev = self._test_output.get(item.nodeid, "")
            self._test_output[item.nodeid] = prev + captured

    def _report_test_result(self, item: pytest.Item, report) -> None:
        """Build and POST test-result payload (called once during the call phase)."""
        self._total += 1
        test_name = item.name
        passed = report.passed

        if report.skipped:
            pass  # Skipped — don't count as passed, failed, or error
        elif report.passed:
            self._passed += 1
        elif report.failed:
            self._failed += 1
        else:
            self._errors += 1

        # Calculate duration
        duration_s = None
        start = self._test_starts.get(item.nodeid)
        if start is not None:
            duration_s = time.monotonic() - start

        # Extract error message
        error_message = None
        if report.failed and report.longrepr:
            error_message = str(report.longrepr)[:2000]  # Truncate for API

        # Flush any pending stream capture so _test_output is complete
        self._flush_log_buffer()

        # Collect captured log output for this test.
        # Sources: pytest captured output + StreamCapture _on_output
        log_output = self._test_output.pop(item.nodeid, None)
        if log_output:
            log_output = log_output.strip()[:10000]  # Cap at 10KB

        # Build measurements dict from auto-extracted power data and
        # any custom measurements the test code attached via
        # reporter.execution_measurements.
        measurements = None
        ctx = item.funcargs.get("ctx")
        if ctx and hasattr(ctx, "power") and hasattr(ctx.power, "last_measurement"):
            meas = ctx.power.last_measurement
            if meas:
                measurements = {
                    "current_ma": getattr(meas, "current_ma", None),
                    "voltage_v": getattr(meas, "voltage_v", None),
                    "power_mw": getattr(meas, "power_mw", None),
                    "duration_s": getattr(meas, "duration_s", None),
                }

        # Merge custom execution measurements (test code writes these
        # via reporter.execution_measurements dict)
        if self.execution_measurements:
            if measurements is None:
                measurements = {}
            measurements.update(self.execution_measurements)

        # Resolve module from nodeid (same logic as test-start)
        parts = item.nodeid.split("::")
        module = None
        if len(parts) >= 2:
            file_part = parts[0]
            if "/" in file_part:
                file_part = file_part.rsplit("/", 1)[-1]
            if file_part.endswith(".py"):
                module = file_part[:-3]

        payload: Dict[str, Any] = {
            "testName": test_name,
            "module": module,
            "passed": passed,
            "skipped": bool(report.skipped),
            "durationS": duration_s,
            "errorMessage": error_message,
            "measurements": measurements,
            "logOutput": log_output,
        }
        # Include device serial when set
        if self._current_device is not None:
            payload["deviceSerial"] = self._current_device

        self._post("report/execution-result", payload)

    # -- pytest hook: makereport ----------------------------------------

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> None:
        """Called to create a TestReport for each test phase (setup/call/teardown).

        Dispatches to helper methods for skip handling, output accumulation,
        and result reporting to keep each concern isolated.
        """
        outcome = yield
        if not self.enabled:
            return

        report = outcome.get_result()

        # Handle skips during setup phase (no call phase will follow)
        if report.when == "setup" and report.skipped:
            self._handle_skip_result(item)
            return

        # Accumulate captured output from all phases
        self._accumulate_output(item, report)

        # Only report on the "call" phase (the actual test), not setup/teardown
        if report.when != "call":
            return

        self._report_test_result(item, report)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Called after whole test run finished."""
        if not self.enabled:
            return

        # Stop live log streaming (this flushes remaining logs)
        self._stop_stream_capture()

        duration_s = None
        if self._start_time is not None:
            duration_s = time.monotonic() - self._start_time

        self._post("report/finish", {
            "total": self._total,
            "passed": self._passed,
            "failed": self._failed,
            "errors": self._errors,
            "durationS": round(duration_s, 2) if duration_s is not None else None,
        })

        log.info(
            "ConcordReporter: session finished — %d total, %d passed, %d failed, %d errors",
            self._total, self._passed, self._failed, self._errors,
        )


# -- Pytest fixtures --------------------------------------------------

@pytest.fixture
def report(request):
    """Active ConcordReporter or NoOpReporter for offline mode.

    Usage::

        def test_boot(report, dut):
            with report.step("Power on"):
                dut.power_enable(0, 4.5)
    """
    reporter = getattr(request.config, "_concord_reporter", None)
    if reporter is None:
        return NoOpReporter()
    return reporter


# -- Plugin registration ----------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register ConcordReporter if CONCORD_SESSION_ID or CONCORD_RUN_ID is set.

    This function is discovered by pytest when this module is listed
    in pytest_plugins or when the package is installed as a plugin.
    """
    if get_run_id():
        reporter = ConcordReporter(config)
        config.pluginmanager.register(reporter, "concord_reporter")
