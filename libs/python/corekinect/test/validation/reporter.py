"""Concord Reporter — pytest plugin that reports results to the Concord HTTP API.

Opt-in activation via environment variables:
    CONCORD_RUN_ID:  The validation run ID (from POST /v2/validation/runs).
    CONCORD_API_URL: Base URL of the Concord HTTP API (e.g., http://concord-api:9001).
    CONCORD_API_KEY: API key for authentication (ApiKey header).

When these are NOT set, the reporter does absolutely nothing — tests run
exactly as they always have. This is the "offline mode" for local
development and SSH-based runs.

When activated, the reporter makes HTTP calls to the 6A callback endpoints:
    POST /v2/validation/runs/<id>/report/start
    POST /v2/validation/runs/<id>/report/test-start
    POST /v2/validation/runs/<id>/report/test-result
    POST /v2/validation/runs/<id>/report/finish

All HTTP calls are fire-and-forget with error handling — the reporter NEVER
causes a test to fail. If the API is unreachable, errors are logged and
the test suite continues normally.

Registration:
    Add to conftest.py (already done):
        from .reporter import ConcordReporter
        def pytest_configure(config):
            config.pluginmanager.register(ConcordReporter(config), "concord_reporter")

    Or via pytest_plugins in conftest.py:
        pytest_plugins = ["corekinect.test.validation.reporter"]
"""

import os
import time
from typing import Any, Dict, Optional

import pytest

from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="concord_reporter")

# Attempt to import requests; if not installed, reporter is disabled.
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class ConcordReporter:
    """pytest plugin that reports validation results to Concord HTTP API."""

    def __init__(self, config: Optional[Any] = None):
        self.run_id = os.environ.get("CONCORD_RUN_ID") or ""
        self.api_url = (os.environ.get("CONCORD_API_URL") or "").rstrip("/")
        self.api_key = os.environ.get("CONCORD_API_KEY") or ""
        self.enabled = bool(self.run_id and self.api_url)

        # Accumulated counters
        self._total = 0
        self._passed = 0
        self._failed = 0
        self._errors = 0
        self._start_time: Optional[float] = None

        # Per-test tracking: nodeid → start time
        self._test_starts: Dict[str, float] = {}
        # Per-test captured output: nodeid → log lines
        self._test_output: Dict[str, str] = {}

        if self.enabled and not _HAS_REQUESTS:
            log.warning(
                "ConcordReporter: CONCORD_RUN_ID is set but 'requests' "
                "package is not installed. Reporter disabled."
            )
            self.enabled = False

        if self.enabled:
            log.info(
                "ConcordReporter: active (run_id=%s, api=%s)",
                self.run_id,
                self.api_url,
            )
        else:
            log.debug("ConcordReporter: inactive (CONCORD_RUN_ID not set)")

    # ── HTTP helpers ──────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        # Allow Host header override for ingress routing when using IP address
        host_header = os.environ.get("CONCORD_API_HOST")
        if host_header:
            headers["Host"] = host_header
        return headers

    def _post(self, path: str, json_data: Dict[str, Any]) -> Optional[Dict]:
        """POST to Concord API. Returns response JSON or None on failure."""
        url = f"{self.api_url}/v2/validation/runs/{self.run_id}/{path}"
        try:
            resp = requests.post(url, json=json_data, headers=self._headers(), timeout=10, verify=False)
            if resp.status_code >= 400:
                log.warning(
                    "ConcordReporter: %s returned %d: %s",
                    path, resp.status_code, resp.text[:200],
                )
                return None
            return resp.json()
        except Exception as e:
            log.warning("ConcordReporter: %s failed: %s", path, e)
            return None

    # ── pytest hooks ──────────────────────────────────────

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Called after Session object created, before collection."""
        if not self.enabled:
            return
        self._start_time = time.monotonic()
        self._post("report/start", {"started": True})

    def pytest_runtest_logstart(self, nodeid: str, location: tuple) -> None:
        """Called at the start of running a test item."""
        if not self.enabled:
            return

        self._test_starts[nodeid] = time.monotonic()

        # Extract module and test name from nodeid
        # e.g., "tests/stage4/test_boot.py::test_power_cycle" → module=test_boot, name=test_power_cycle
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

        self._post("report/test-start", {
            "testName": test_name,
            "module": module,
        })

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> None:
        """Called to create a TestReport for each test phase (setup/call/teardown)."""
        outcome = yield
        if not self.enabled:
            return

        report = outcome.get_result()

        # Handle skips during setup phase (no call phase will follow)
        if report.when == "setup" and report.skipped:
            self._total += 1
            self._post("report/test-result", {
                "testName": item.name,
                "passed": True,
                "durationS": 0,
                "errorMessage": None,
                "measurements": None,
                "skipped": True,
            })
            return

        # Accumulate captured output from all phases
        captured = ""
        if report.capstdout:
            captured += report.capstdout
        if report.capstderr:
            captured += report.capstderr
        if report.caplog:
            captured += report.caplog
        # Also capture sections (pytest log output, etc.)
        for title, content in report.sections:
            captured += f"\n--- {title} ---\n{content}"

        if captured.strip():
            prev = self._test_output.get(item.nodeid, "")
            self._test_output[item.nodeid] = prev + captured

        # Only report on the "call" phase (the actual test), not setup/teardown
        if report.when != "call":
            return

        self._total += 1
        test_name = item.name
        passed = report.passed

        if report.passed:
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

        # Collect captured log output for this test
        log_output = self._test_output.pop(item.nodeid, None)
        if log_output:
            log_output = log_output.strip()[:10000]  # Cap at 10KB

        # Extract power measurements from test context if available
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

        self._post("report/test-result", {
            "testName": test_name,
            "passed": passed,
            "durationS": duration_s,
            "errorMessage": error_message,
            "measurements": measurements,
            "logOutput": log_output,
        })

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Called after whole test run finished."""
        if not self.enabled:
            return

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


# ── Plugin registration ──────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """Register ConcordReporter if CONCORD_RUN_ID is set.

    This function is discovered by pytest when this module is listed
    in pytest_plugins or when the package is installed as a plugin.
    """
    if os.environ.get("CONCORD_RUN_ID"):
        reporter = ConcordReporter(config)
        config.pluginmanager.register(reporter, "concord_reporter")
