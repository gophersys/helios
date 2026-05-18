"""Tests for the ztest runner.

Covers:

* ``parse_ztest_output`` — defensive parsing of Zephyr ztest UART output.
* ``discover_hex_files`` — locating ztest hex artifacts in an asset_set.
* ``ZTestReporter`` — HTTP POST shape (mocked at ``requests`` boundary).
* ``parse_cli_args`` — CLI argument parsing.
* End-to-end replay: feeding a captured ztest log through the pipeline.

The MTIB gRPC client and the ``requests`` HTTP client are the only
external boundaries that aren't real here — both are abstracted via
``MtibClientLike`` / a ``session=`` injection point so production
wires the real implementation and tests wire a recorded fixture.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.ztest_runner import (
    DEFAULT_TIMEOUT_S,
    AssetDiscoveryError,
    ExitCode,
    HexAsset,
    Outcome,
    ZTestParseError,
    ZTestReporter,
    ZTestResult,
    ZTestSummary,
    discover_hex_files,
    parse_cli_args,
    parse_ztest_output,
    replay_uart_log,
    run,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


class TestParseZTestOutput:
    def test_parses_simple_suite_all_pass(self):
        out = (
            "Running TESTSUITE smoke\n"
            "START - test_one\n"
            " PASS - test_one in 0.001 seconds\n"
            "START - test_two\n"
            " PASS - test_two in 0.002 seconds\n"
            "TESTSUITE smoke succeeded\n"
            "PROJECT EXECUTION SUCCESSFUL\n"
        )
        summary = parse_ztest_output(out)
        assert len(summary.suites) == 1
        suite = summary.suites[0]
        assert suite.name == "smoke"
        assert suite.passed == 2
        assert suite.failed == 0
        assert suite.skipped == 0
        assert suite.succeeded is True
        assert summary.project_succeeded is True
        assert summary.exit_code == ExitCode.SUCCESS

    def test_parses_fail_skip_and_pass(self):
        out = (
            "Running TESTSUITE driver\n"
            " PASS - test_init in 0.010 seconds\n"
            " FAIL - test_read in 0.020 seconds\n"
            " SKIP - test_write in 0.000 seconds\n"
            "TESTSUITE driver failed\n"
            "PROJECT EXECUTION FAILED\n"
        )
        summary = parse_ztest_output(out)
        suite = summary.suites[0]
        assert suite.passed == 1
        assert suite.failed == 1
        assert suite.skipped == 1
        assert suite.succeeded is False
        assert summary.project_succeeded is False
        assert summary.exit_code == ExitCode.TEST_FAILURE

        by_name = {r.name: r for r in suite.results}
        assert by_name["test_init"].outcome == Outcome.PASS
        assert by_name["test_read"].outcome == Outcome.FAIL
        assert by_name["test_write"].outcome == Outcome.SKIP

    def test_records_durations_in_seconds(self):
        out = (
            "Running TESTSUITE x\n"
            " PASS - quick in 0.001 seconds\n"
            " PASS - slow in 1.234 seconds\n"
            "TESTSUITE x succeeded\n"
            "PROJECT EXECUTION SUCCESSFUL\n"
        )
        summary = parse_ztest_output(out)
        by_name = {r.name: r for r in summary.suites[0].results}
        assert by_name["quick"].duration_s == pytest.approx(0.001)
        assert by_name["slow"].duration_s == pytest.approx(1.234)

    def test_ignores_zephyr_log_noise(self):
        out = (
            "[00:00:01.234,000] <inf> app: ready\n"
            "*** Booting Zephyr OS build v3.6 ***\n"
            "Running TESTSUITE smoke\n"
            "[00:00:01.500,000] <wrn> driver: something\n"
            " PASS - test_one in 0.001 seconds\n"
            "uart_async: tx flush\n"
            "TESTSUITE smoke succeeded\n"
            "PROJECT EXECUTION SUCCESSFUL\n"
        )
        summary = parse_ztest_output(out)
        assert summary.suites[0].passed == 1
        assert len(summary.suites[0].results) == 1

    def test_parses_multiple_suites(self):
        out = (
            "Running TESTSUITE alpha\n"
            " PASS - test_a in 0.001 seconds\n"
            "TESTSUITE alpha succeeded\n"
            "Running TESTSUITE beta\n"
            " FAIL - test_b in 0.002 seconds\n"
            "TESTSUITE beta failed\n"
            "PROJECT EXECUTION FAILED\n"
        )
        summary = parse_ztest_output(out)
        assert len(summary.suites) == 2
        assert summary.suites[0].name == "alpha"
        assert summary.suites[0].succeeded is True
        assert summary.suites[1].name == "beta"
        assert summary.suites[1].succeeded is False
        assert summary.total_failed == 1
        assert summary.total_passed == 1

    def test_missing_running_header_raises(self):
        out = " PASS - test_one in 0.001 seconds\n"
        with pytest.raises(ZTestParseError) as exc:
            parse_ztest_output(out)
        assert "TESTSUITE" in str(exc.value)

    def test_empty_output_raises(self):
        with pytest.raises(ZTestParseError):
            parse_ztest_output("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ZTestParseError):
            parse_ztest_output("   \n  \n")

    def test_project_succeeded_inferred_from_suites_when_marker_missing(self):
        """Captures sometimes drop the final PROJECT EXECUTION line because
        the device reset or UART closed. We infer success/failure from the
        suite outcomes rather than calling it indeterminate."""
        out = (
            "Running TESTSUITE smoke\n"
            " PASS - test_one in 0.001 seconds\n"
            "TESTSUITE smoke succeeded\n"
        )
        summary = parse_ztest_output(out)
        assert summary.project_succeeded is True
        assert summary.exit_code == ExitCode.SUCCESS

    def test_project_inferred_failed_when_suite_failed_and_marker_missing(self):
        out = (
            "Running TESTSUITE driver\n"
            " FAIL - test_one in 0.001 seconds\n"
            "TESTSUITE driver failed\n"
        )
        summary = parse_ztest_output(out)
        assert summary.project_succeeded is False

    def test_variable_whitespace_on_result_lines(self):
        """ztest sometimes emits ``  PASS - ...`` (2 spaces) or just ``PASS - ...``;
        the parser must tolerate both."""
        out = (
            "Running TESTSUITE x\n"
            "PASS - a in 0.001 seconds\n"
            "  PASS - b in 0.002 seconds\n"
            "\tPASS - c in 0.003 seconds\n"
            "TESTSUITE x succeeded\n"
            "PROJECT EXECUTION SUCCESSFUL\n"
        )
        summary = parse_ztest_output(out)
        assert summary.suites[0].passed == 3

    def test_parses_captured_pass_fixture(self):
        text = (FIXTURES_DIR / "sample_ztest_pass.txt").read_text()
        summary = parse_ztest_output(text)
        assert summary.suites[0].name == "lsm6dso_smoke"
        assert summary.suites[0].passed == 3
        assert summary.suites[0].failed == 0
        assert summary.project_succeeded is True

    def test_parses_captured_mixed_fixture(self):
        text = (FIXTURES_DIR / "sample_ztest_mixed.txt").read_text()
        summary = parse_ztest_output(text)
        assert len(summary.suites) == 2
        assert summary.total_passed == 2
        assert summary.total_failed == 1
        assert summary.total_skipped == 1
        assert summary.project_succeeded is False


class TestZTestResult:
    def test_outcome_enum_values(self):
        assert Outcome.PASS.value == "PASS"
        assert Outcome.FAIL.value == "FAIL"
        assert Outcome.SKIP.value == "SKIP"

    def test_result_passed_property(self):
        r = ZTestResult(name="x", outcome=Outcome.PASS, duration_s=0.1)
        assert r.passed is True
        assert r.failed is False
        assert r.skipped is False

    def test_result_failed_property(self):
        r = ZTestResult(name="x", outcome=Outcome.FAIL, duration_s=0.1)
        assert r.failed is True
        assert r.passed is False

    def test_result_skipped_property(self):
        r = ZTestResult(name="x", outcome=Outcome.SKIP, duration_s=0.0)
        assert r.skipped is True


class TestZTestSummary:
    def test_exit_code_success(self):
        s = ZTestSummary(suites=[], project_succeeded=True)
        assert s.exit_code == ExitCode.SUCCESS

    def test_exit_code_test_failure(self):
        s = ZTestSummary(suites=[], project_succeeded=False)
        assert s.exit_code == ExitCode.TEST_FAILURE

    def test_total_counts(self):
        from corekinect.test.ztest_runner import ZTestSuite

        s = ZTestSummary(
            suites=[
                ZTestSuite(
                    name="a",
                    results=[
                        ZTestResult(name="t1", outcome=Outcome.PASS, duration_s=0.1),
                        ZTestResult(name="t2", outcome=Outcome.FAIL, duration_s=0.2),
                    ],
                    succeeded=False,
                ),
                ZTestSuite(
                    name="b",
                    results=[
                        ZTestResult(name="t3", outcome=Outcome.SKIP, duration_s=0.0),
                    ],
                    succeeded=True,
                ),
            ],
            project_succeeded=False,
        )
        assert s.total_passed == 1
        assert s.total_failed == 1
        assert s.total_skipped == 1
        assert s.total == 3


# ──────────────────────────────────────────────────────────────────────
# AssetSet discovery
# ──────────────────────────────────────────────────────────────────────


class TestDiscoverHexFiles:
    def test_finds_labelled_hex_files(self, tmp_path):
        (tmp_path / "smoke_app_ztest.hex").write_text(":00000001FF\n")
        (tmp_path / "smoke_comms_ztest.hex").write_text(":00000001FF\n")
        (tmp_path / "irrelevant.bin").write_bytes(b"\x00")

        hexes = discover_hex_files(tmp_path, labels=["smoke_app_ztest", "smoke_comms_ztest"])
        assert len(hexes) == 2
        names = {h.label for h in hexes}
        assert names == {"smoke_app_ztest", "smoke_comms_ztest"}

    def test_returns_hex_asset_with_path(self, tmp_path):
        hex_path = tmp_path / "smoke_app_ztest.hex"
        hex_path.write_text(":00000001FF\n")
        hexes = discover_hex_files(tmp_path, labels=["smoke_app_ztest"])
        assert isinstance(hexes[0], HexAsset)
        assert hexes[0].path == hex_path
        assert hexes[0].label == "smoke_app_ztest"

    def test_raises_when_label_missing(self, tmp_path):
        (tmp_path / "smoke_app_ztest.hex").write_text(":00000001FF\n")
        with pytest.raises(AssetDiscoveryError) as exc:
            discover_hex_files(tmp_path, labels=["smoke_app_ztest", "nonexistent_ztest"])
        assert "nonexistent_ztest" in str(exc.value)

    def test_raises_on_missing_directory(self):
        with pytest.raises(AssetDiscoveryError):
            discover_hex_files(Path("/nonexistent/path/xyz"), labels=["a"])

    def test_target_inferred_from_label(self, tmp_path):
        """Labels follow the ``<stage>_<role>_ztest`` convention; the role
        is what tells us which processor to flash."""
        for n in ("smoke_app_ztest.hex", "smoke_comms_ztest.hex"):
            (tmp_path / n).write_text(":00000001FF\n")
        hexes = discover_hex_files(tmp_path, labels=["smoke_app_ztest", "smoke_comms_ztest"])
        by_role = {h.role: h for h in hexes}
        assert by_role["app"].label == "smoke_app_ztest"
        assert by_role["comms"].label == "smoke_comms_ztest"

    def test_label_without_underscore_role_defaults_to_app(self, tmp_path):
        """Plain ``ztest.hex`` (single processor) is permitted; role is
        defaulted to 'app'."""
        (tmp_path / "ztest.hex").write_text(":00000001FF\n")
        hexes = discover_hex_files(tmp_path, labels=["ztest"])
        assert hexes[0].role == "app"


# ──────────────────────────────────────────────────────────────────────
# HTTP reporter (mocked at requests boundary)
# ──────────────────────────────────────────────────────────────────────


class _RecordingSession:
    """Minimal ``requests.Session`` stand-in.

    Records every POST so tests can assert URL + JSON body shape.
    """

    def __init__(self):
        self.posts: List[dict] = []

    def post(self, url, *, json=None, headers=None, timeout=None):
        self.posts.append({
            "url": url,
            "json": json,
            "headers": headers or {},
            "timeout": timeout,
        })
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = {"ok": True}
        return resp


class TestZTestReporter:
    def test_report_execution_start_shape(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.report_execution_start(name="lsm6dso.test_chip_id", module="lsm6dso")
        assert len(sess.posts) == 1
        post = sess.posts[0]
        assert post["url"].endswith("/v2/runs/run-1/report/execution-start")
        assert post["headers"]["Authorization"] == "ApiKey key"
        assert post["json"]["testName"] == "lsm6dso.test_chip_id"
        assert post["json"]["module"] == "lsm6dso"
        assert post["json"]["targetId"] == "tgt-1"

    def test_report_execution_result_pass(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.report_execution_result(
            name="lsm6dso.test_chip_id",
            passed=True,
            duration_s=0.012,
            error_message=None,
        )
        post = sess.posts[0]
        assert post["url"].endswith("/v2/runs/run-1/report/execution-result")
        assert post["json"]["testName"] == "lsm6dso.test_chip_id"
        assert post["json"]["passed"] is True
        assert post["json"]["skipped"] is False
        assert post["json"]["durationS"] == pytest.approx(0.012)
        assert post["json"]["errorMessage"] is None

    def test_report_execution_result_fail_with_error(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.report_execution_result(
            name="lsm6dso.test_read",
            passed=False,
            duration_s=0.122,
            error_message="register mismatch",
        )
        post = sess.posts[0]
        assert post["json"]["passed"] is False
        assert post["json"]["errorMessage"] == "register mismatch"

    def test_report_execution_result_skip(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.report_execution_result(
            name="lsm6dso.test_int",
            passed=False,
            duration_s=0.0,
            error_message=None,
            skipped=True,
        )
        post = sess.posts[0]
        assert post["json"]["skipped"] is True
        assert post["json"]["passed"] is False

    def test_report_run_finish(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.report_finish(passed=True, total=3, failed=0)
        post = sess.posts[0]
        assert post["url"].endswith("/v2/runs/run-1/report/finish")
        assert post["json"]["passed"] is True
        assert post["json"]["total"] == 3
        assert post["json"]["failed"] == 0

    def test_heartbeat_posts_to_correct_endpoint(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        r.heartbeat()
        post = sess.posts[0]
        # Validation runs heartbeat via the same /report/log-chunk shape
        # the pytest runner uses — a no-op POST with the run id is
        # enough to keep the scheduler's stale-runner reaper happy.
        assert "run-1" in post["url"]

    def test_publish_summary_emits_one_post_per_test(self):
        from corekinect.test.ztest_runner import ZTestSuite

        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
        )
        summary = ZTestSummary(
            suites=[
                ZTestSuite(
                    name="smoke",
                    results=[
                        ZTestResult(name="test_a", outcome=Outcome.PASS, duration_s=0.01),
                        ZTestResult(name="test_b", outcome=Outcome.FAIL, duration_s=0.02),
                        ZTestResult(name="test_c", outcome=Outcome.SKIP, duration_s=0.0),
                    ],
                    succeeded=False,
                ),
            ],
            project_succeeded=False,
        )
        r.publish_summary(summary)
        # 3 execution-start + 3 execution-result + 1 finish = 7 POSTs
        assert len(sess.posts) == 7
        urls = [p["url"] for p in sess.posts]
        assert sum(1 for u in urls if "execution-start" in u) == 3
        assert sum(1 for u in urls if "execution-result" in u) == 3
        assert sum(1 for u in urls if "/finish" in u) == 1

    def test_disabled_reporter_silently_drops(self):
        sess = _RecordingSession()
        r = ZTestReporter(
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            session=sess,
            enabled=False,
        )
        r.report_execution_start(name="x", module=None)
        r.report_execution_result(name="x", passed=True, duration_s=0.1, error_message=None)
        r.report_finish(passed=True, total=1, failed=0)
        assert sess.posts == []


# ──────────────────────────────────────────────────────────────────────
# CLI arg parsing
# ──────────────────────────────────────────────────────────────────────


class TestParseCliArgs:
    def test_required_args(self):
        args = parse_cli_args([
            "--run-id", "run-1",
            "--target-id", "tgt-1",
            "--asset-set", "/tmp/assets",
            "--api-url", "http://api.local",
            "--api-key", "abc",
            "--mtib-host", "10.0.0.1",
            "--labels", "smoke_app_ztest,smoke_comms_ztest",
        ])
        assert args.run_id == "run-1"
        assert args.target_id == "tgt-1"
        assert args.asset_set == "/tmp/assets"
        assert args.api_url == "http://api.local"
        assert args.api_key == "abc"
        assert args.mtib_host == "10.0.0.1"
        assert args.labels == ["smoke_app_ztest", "smoke_comms_ztest"]

    def test_default_mtib_port(self):
        args = parse_cli_args([
            "--run-id", "r",
            "--target-id", "t",
            "--asset-set", "/x",
            "--api-url", "http://a",
            "--api-key", "k",
            "--mtib-host", "h",
            "--labels", "l",
        ])
        assert args.mtib_port == 50053

    def test_override_mtib_port(self):
        args = parse_cli_args([
            "--run-id", "r",
            "--target-id", "t",
            "--asset-set", "/x",
            "--api-url", "http://a",
            "--api-key", "k",
            "--mtib-host", "h",
            "--mtib-port", "60000",
            "--labels", "l",
        ])
        assert args.mtib_port == 60000

    def test_default_timeout(self):
        args = parse_cli_args([
            "--run-id", "r",
            "--target-id", "t",
            "--asset-set", "/x",
            "--api-url", "http://a",
            "--api-key", "k",
            "--mtib-host", "h",
            "--labels", "l",
        ])
        assert args.timeout_s == DEFAULT_TIMEOUT_S

    def test_replay_uart_mode(self):
        args = parse_cli_args([
            "--replay-uart", "/path/to/log.txt",
            "--run-id", "r",
            "--target-id", "t",
            "--api-url", "http://a",
            "--api-key", "k",
            "--dry-run-http",
        ])
        assert args.replay_uart == "/path/to/log.txt"
        assert args.dry_run_http is True

    def test_replay_mode_does_not_require_asset_set_or_mtib(self):
        """Replay reads from a file and skips MTIB entirely. The CLI
        parser must reflect that — otherwise local debugging is gated on
        having a fixture in front of you."""
        args = parse_cli_args([
            "--replay-uart", "/x",
            "--run-id", "r",
            "--target-id", "t",
            "--api-url", "http://a",
            "--api-key", "k",
        ])
        assert args.asset_set is None
        assert args.mtib_host is None


# ──────────────────────────────────────────────────────────────────────
# End-to-end replay
# ──────────────────────────────────────────────────────────────────────


class TestReplayUartLog:
    def test_replay_with_dry_run_http(self, tmp_path, capsys):
        """Replay reads a captured UART log, parses it, and prints what
        it WOULD POST instead of sending. Used for local debugging."""
        log_file = FIXTURES_DIR / "sample_ztest_pass.txt"
        exit_code = replay_uart_log(
            log_file,
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            dry_run_http=True,
        )
        assert exit_code == ExitCode.SUCCESS
        captured = capsys.readouterr().out
        # Dry-run prints each payload that would be sent — at minimum
        # the test names should appear in the printed output.
        assert "test_chip_id" in captured
        assert "test_xl_init" in captured
        assert "test_gyro_init" in captured

    def test_replay_returns_failure_for_failed_fixture(self):
        log_file = FIXTURES_DIR / "sample_ztest_mixed.txt"
        exit_code = replay_uart_log(
            log_file,
            run_id="run-1",
            target_id="tgt-1",
            api_url="http://api.local",
            api_key="key",
            dry_run_http=True,
        )
        assert exit_code == ExitCode.TEST_FAILURE


# ──────────────────────────────────────────────────────────────────────
# run() — the production entry point
# ──────────────────────────────────────────────────────────────────────


class _FakeMtibClient:
    """In-memory MtibClientLike.

    Wired into ``run()`` via the ``mtib_factory=`` seam so hardware-free
    tests can drive the full pipeline. Production wires the real
    ``MtibV1Client``.
    """

    def __init__(self, *, uart_output: str = ""):
        self.uart_output = uart_output
        self.connect_called = False
        self.flashed: List[str] = []
        self.disconnected = False

    def connect(self) -> None:
        self.connect_called = True

    def disconnect(self) -> None:
        self.disconnected = True

    def flash_hex(self, path: str, role: str) -> None:
        self.flashed.append(f"{role}:{path}")

    def stream_uart(self, role: str, timeout_s: float):
        """Yield UART chunks. Tests pre-load ``self.uart_output``."""
        # Emit the buffer as one chunk so the parser sees the whole log.
        yield self.uart_output


class TestRunIntegration:
    def test_run_happy_path_with_fake_mtib(self, tmp_path):
        """End-to-end: discover hex, flash via fake MTIB, parse UART
        output, POST results via mocked session, return SUCCESS."""
        (tmp_path / "smoke_app_ztest.hex").write_text(":00000001FF\n")

        uart_text = (FIXTURES_DIR / "sample_ztest_pass.txt").read_text()
        fake_mtib = _FakeMtibClient(uart_output=uart_text)
        sess = _RecordingSession()

        exit_code = run(
            run_id="run-1",
            target_id="tgt-1",
            asset_set_dir=tmp_path,
            api_url="http://api.local",
            api_key="key",
            labels=["smoke_app_ztest"],
            timeout_s=30,
            mtib_factory=lambda: fake_mtib,
            session=sess,
        )

        assert exit_code == ExitCode.SUCCESS
        assert fake_mtib.connect_called is True
        assert fake_mtib.disconnected is True
        # one flash for the single label
        assert len(fake_mtib.flashed) == 1
        assert "smoke_app_ztest.hex" in fake_mtib.flashed[0]
        # POSTs were made
        urls = [p["url"] for p in sess.posts]
        assert any("execution-result" in u for u in urls)
        assert any("/finish" in u for u in urls)

    def test_run_returns_test_failure_when_tests_fail(self, tmp_path):
        (tmp_path / "driver_app_ztest.hex").write_text(":00000001FF\n")
        uart_text = (FIXTURES_DIR / "sample_ztest_mixed.txt").read_text()
        fake_mtib = _FakeMtibClient(uart_output=uart_text)
        sess = _RecordingSession()

        exit_code = run(
            run_id="run-1",
            target_id="tgt-1",
            asset_set_dir=tmp_path,
            api_url="http://api.local",
            api_key="key",
            labels=["driver_app_ztest"],
            timeout_s=30,
            mtib_factory=lambda: fake_mtib,
            session=sess,
        )
        assert exit_code == ExitCode.TEST_FAILURE

    def test_run_returns_infra_error_when_no_hex_found(self, tmp_path):
        """No matching hex in the asset_set → infra error, NOT silently zero."""
        fake_mtib = _FakeMtibClient(uart_output="")
        sess = _RecordingSession()

        exit_code = run(
            run_id="run-1",
            target_id="tgt-1",
            asset_set_dir=tmp_path,
            api_url="http://api.local",
            api_key="key",
            labels=["missing_label"],
            timeout_s=30,
            mtib_factory=lambda: fake_mtib,
            session=sess,
        )
        assert exit_code == ExitCode.INFRA_ERROR
        # MTIB was never asked to flash because discovery failed first.
        assert fake_mtib.flashed == []

    def test_run_returns_infra_error_on_unparseable_output(self, tmp_path):
        (tmp_path / "smoke_app_ztest.hex").write_text(":00000001FF\n")
        # Empty UART → parser raises, run() returns INFRA_ERROR.
        fake_mtib = _FakeMtibClient(uart_output="")
        sess = _RecordingSession()

        exit_code = run(
            run_id="run-1",
            target_id="tgt-1",
            asset_set_dir=tmp_path,
            api_url="http://api.local",
            api_key="key",
            labels=["smoke_app_ztest"],
            timeout_s=30,
            mtib_factory=lambda: fake_mtib,
            session=sess,
        )
        assert exit_code == ExitCode.INFRA_ERROR
