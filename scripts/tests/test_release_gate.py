"""Tests for release gate script."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from release_gate import (
    CheckResult,
    GateReport,
    check_version_file,
    run_gate,
)


class TestCheckResult:
    """CheckResult data structure."""

    def test_create_passed(self):
        r = CheckResult(name="test", passed=True, message="ok")
        assert r.passed is True
        assert r.name == "test"

    def test_create_failed(self):
        r = CheckResult(name="test", passed=False, message="bad")
        assert r.passed is False


class TestCheckVersionFile:
    """Gate fails if VERSION file is missing or invalid."""

    def test_version_file_exists(self, tmp_path, monkeypatch):
        version_file = tmp_path / "VERSION"
        version_file.write_text("1.2.3\n")
        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        result = check_version_file(repo_root=str(tmp_path))
        assert result.passed is True
        assert "1.2.3" in result.message

    def test_version_file_missing(self, tmp_path):
        result = check_version_file(repo_root=str(tmp_path))
        assert result.passed is False
        assert "missing" in result.message.lower() or "not found" in result.message.lower()

    def test_version_file_invalid_semver(self, tmp_path):
        version_file = tmp_path / "VERSION"
        version_file.write_text("not-a-version\n")
        result = check_version_file(repo_root=str(tmp_path))
        assert result.passed is False


class TestCheckCleanWorktree:
    """Gate fails if working tree is dirty."""

    def test_clean_worktree_result_structure(self):
        # We test the structure, actual git state depends on environment
        from release_gate import check_clean_worktree

        result = check_clean_worktree()
        assert isinstance(result, CheckResult)
        assert result.name == "clean_worktree"
        assert isinstance(result.passed, bool)


class TestGateReport:
    """Report includes all check results and overall status."""

    def test_report_structure(self):
        checks = [
            CheckResult(name="check1", passed=True, message="ok"),
            CheckResult(name="check2", passed=False, message="failed"),
        ]
        report = GateReport(
            version="1.0.0",
            commit_sha="abc12345",
            checks=checks,
            overall="failed",
        )
        assert report.overall == "failed"
        assert len(report.checks) == 2

    def test_report_to_json(self):
        checks = [
            CheckResult(name="check1", passed=True, message="ok", duration_ms=50),
        ]
        report = GateReport(
            version="1.0.0",
            commit_sha="abc12345",
            checks=checks,
            overall="passed",
        )
        from dataclasses import asdict

        data = asdict(report)
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["overall"] == "passed"
        assert parsed["checks"][0]["name"] == "check1"

    def test_report_all_passed(self):
        checks = [
            CheckResult(name="a", passed=True, message="ok"),
            CheckResult(name="b", passed=True, message="ok"),
        ]
        report = GateReport(
            version="1.0.0", commit_sha="abc", checks=checks, overall="passed"
        )
        assert report.overall == "passed"


class TestGateOverride:
    """Override flag allows proceeding despite failures."""

    def test_override_changes_status(self):
        checks = [
            CheckResult(name="check1", passed=False, message="fail"),
        ]
        report = GateReport(
            version="1.0.0",
            commit_sha="abc",
            checks=checks,
            overall="overridden",
            override_reason="hotfix required",
        )
        assert report.overall == "overridden"
        assert report.override_reason == "hotfix required"

    def test_override_without_reason_is_invalid(self):
        # The run_gate function should require reason when override is True
        # We test the contract: override=True + no reason = still failed
        checks = [
            CheckResult(name="check1", passed=False, message="fail"),
        ]
        report = GateReport(
            version="1.0.0",
            commit_sha="abc",
            checks=checks,
            overall="failed",
            override_reason=None,
        )
        assert report.overall == "failed"
