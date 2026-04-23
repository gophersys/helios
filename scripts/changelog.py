#!/usr/bin/env python3
"""Generate changelog from conventional commits.

Usage:
    python scripts/changelog.py [from_ref] [to_ref]

    If no refs given, uses last git tag to HEAD.

Output: Markdown changelog to stdout.
Exit code: 0=patch, 1=minor, 2=major (for CI version bump decisions).
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

COMMIT_PATTERN = re.compile(
    r"^(?P<type>feat|fix|refactor|docs|test|chore|perf|ci|build|style)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$"
)

CATEGORY_MAP = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "refactor": "Refactors",
    "perf": "Performance",
    "docs": "Documentation",
    "test": "Tests",
    "ci": "CI/CD",
    "build": "Build",
    "chore": "Chores",
    "style": "Style",
}

# Bump priority: types that indicate at least a minor bump
MINOR_TYPES = {"feat"}


@dataclass
class ParsedCommit:
    sha: str
    type: str
    scope: Optional[str]
    description: str
    breaking: bool
    body: str


def parse_commit_line(line: str) -> Optional[ParsedCommit]:
    """Parse a single line of 'SHA subject' into a ParsedCommit, or None."""
    parts = line.strip().split(" ", 1)
    if len(parts) < 2:
        return None
    sha, subject = parts[0], parts[1]
    m = COMMIT_PATTERN.match(subject)
    if not m:
        return None
    return ParsedCommit(
        sha=sha,
        type=m.group("type"),
        scope=m.group("scope"),
        description=m.group("description"),
        breaking=m.group("breaking") == "!",
        body="",
    )


def get_commits(from_ref: str, to_ref: str = "HEAD") -> list[ParsedCommit]:
    """Get parsed conventional commits between two refs."""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"{from_ref}..{to_ref}",
                "--pretty=format:%h %s",
                "--no-merges",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    commits = []
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

    for line in lines:
        parsed = parse_commit_line(line)
        if parsed:
            # Fetch the full body for breaking change detection
            try:
                body_result = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%b", parsed.sha],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                parsed.body = body_result.stdout.strip()
            except subprocess.CalledProcessError:
                pass
            commits.append(parsed)

    return commits


def categorize(commits: list[ParsedCommit]) -> dict[str, list[ParsedCommit]]:
    """Group commits by category."""
    categories: dict[str, list[ParsedCommit]] = {}
    for c in commits:
        cat = CATEGORY_MAP.get(c.type, "Other")
        categories.setdefault(cat, []).append(c)
    return categories


def determine_bump(commits: list[ParsedCommit]) -> str:
    """Return 'major', 'minor', or 'patch' based on commit types."""
    if not commits:
        return "patch"

    has_breaking = any(
        c.breaking or "BREAKING CHANGE" in c.body for c in commits
    )
    if has_breaking:
        return "major"

    has_minor = any(c.type in MINOR_TYPES for c in commits)
    if has_minor:
        return "minor"

    return "patch"


def generate_markdown(
    version: str,
    categories: dict[str, list[ParsedCommit]],
    breaking: list[ParsedCommit],
) -> str:
    """Generate markdown changelog for a version."""
    lines = [f"## {version}", ""]

    if breaking:
        lines.append("### Breaking Changes")
        lines.append("")
        for c in breaking:
            scope_str = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_str}{c.description} ({c.sha})")
        lines.append("")

    # Render categories in a stable order
    category_order = [
        "Features",
        "Bug Fixes",
        "Performance",
        "Refactors",
        "Documentation",
        "Tests",
        "CI/CD",
        "Build",
        "Style",
        "Chores",
    ]

    for cat in category_order:
        commits = categories.get(cat)
        if not commits:
            continue
        lines.append(f"### {cat}")
        lines.append("")
        for c in commits:
            scope_str = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_str}{c.description} ({c.sha})")
        lines.append("")

    # Handle any categories not in the predefined order
    for cat, commits in categories.items():
        if cat in category_order:
            continue
        lines.append(f"### {cat}")
        lines.append("")
        for c in commits:
            scope_str = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_str}{c.description} ({c.sha})")
        lines.append("")

    return "\n".join(lines)


def get_last_tag() -> Optional[str]:
    """Get the most recent git tag, or None."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_version_from_file() -> str:
    """Read version from VERSION file."""
    try:
        with open("VERSION") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def main() -> int:
    args = sys.argv[1:]

    if len(args) >= 2:
        from_ref, to_ref = args[0], args[1]
    elif len(args) == 1:
        from_ref, to_ref = args[0], "HEAD"
    else:
        tag = get_last_tag()
        if tag:
            from_ref, to_ref = tag, "HEAD"
        else:
            # No tags: use initial commit
            try:
                result = subprocess.run(
                    ["git", "rev-list", "--max-parents=0", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                from_ref = result.stdout.strip().split("\n")[0]
                to_ref = "HEAD"
            except subprocess.CalledProcessError:
                print("Error: no git history found", file=sys.stderr)
                return 1

    commits = get_commits(from_ref, to_ref)
    if not commits:
        print("No conventional commits found.", file=sys.stderr)
        return 0

    bump = determine_bump(commits)
    version = get_version_from_file()
    categories = categorize(commits)
    breaking = [c for c in commits if c.breaking or "BREAKING CHANGE" in c.body]

    md = generate_markdown(version, categories, breaking)
    print(md)

    print(f"\nSuggested bump: {bump}", file=sys.stderr)

    exit_codes = {"patch": 0, "minor": 1, "major": 2}
    return exit_codes.get(bump, 0)


if __name__ == "__main__":
    sys.exit(main())
