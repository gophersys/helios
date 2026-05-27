"""Phase D Layer 1 — runner project.json must declare implicit dependencies.

The test-runner Docker image bakes in `libs/python/corekinect`,
`libs/protocols/mtib`, and `tools/corectl`. When any of those sources
change, Nx must mark the runner as dirty so the affected-graph picks it
up for rebuild and re-push.

Without `implicitDependencies` on the runner's `project.json`, a change
to corekinect would deploy through `nx update platform` without
rebuilding the runner image — and the live runner pods would run a
stale corekinect against new test packages. That is the v0.12.0 -> 0.12.3
silent-skew failure mode.

Nx's `implicitDependencies` takes project NAMES (the `name` field in
each project.json), not source paths. We assert the names AND validate
that those names resolve to project trees that actually cover the
baked-in code paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PROJECT_JSON = WORKSPACE_ROOT / "deploy" / "runner" / "project.json"

# Project NAMES (the `name` field in each upstream project.json) the
# runner depends on, plus the source path each one must cover.
# (project_name, expected_source_path_under_workspace_root)
REQUIRED_IMPLICIT_DEPENDENCIES = (
    ("corekinect", "libs/python/corekinect"),
    ("protocols", "libs/protocols"),
    ("corectl", "tools/corectl"),
)


@pytest.fixture(scope="module")
def runner_project() -> dict:
    """Load deploy/runner/project.json as a dict."""
    assert RUNNER_PROJECT_JSON.exists(), (
        f"runner project.json not found at {RUNNER_PROJECT_JSON}"
    )
    with RUNNER_PROJECT_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_project_by_name(name: str) -> dict | None:
    """Find a project.json with `name == <name>` anywhere in the workspace."""
    for candidate in WORKSPACE_ROOT.rglob("project.json"):
        # Skip node_modules and any nested dependency trees.
        if "node_modules" in candidate.parts:
            continue
        try:
            with candidate.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("name") == name:
            return data
    return None


def test_runner_declares_implicit_dependencies(runner_project: dict) -> None:
    """`implicitDependencies` must exist on the runner project."""
    assert "implicitDependencies" in runner_project, (
        "deploy/runner/project.json must declare `implicitDependencies` so that "
        "changes to baked-in sources (corekinect, mtib protocols, corectl) mark "
        "the runner image as affected. Without this, runner pods drift from "
        "the platform code — the exact v0.12.0->0.12.3 skew failure mode."
    )


def test_runner_implicit_dependencies_are_a_list_not_a_string(runner_project: dict) -> None:
    """Nx expects a JSON array. A bare string here is silently ignored."""
    deps = runner_project.get("implicitDependencies")
    assert isinstance(deps, list), (
        f"implicitDependencies must be a JSON array, got {type(deps).__name__}. "
        "Nx ignores non-list values without warning."
    )


@pytest.mark.parametrize("name,expected_path", REQUIRED_IMPLICIT_DEPENDENCIES)
def test_runner_implicit_dependency_listed(runner_project: dict, name: str, expected_path: str) -> None:
    """Each required dependency project must appear in implicitDependencies."""
    deps = runner_project.get("implicitDependencies", [])
    assert name in deps, (
        f"{name!r} is missing from runner implicitDependencies. "
        f"The runner image bakes in {expected_path!r}; changes there must "
        "trigger a runner rebuild or the deployed pods run stale code."
    )


@pytest.mark.parametrize("name,expected_path", REQUIRED_IMPLICIT_DEPENDENCIES)
def test_required_dependency_project_resolves(name: str, expected_path: str) -> None:
    """Each dependency name must resolve to a real Nx project on disk."""
    project = _load_project_by_name(name)
    assert project is not None, (
        f"Nx project named {name!r} could not be located in the workspace. "
        "implicitDependencies takes project NAMES (the `name` field of each "
        "project.json), not source paths. If the project was renamed, update "
        "the runner's implicitDependencies and this test together."
    )


@pytest.mark.parametrize("name,expected_path", REQUIRED_IMPLICIT_DEPENDENCIES)
def test_dependency_project_covers_expected_source_path(name: str, expected_path: str) -> None:
    """The resolved project's root/sourceRoot must include the baked source path.

    Catches the failure mode where the project name still exists but its
    sourceRoot has moved away from what the runner image actually contains.
    """
    project = _load_project_by_name(name)
    assert project is not None, f"Project {name!r} not found — earlier test should have caught this."

    root = project.get("root") or project.get("sourceRoot") or ""
    source_root = project.get("sourceRoot") or root
    # The expected path must equal, contain, or be contained by the project's tree.
    covered = (
        expected_path == root
        or expected_path == source_root
        or expected_path.startswith(root + "/")
        or expected_path.startswith(source_root + "/")
        or root.startswith(expected_path + "/")
        or source_root.startswith(expected_path + "/")
    )
    assert covered, (
        f"Nx project {name!r} (root={root!r}, sourceRoot={source_root!r}) does "
        f"not cover the expected baked-in path {expected_path!r}. The runner's "
        "implicit dependency contract is broken — either the project moved or "
        "the runner image no longer bakes in that path."
    )
