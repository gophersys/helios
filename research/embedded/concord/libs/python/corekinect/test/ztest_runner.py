"""Zephyr ztest runner — hardware path for Concord validation.

This module is the dispatch target the backend Job picks when a
TestPackage declares ``framework: ztest`` in its concord.yaml.

Pipeline
--------

    1.  Discover hex artifacts in the AssetSet directory by label.
    2.  Connect to the MTIB gRPC server controlling the fixture.
    3.  Upload + flash each hex to the relevant processor.
    4.  Subscribe to the UART stream and collect output for up to
        ``timeout_s`` or until the device emits the final
        ``PROJECT EXECUTION`` marker.
    5.  Parse the captured ztest output into structured per-suite,
        per-test results.
    6.  POST one ``execution-start`` + one ``execution-result`` per ztest
        case to the Concord HTTP API under the standard reporter
        contract; finish with a single ``report/finish``.
    7.  Exit:  0 on all-pass, 1 on any test failure, 2 on infra error.

Boundaries / seams
------------------

The MTIB gRPC client is wired via the ``mtib_factory`` callable so unit
tests can substitute a recorded-fixture client. ``requests.Session`` is
likewise injectable via ``session=``. Both injection points exist
purely so the production path can stay real while tests aren't gated on
having a fixture in front of them.

Replay mode
-----------

``replay_uart_log`` reads a captured UART log file, parses it, and runs
the rest of the pipeline (optionally with ``dry_run_http=True`` to
print the payloads instead of POSTing). Used for local iteration on
the parser + reporter without hardware.

CLI
---

::

    python -m corekinect.test.ztest_runner \\
        --run-id <id> --target-id <tid> --asset-set <dir> \\
        --api-url <url> --api-key <key> \\
        --mtib-host <host> [--mtib-port <port>] \\
        --labels <label1,label2,...> [--timeout-s 600]

    # Replay against a captured UART log (no hardware needed):
    python -m corekinect.test.ztest_runner \\
        --replay-uart fixtures/sample-ztest-output.txt \\
        --run-id <id> --target-id <tid> \\
        --api-url <url> --api-key <key> \\
        [--dry-run-http]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import (
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
)

logger = logging.getLogger("ztest_runner")


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_MTIB_PORT = 50053
DEFAULT_TIMEOUT_S = 600
HEARTBEAT_INTERVAL_S = 30.0


# ──────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────


class ZTestParseError(ValueError):
    """Raised when ztest UART output cannot be parsed.

    The capture is too short to be a real ztest run (missing
    ``Running TESTSUITE`` header, empty body, …). Reporting partial
    results would mask a UART loss or device crash, so we surface the
    failure explicitly.
    """


class AssetDiscoveryError(FileNotFoundError):
    """Raised when one or more required ztest hex labels are missing
    from the AssetSet directory."""


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────


class ExitCode(IntEnum):
    SUCCESS = 0
    TEST_FAILURE = 1
    INFRA_ERROR = 2


class Outcome(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class ZTestResult:
    name: str
    outcome: Outcome
    duration_s: float

    @property
    def passed(self) -> bool:
        return self.outcome == Outcome.PASS

    @property
    def failed(self) -> bool:
        return self.outcome == Outcome.FAIL

    @property
    def skipped(self) -> bool:
        return self.outcome == Outcome.SKIP


@dataclass(frozen=True)
class ZTestSuite:
    name: str
    results: List[ZTestResult]
    succeeded: bool

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.failed)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.skipped)


@dataclass(frozen=True)
class ZTestSummary:
    suites: List[ZTestSuite]
    project_succeeded: bool

    @property
    def total(self) -> int:
        return sum(len(s.results) for s in self.suites)

    @property
    def total_passed(self) -> int:
        return sum(s.passed for s in self.suites)

    @property
    def total_failed(self) -> int:
        return sum(s.failed for s in self.suites)

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.suites)

    @property
    def exit_code(self) -> ExitCode:
        if self.project_succeeded and self.total_failed == 0:
            return ExitCode.SUCCESS
        return ExitCode.TEST_FAILURE


@dataclass(frozen=True)
class HexAsset:
    """A single ztest hex file inside the AssetSet, with its label and
    inferred target role (``app`` / ``comms`` / …)."""

    label: str
    path: Path
    role: str  # "app", "comms", etc — used to choose MTIB HostType


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────

# Result line: optional leading whitespace, then PASS|FAIL|SKIP,
# then " - <name> in <secs> seconds". Defensive — handles tabs and
# extra spaces because UART captures vary.
_RESULT_RE = re.compile(
    r"^\s*(PASS|FAIL|SKIP)\s*-\s*(\S+)\s+in\s+([\d.]+)\s+seconds",
    re.MULTILINE,
)
_SUITE_START_RE = re.compile(r"^\s*Running\s+TESTSUITE\s+(\S+)", re.MULTILINE)
_SUITE_END_RE = re.compile(
    r"^\s*TESTSUITE\s+(\S+)\s+(succeeded|failed)", re.MULTILINE
)
_PROJECT_RESULT_RE = re.compile(
    r"^\s*PROJECT\s+EXECUTION\s+(SUCCESSFUL|FAILED)", re.MULTILINE
)


def parse_ztest_output(text: str) -> ZTestSummary:
    """Parse a captured ztest UART log into a :class:`ZTestSummary`.

    Tolerates Zephyr log noise (``[ts] <lvl> module: msg``), boot
    banners, ANSI escapes, and missing optional markers. Raises
    :class:`ZTestParseError` when the input lacks a ``Running TESTSUITE``
    header or contains no result lines at all — those failures point
    at UART capture problems, not at a clean "no tests" outcome.
    """
    if not text or not text.strip():
        raise ZTestParseError("Empty UART output — capture failed before any data arrived")

    suite_starts = list(_SUITE_START_RE.finditer(text))
    if not suite_starts:
        raise ZTestParseError(
            "No 'Running TESTSUITE' marker found in UART output — "
            "device may have crashed before ztest started, or UART was lost"
        )

    suite_ends = {m.group(1): m.group(2) for m in _SUITE_END_RE.finditer(text)}

    # Walk the result regex across the full buffer, then bucket by
    # the suite whose start offset most recently precedes the match.
    suite_boundaries: List[tuple] = []  # (start_offset, suite_name)
    for m in suite_starts:
        suite_boundaries.append((m.start(), m.group(1)))

    def _suite_at(offset: int) -> Optional[str]:
        current = None
        for start, name in suite_boundaries:
            if start <= offset:
                current = name
            else:
                break
        return current

    results_by_suite: dict = {name: [] for _, name in suite_boundaries}
    for m in _RESULT_RE.finditer(text):
        suite_name = _suite_at(m.start())
        if suite_name is None:
            # Result line before any suite start — treat as parse failure.
            continue
        outcome = Outcome(m.group(1))
        test_name = m.group(2)
        duration_s = float(m.group(3))
        results_by_suite[suite_name].append(
            ZTestResult(name=test_name, outcome=outcome, duration_s=duration_s)
        )

    suites: List[ZTestSuite] = []
    for _, suite_name in suite_boundaries:
        results = results_by_suite[suite_name]
        end_status = suite_ends.get(suite_name)
        # Suite succeeded only if: end marker says so AND no failures.
        # When end marker is missing (capture truncated), infer from results.
        if end_status is not None:
            succeeded = end_status == "succeeded" and not any(r.failed for r in results)
        else:
            succeeded = bool(results) and not any(r.failed for r in results)
        suites.append(ZTestSuite(name=suite_name, results=results, succeeded=succeeded))

    if all(not s.results for s in suites):
        raise ZTestParseError(
            "TESTSUITE markers found but no PASS/FAIL/SKIP result lines — "
            "ztest may have hung or output was lost mid-suite"
        )

    project_match = _PROJECT_RESULT_RE.search(text)
    if project_match is not None:
        project_succeeded = project_match.group(1) == "SUCCESSFUL"
    else:
        # No final marker — infer from suite outcomes.
        project_succeeded = all(s.succeeded for s in suites)

    return ZTestSummary(suites=suites, project_succeeded=project_succeeded)


# ──────────────────────────────────────────────────────────────────────
# AssetSet discovery
# ──────────────────────────────────────────────────────────────────────


_ROLE_FROM_LABEL_RE = re.compile(r"_([a-z][a-z0-9]*)_ztest$")


def _role_for_label(label: str) -> str:
    """Infer the processor role from a label like ``smoke_app_ztest``.

    Returns ``"app"`` when the label has no role suffix — that covers the
    single-processor case where the label is simply ``ztest`` or
    ``something_ztest`` (no middle component).
    """
    m = _ROLE_FROM_LABEL_RE.search(label)
    if m:
        return m.group(1)
    return "app"


def discover_hex_files(
    asset_set_dir: Path,
    labels: Sequence[str],
) -> List[HexAsset]:
    """Locate the ztest hex artifacts for the requested labels.

    Each label maps to ``<label>.hex`` inside ``asset_set_dir``. Raises
    :class:`AssetDiscoveryError` if the directory doesn't exist or any
    label is missing — we never silently flash less than the caller asked
    for, because that produces tests-not-run results that look like
    tests-skipped to the operator.
    """
    asset_set_dir = Path(asset_set_dir)
    if not asset_set_dir.is_dir():
        raise AssetDiscoveryError(
            f"Asset set directory not found or not a directory: {asset_set_dir}"
        )

    found: List[HexAsset] = []
    missing: List[str] = []
    for label in labels:
        hex_path = asset_set_dir / f"{label}.hex"
        if hex_path.is_file():
            found.append(
                HexAsset(label=label, path=hex_path, role=_role_for_label(label))
            )
        else:
            missing.append(label)

    if missing:
        raise AssetDiscoveryError(
            f"Missing ztest hex files in {asset_set_dir} for labels: "
            f"{', '.join(missing)}"
        )

    return found


# ──────────────────────────────────────────────────────────────────────
# HTTP reporter
# ──────────────────────────────────────────────────────────────────────


class _HttpSessionLike(Protocol):
    def post(self, url, *, json=None, headers=None, timeout=None): ...


class ZTestReporter:
    """POSTs ztest results to the Concord HTTP API.

    Wire shape matches the pytest reporter — same
    ``/v2/runs/<id>/report/{execution-start,execution-result,finish}``
    endpoints, same body fields, same auth scheme. The backend doesn't
    need to know which framework produced the payloads.

    Parameters
    ----------
    run_id, target_id, api_url, api_key
        The standard Concord runner envelope.
    session
        ``requests.Session``-shaped object. Defaults to a real session;
        unit tests inject a recorder.
    enabled
        When ``False`` every POST is silently dropped — useful for
        ``dry_run_http`` mode and for tests that build the reporter
        without wanting I/O.
    """

    def __init__(
        self,
        *,
        run_id: str,
        target_id: str,
        api_url: str,
        api_key: Optional[str] = None,
        session: Optional[_HttpSessionLike] = None,
        enabled: bool = True,
        timeout_s: float = 10.0,
    ) -> None:
        self.run_id = run_id
        self.target_id = target_id
        self.api_url = (api_url or "").rstrip("/")
        self.api_key = api_key
        self.enabled = enabled
        self.timeout_s = timeout_s
        if session is not None:
            self._session = session
        else:
            try:
                import requests  # type: ignore

                self._session = requests.Session()
            except ImportError:
                logger.warning(
                    "requests not installed — ZTestReporter disabled"
                )
                self.enabled = False
                self._session = None  # type: ignore

    # ── internal ──

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"ApiKey {self.api_key}"
        return h

    def _post(self, endpoint: str, body: dict) -> None:
        if not self.enabled or self._session is None:
            return
        url = f"{self.api_url}/v2/runs/{self.run_id}/{endpoint}"
        try:
            self._session.post(
                url,
                json=body,
                headers=self._headers(),
                timeout=self.timeout_s,
            )
        except Exception as exc:  # pragma: no cover — network errors logged
            logger.warning("ZTestReporter POST %s failed: %s", url, exc)

    # ── public API ──

    def report_execution_start(self, *, name: str, module: Optional[str]) -> None:
        self._post(
            "report/execution-start",
            {
                "testName": name,
                "module": module,
                "targetId": self.target_id,
            },
        )

    def report_execution_result(
        self,
        *,
        name: str,
        passed: bool,
        duration_s: float,
        error_message: Optional[str],
        skipped: bool = False,
        module: Optional[str] = None,
    ) -> None:
        self._post(
            "report/execution-result",
            {
                "testName": name,
                "module": module,
                "targetId": self.target_id,
                "passed": passed,
                "skipped": skipped,
                "durationS": duration_s,
                "errorMessage": error_message,
            },
        )

    def report_finish(self, *, passed: bool, total: int, failed: int) -> None:
        self._post(
            "report/finish",
            {
                "passed": passed,
                "total": total,
                "failed": failed,
            },
        )

    def heartbeat(self) -> None:
        """Periodic ping so the scheduler's stale-runner reaper sees life.

        Uses the same ``report/log-chunk`` endpoint the pytest reporter
        uses — an empty-payload POST is enough; the backend stamps
        ``runnerLastHeartbeat`` on every report endpoint it serves.
        """
        self._post(
            "report/log-chunk",
            {
                "targetId": self.target_id,
                "chunk": "",
            },
        )

    def publish_summary(self, summary: ZTestSummary) -> None:
        """Emit one execution-start + one execution-result per test
        across all suites, then a single ``report/finish``."""
        for suite in summary.suites:
            for r in suite.results:
                qualified = f"{suite.name}.{r.name}"
                self.report_execution_start(name=qualified, module=suite.name)
                self.report_execution_result(
                    name=qualified,
                    module=suite.name,
                    passed=r.passed,
                    skipped=r.skipped,
                    duration_s=r.duration_s,
                    error_message=None if r.passed or r.skipped else "ztest reported FAIL",
                )
        self.report_finish(
            passed=summary.project_succeeded and summary.total_failed == 0,
            total=summary.total,
            failed=summary.total_failed,
        )


# ──────────────────────────────────────────────────────────────────────
# Dry-run / print-only reporter (used by replay mode + --dry-run-http)
# ──────────────────────────────────────────────────────────────────────


class _DryRunSession:
    """Stand-in for ``requests.Session`` that prints what would be POSTed.

    Returns a 200-OK shaped object so callers behave identically to a
    real session. Intended for local-iteration only.
    """

    def post(self, url, *, json=None, headers=None, timeout=None):
        body = json or {}
        print(f"[dry-run] POST {url}")
        for k, v in body.items():
            print(f"    {k}: {v}")
        return _OkResponse()


class _OkResponse:
    status_code = 200
    ok = True

    def json(self):
        return {"ok": True}


# ──────────────────────────────────────────────────────────────────────
# MTIB client seam
# ──────────────────────────────────────────────────────────────────────


class MtibClientLike(Protocol):
    """The slice of the MTIB client surface that the ztest runner needs.

    Production wires :class:`MtibV1Adapter` around the real
    :class:`MtibV1Client`. Tests pass any object satisfying this
    Protocol — a recorded fixture, a mock, …
    """

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def flash_hex(self, path: str, role: str) -> None: ...
    def stream_uart(self, role: str, timeout_s: float) -> Iterable[str]: ...


def make_default_mtib_client(host: str, port: int) -> MtibClientLike:
    """Build the production MTIB adapter.

    Imports are deferred so unit tests that never call this don't pay the
    gRPC import cost (and don't crash on systems without protobuf
    installed).
    """
    from corekinect.mtib_client.v1.client.core import MtibV1Client
    from corekinect.mtib_client.v1.client.config import NetConfig

    config = MtibV1Client.Config(net=NetConfig(addr=host, port=port))
    inner = MtibV1Client(config)
    return MtibV1Adapter(inner)


class MtibV1Adapter:
    """Adapter that exposes the small ztest-runner surface on top of
    :class:`MtibV1Client`. Keeps the runner code free of protobuf and
    role-to-HostType plumbing.
    """

    _ROLE_TO_TARGET = {
        "app": "nrf52840",
        "comms": "nrf9151",
        "modem": "nrf9151_modem",
    }

    def __init__(self, inner):
        self._inner = inner

    def connect(self) -> None:
        err = self._inner.connect()
        if err:
            raise RuntimeError(f"MTIB connect failed: {err}")

    def disconnect(self) -> None:
        try:
            self._inner.disconnect()
        except Exception:
            # Cleanup is best-effort.
            pass

    def flash_hex(self, path: str, role: str) -> None:
        from protocols.mtib.mtib_pb2 import FwFileInfo, HostType  # type: ignore

        target_str = self._ROLE_TO_TARGET.get(role)
        if target_str is None:
            raise ValueError(f"Unknown role {role!r}")
        host_type_map = {
            "nrf52840": HostType.HOST_TYPE_NRF52840,
            "nrf9151": HostType.HOST_TYPE_NRF9151,
            "nrf9151_modem": HostType.HOST_TYPE_NRF9151_MODEM,
        }
        host_type = host_type_map[target_str]

        upload_err = self._inner.UploadFwFile(path, host_type)
        if upload_err:
            raise RuntimeError(f"MTIB upload failed: {upload_err}")

        file_info = FwFileInfo(name=os.path.basename(path), target=host_type)
        _, flash_err = self._inner.FlashFwFile(
            file_info, sector_erase=True, recover=False
        )
        if flash_err:
            raise RuntimeError(f"MTIB flash failed: {flash_err}")

    def stream_uart(self, role: str, timeout_s: float) -> Iterator[str]:
        """Stream UART text chunks from the given processor for up to
        ``timeout_s`` seconds. Stops early when the ztest
        ``PROJECT EXECUTION`` marker is observed."""
        from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest  # type: ignore

        target_str = self._ROLE_TO_TARGET.get(role, "app")
        host_type = {
            "nrf52840": HostType.HOST_TYPE_NRF52840,
            "nrf9151": HostType.HOST_TYPE_NRF9151,
            "nrf9151_modem": HostType.HOST_TYPE_NRF9151_MODEM,
        }[target_str]

        deadline = time.monotonic() + timeout_s
        stop = threading.Event()

        def request_gen():
            while not stop.is_set() and time.monotonic() < deadline:
                yield UartStreamRequest(target=host_type, data=b"")
                time.sleep(0.05)

        seen = ""
        try:
            for resp in self._inner.UartStream(host_type, request_gen()):
                if resp.data:
                    chunk = resp.data.decode("utf-8", errors="replace")
                    seen += chunk
                    yield chunk
                    if "PROJECT EXECUTION" in seen:
                        stop.set()
                        return
                if time.monotonic() >= deadline:
                    return
        finally:
            stop.set()


# ──────────────────────────────────────────────────────────────────────
# Replay
# ──────────────────────────────────────────────────────────────────────


def replay_uart_log(
    log_path: Path,
    *,
    run_id: str,
    target_id: str,
    api_url: str,
    api_key: Optional[str],
    dry_run_http: bool = False,
    session: Optional[_HttpSessionLike] = None,
) -> ExitCode:
    """Parse a captured UART log and publish results.

    Used for local debugging without hardware. Returns the same exit
    code semantics as :func:`run`.
    """
    log_path = Path(log_path)
    if not log_path.is_file():
        logger.error("Replay log not found: %s", log_path)
        return ExitCode.INFRA_ERROR

    text = log_path.read_text(errors="replace")
    try:
        summary = parse_ztest_output(text)
    except ZTestParseError as exc:
        logger.error("Replay parse failed: %s", exc)
        return ExitCode.INFRA_ERROR

    if dry_run_http:
        reporter_session: _HttpSessionLike = _DryRunSession()
    elif session is not None:
        reporter_session = session
    else:
        reporter_session = None  # type: ignore — ZTestReporter builds default

    reporter = ZTestReporter(
        run_id=run_id,
        target_id=target_id,
        api_url=api_url,
        api_key=api_key,
        session=reporter_session if reporter_session is not None else None,
    )
    reporter.publish_summary(summary)
    return summary.exit_code


# ──────────────────────────────────────────────────────────────────────
# run() — production entry point
# ──────────────────────────────────────────────────────────────────────


def run(
    *,
    run_id: str,
    target_id: str,
    asset_set_dir: Path,
    api_url: str,
    api_key: Optional[str],
    labels: Sequence[str],
    timeout_s: float = DEFAULT_TIMEOUT_S,
    mtib_factory: Optional[Callable[[], MtibClientLike]] = None,
    session: Optional[_HttpSessionLike] = None,
    heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
) -> ExitCode:
    """Run a ztest hex on the connected fixture and publish results.

    Parameters mirror the CLI flags. ``mtib_factory`` and ``session`` are
    seams for tests; production callers leave them ``None`` and the
    function builds real instances.
    """
    asset_set_dir = Path(asset_set_dir)

    # ── 1. Discover hexes ──
    try:
        hexes = discover_hex_files(asset_set_dir, labels=labels)
    except AssetDiscoveryError as exc:
        logger.error("Asset discovery failed: %s", exc)
        return ExitCode.INFRA_ERROR

    # ── 2. Build MTIB client ──
    if mtib_factory is None:
        # In production we need host/port — caller-side responsibility to
        # pass mtib_factory here; the CLI path always does. This branch is
        # a defensive default that immediately errors so a misconfigured
        # call doesn't silently skip the flash step.
        logger.error("run() requires mtib_factory= when no MTIB is wired by the caller")
        return ExitCode.INFRA_ERROR

    mtib = mtib_factory()
    try:
        mtib.connect()
    except Exception as exc:
        logger.error("MTIB connect failed: %s", exc)
        return ExitCode.INFRA_ERROR

    # ── 3. Build reporter (real or replay-style) ──
    reporter = ZTestReporter(
        run_id=run_id,
        target_id=target_id,
        api_url=api_url,
        api_key=api_key,
        session=session,
    )

    # ── 4. Background heartbeat ──
    stop_hb = threading.Event()

    def _hb_loop():
        while not stop_hb.wait(heartbeat_interval_s):
            try:
                reporter.heartbeat()
            except Exception:
                pass

    hb_thread = threading.Thread(target=_hb_loop, daemon=True, name="ztest-heartbeat")
    hb_thread.start()

    try:
        # ── 5. Flash each hex ──
        primary_role = "app"
        for h in hexes:
            try:
                mtib.flash_hex(str(h.path), h.role)
            except Exception as exc:
                logger.error("Flash failed for %s: %s", h.path, exc)
                return ExitCode.INFRA_ERROR
            # The role we'll subscribe UART on is the role of the *first*
            # flashed hex; multi-processor ztest captures cross-stream
            # routing aren't supported in this initial drop. Document.
            if h is hexes[0]:
                primary_role = h.role

        # ── 6. Stream UART until ztest finishes or timeout ──
        captured = ""
        try:
            for chunk in mtib.stream_uart(primary_role, timeout_s=timeout_s):
                captured += chunk
        except Exception as exc:
            logger.error("UART stream failed: %s", exc)
            return ExitCode.INFRA_ERROR

        # ── 7. Parse ──
        try:
            summary = parse_ztest_output(captured)
        except ZTestParseError as exc:
            logger.error("ztest output parse failed: %s", exc)
            return ExitCode.INFRA_ERROR

        # ── 8. Publish + exit ──
        reporter.publish_summary(summary)
        return summary.exit_code

    finally:
        stop_hb.set()
        try:
            mtib.disconnect()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


def parse_cli_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="corekinect.test.ztest_runner",
        description="Concord ztest runner — flashes a ztest hex via MTIB, "
        "captures UART, parses results, and POSTs them to the http-api.",
    )
    p.add_argument("--run-id", required=True, help="Concord TestRun id")
    p.add_argument("--target-id", required=True, help="Concord RunTarget id")
    p.add_argument("--api-url", required=True, help="Concord http-api base URL")
    p.add_argument("--api-key", required=True, help="API key for reporter auth")

    # Production-mode args
    p.add_argument("--asset-set", default=None, help="Directory holding ztest .hex files")
    p.add_argument("--mtib-host", default=None, help="MTIB gRPC host")
    p.add_argument("--mtib-port", type=int, default=DEFAULT_MTIB_PORT, help="MTIB gRPC port")
    p.add_argument(
        "--labels",
        default="",
        help="Comma-separated list of hex labels to flash "
        "(e.g. 'smoke_app_ztest,smoke_comms_ztest')",
    )
    p.add_argument(
        "--timeout-s",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help="UART capture timeout in seconds",
    )

    # Replay / dry-run flags
    p.add_argument(
        "--replay-uart",
        default=None,
        help="Path to a captured UART log file to replay instead of "
        "talking to hardware",
    )
    p.add_argument(
        "--dry-run-http",
        action="store_true",
        help="Print HTTP payloads to stdout instead of POSTing them",
    )

    args = p.parse_args(argv)
    args.labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_cli_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.replay_uart:
        exit_code = replay_uart_log(
            Path(args.replay_uart),
            run_id=args.run_id,
            target_id=args.target_id,
            api_url=args.api_url,
            api_key=args.api_key,
            dry_run_http=args.dry_run_http,
        )
        return int(exit_code)

    # Live path
    if not args.asset_set:
        logger.error("--asset-set is required unless --replay-uart is used")
        return int(ExitCode.INFRA_ERROR)
    if not args.mtib_host:
        logger.error("--mtib-host is required unless --replay-uart is used")
        return int(ExitCode.INFRA_ERROR)
    if not args.labels:
        logger.error("--labels is required (comma-separated)")
        return int(ExitCode.INFRA_ERROR)

    mtib_factory = (
        None
        if args.dry_run_http and not args.mtib_host
        else (lambda: make_default_mtib_client(args.mtib_host, args.mtib_port))
    )

    session = _DryRunSession() if args.dry_run_http else None

    exit_code = run(
        run_id=args.run_id,
        target_id=args.target_id,
        asset_set_dir=Path(args.asset_set),
        api_url=args.api_url,
        api_key=args.api_key,
        labels=args.labels,
        timeout_s=args.timeout_s,
        mtib_factory=mtib_factory,
        session=session,
    )
    return int(exit_code)


if __name__ == "__main__":  # pragma: no cover — CLI smoke
    sys.exit(main())
