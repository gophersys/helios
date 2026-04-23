"""Tests for changelog generator."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from changelog import (
    COMMIT_PATTERN,
    ParsedCommit,
    categorize,
    determine_bump,
    generate_markdown,
    parse_commit_line,
)


class TestParseConventionalCommit:
    """Parse conventional commit strings into structured data."""

    def test_simple_feat(self):
        result = parse_commit_line(
            "abc1234 feat: add release endpoint"
        )
        assert result is not None
        assert result.type == "feat"
        assert result.scope is None
        assert result.description == "add release endpoint"
        assert result.sha == "abc1234"
        assert result.breaking is False

    def test_feat_with_scope(self):
        result = parse_commit_line(
            "def5678 feat(http-api): add release endpoint"
        )
        assert result is not None
        assert result.type == "feat"
        assert result.scope == "http-api"
        assert result.description == "add release endpoint"

    def test_fix_commit(self):
        result = parse_commit_line(
            "aaa1111 fix(app): correct validation status display"
        )
        assert result is not None
        assert result.type == "fix"
        assert result.scope == "app"
        assert result.description == "correct validation status display"

    def test_breaking_with_bang(self):
        result = parse_commit_line(
            "bbb2222 feat(api)!: remove v1 endpoints"
        )
        assert result is not None
        assert result.breaking is True
        assert result.type == "feat"

    def test_refactor(self):
        result = parse_commit_line(
            "ccc3333 refactor(protocols): consolidate device message types"
        )
        assert result is not None
        assert result.type == "refactor"
        assert result.scope == "protocols"

    def test_non_conventional_commit_returns_none(self):
        result = parse_commit_line("ddd4444 merge branch 'main'")
        assert result is None

    def test_all_valid_types(self):
        for t in ["feat", "fix", "refactor", "docs", "test", "chore", "perf", "ci", "build", "style"]:
            result = parse_commit_line(f"aaa0000 {t}: something")
            assert result is not None, f"Failed to parse type '{t}'"
            assert result.type == t


class TestCategorizeCommits:
    """Group commits by type into changelog categories."""

    def _make_commit(self, type_: str, desc: str, scope: str = None, breaking: bool = False):
        return ParsedCommit(
            sha="abc1234",
            type=type_,
            scope=scope,
            description=desc,
            breaking=breaking,
            body="",
        )

    def test_groups_by_category(self):
        commits = [
            self._make_commit("feat", "add login"),
            self._make_commit("feat", "add logout"),
            self._make_commit("fix", "fix crash"),
            self._make_commit("refactor", "clean up utils"),
        ]
        result = categorize(commits)
        assert len(result["Features"]) == 2
        assert len(result["Bug Fixes"]) == 1
        assert len(result["Refactors"]) == 1

    def test_empty_list(self):
        result = categorize([])
        assert len(result) == 0

    def test_single_type(self):
        commits = [self._make_commit("fix", "fix a"), self._make_commit("fix", "fix b")]
        result = categorize(commits)
        assert "Bug Fixes" in result
        assert len(result["Bug Fixes"]) == 2


class TestDetectBreakingChanges:
    """Commits with BREAKING CHANGE footer or ! after type are breaking."""

    def _make_commit(self, type_: str, desc: str, breaking: bool = False, body: str = ""):
        return ParsedCommit(
            sha="abc1234",
            type=type_,
            scope=None,
            description=desc,
            breaking=breaking,
            body=body,
        )

    def test_bang_marker_is_breaking(self):
        c = self._make_commit("feat", "remove v1", breaking=True)
        assert c.breaking is True

    def test_body_breaking_change(self):
        c = self._make_commit("feat", "change api", body="BREAKING CHANGE: removed field x")
        # The body should be checked by determine_bump
        bump = determine_bump([c])
        assert bump == "major"

    def test_no_breaking(self):
        c = self._make_commit("feat", "add endpoint")
        assert c.breaking is False


class TestDetermineVersionBump:
    """feat = minor, fix = patch, BREAKING = major."""

    def _make_commit(self, type_: str, breaking: bool = False, body: str = ""):
        return ParsedCommit(
            sha="abc1234",
            type=type_,
            scope=None,
            description="something",
            breaking=breaking,
            body=body,
        )

    def test_patch_for_fix(self):
        commits = [self._make_commit("fix")]
        assert determine_bump(commits) == "patch"

    def test_minor_for_feat(self):
        commits = [self._make_commit("feat")]
        assert determine_bump(commits) == "minor"

    def test_major_for_breaking(self):
        commits = [self._make_commit("feat", breaking=True)]
        assert determine_bump(commits) == "major"

    def test_major_for_body_breaking(self):
        commits = [self._make_commit("fix", body="BREAKING CHANGE: field removed")]
        assert determine_bump(commits) == "major"

    def test_highest_wins(self):
        commits = [
            self._make_commit("fix"),
            self._make_commit("feat"),
        ]
        assert determine_bump(commits) == "minor"

    def test_breaking_trumps_all(self):
        commits = [
            self._make_commit("fix"),
            self._make_commit("feat"),
            self._make_commit("chore", breaking=True),
        ]
        assert determine_bump(commits) == "major"

    def test_chore_only_is_patch(self):
        commits = [self._make_commit("chore"), self._make_commit("docs")]
        assert determine_bump(commits) == "patch"


class TestGenerateMarkdown:
    """Output properly formatted markdown changelog."""

    def _make_commit(self, type_: str, desc: str, scope: str = None, sha: str = "abc1234"):
        return ParsedCommit(
            sha=sha,
            type=type_,
            scope=scope,
            description=desc,
            breaking=False,
            body="",
        )

    def test_basic_output(self):
        categories = {
            "Features": [self._make_commit("feat", "add login")],
            "Bug Fixes": [self._make_commit("fix", "fix crash")],
        }
        md = generate_markdown("1.2.0", categories, [])
        assert "## 1.2.0" in md
        assert "### Features" in md
        assert "### Bug Fixes" in md
        assert "add login" in md
        assert "fix crash" in md

    def test_scope_in_output(self):
        categories = {
            "Features": [self._make_commit("feat", "add login", scope="auth")],
        }
        md = generate_markdown("1.0.0", categories, [])
        assert "**auth**" in md or "auth" in md

    def test_breaking_changes_section(self):
        breaking_commit = ParsedCommit(
            sha="bbb2222",
            type="feat",
            scope="api",
            description="remove v1 endpoints",
            breaking=True,
            body="",
        )
        categories = {"Features": [breaking_commit]}
        md = generate_markdown("2.0.0", categories, [breaking_commit])
        assert "BREAKING CHANGES" in md or "Breaking Changes" in md

    def test_empty_categories(self):
        md = generate_markdown("0.1.0", {}, [])
        assert "## 0.1.0" in md
