"""Verification suite: FixtureDesign -> TestBedDesign rename completeness.

This is a TDD-style assertion suite. Each test pins a specific facet of the
rename and prints an explicit diff/violation list on failure so the offending
files can be fixed directly. No production source is modified by this file.

Layout assumptions:
    Repo root resolves from this file: ../../../../  ==> /workspaces/concord
    libs/python/                         (Python source under corekinect/, database/)
    apps/backend/                        (HTTP API + adjacent services)
    tools/corectl/src/                   (CLI source)
    apps/frontend/app/src/               (SvelteKit app)
    .claude/knowledge/                   (knowledge base)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Tuple

import pytest


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# tests/integration/test_*.py -> tests/integration -> tests -> http-api ->
# backend -> apps -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[5]


def _exists(p: Path) -> Path:
    assert p.exists(), f"Path does not exist (rename verification cannot run): {p}"
    return p


def _walk_files(root: Path, suffixes: Iterable[str]) -> List[Path]:
    """Yield files under root with the given suffix(es), skipping noise dirs."""
    skip_dirs = {
        "__pycache__",
        ".git",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        "htmlcov",
        "egg-info",
        ".nx",
    }
    out: List[Path] = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(part in skip_dirs or part.endswith(".egg-info") for part in f.parts):
            continue
        if f.suffix in suffixes:
            out.append(f)
    return out


def _strip_python_comments(line: str) -> str:
    """Remove a trailing ``#`` comment, respecting strings naively."""
    in_str: str = ""
    out_chars: List[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < len(line):
                out_chars.append(line[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = ""
        else:
            if ch in ("'", '"'):
                in_str = ch
                out_chars.append(ch)
            elif ch == "#":
                break
            else:
                out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def _line_is_ts_comment(line: str) -> bool:
    stripped = line.lstrip()
    return (
        stripped.startswith("//")
        or stripped.startswith("/*")
        or stripped.startswith("*")
        or stripped.startswith("*/")
    )


# ---------------------------------------------------------------------------
# 1. No stale Python imports of corekinect.fixture
# ---------------------------------------------------------------------------

def test_no_legacy_corekinect_fixture_import() -> None:
    """No code should still ``from corekinect.fixture`` or ``import corekinect.fixture``."""
    roots = [
        _exists(REPO_ROOT / "libs" / "python"),
        _exists(REPO_ROOT / "apps" / "backend"),
        _exists(REPO_ROOT / "tools" / "corectl" / "src"),
    ]

    pattern = re.compile(r"^\s*(from\s+corekinect\.fixture\b|import\s+corekinect\.fixture\b)")
    violations: List[str] = []
    for root in roots:
        for path in _walk_files(root, {".py"}):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, raw in enumerate(lines, start=1):
                # Comment-only lines are allowed.
                if raw.lstrip().startswith("#"):
                    continue
                if pattern.search(raw):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {raw.strip()}")

    if violations:
        msg = "Legacy corekinect.fixture imports found ({}):\n  - ".format(
            len(violations)
        ) + "\n  - ".join(violations)
        pytest.fail(msg)


# ---------------------------------------------------------------------------
# 2. No stale Python classes / symbols
# ---------------------------------------------------------------------------

LEGACY_SYMBOLS = (
    "FixtureValidationError",
    "FixtureIOError",
    "FixtureExtractionError",
    "extract_fixture",
    "FixtureConfig",
    "FixtureContext",
    "fixture_factory",
)


def test_no_legacy_fixture_symbols() -> None:
    """No SDK/consumer file may reference the pre-rename symbol names."""
    roots = [
        _exists(REPO_ROOT / "libs" / "python"),
        _exists(REPO_ROOT / "apps" / "backend"),
        _exists(REPO_ROOT / "tools" / "corectl" / "src"),
    ]

    # Word-boundary search; match the exact identifier only.
    patterns = [(sym, re.compile(rf"\b{re.escape(sym)}\b")) for sym in LEGACY_SYMBOLS]

    # This file itself enumerates the legacy symbol names as string literals,
    # so it must be excluded from its own scan.
    self_path = Path(__file__).resolve()

    violations: List[str] = []
    for root in roots:
        for path in _walk_files(root, {".py"}):
            if path.resolve() == self_path:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if not any(sym in text for sym, _ in patterns):
                continue
            for lineno, raw in enumerate(text.splitlines(), start=1):
                # Skip comment-only lines.
                if raw.lstrip().startswith("#"):
                    continue
                code = _strip_python_comments(raw)
                for sym, rx in patterns:
                    if rx.search(code):
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}:{lineno}: [{sym}] {raw.strip()}"
                        )

    if violations:
        msg = "Legacy fixture symbols found ({}):\n  - ".format(
            len(violations)
        ) + "\n  - ".join(violations)
        pytest.fail(msg)


# ---------------------------------------------------------------------------
# 3. Prisma client exposes testbeddesign accessor
# ---------------------------------------------------------------------------

def test_prisma_client_has_testbeddesign() -> None:
    """The generated Prisma client must expose ``.testbeddesign`` and not ``.fixturedesign``."""
    from database import Prisma  # type: ignore

    client = Prisma()
    assert hasattr(client, "testbeddesign"), (
        "Prisma client is missing the 'testbeddesign' accessor. "
        "Rerun the prisma generator and check schema.prisma for `model TestBedDesign`."
    )
    assert not hasattr(client, "fixturedesign"), (
        "Prisma client still exposes the legacy 'fixturedesign' accessor. "
        "The rename in schema.prisma is incomplete or the generated client is stale."
    )


# ---------------------------------------------------------------------------
# 4. Manifest schema accepts `testbed:` key, rejects `fixture:` key
# ---------------------------------------------------------------------------

def _make_manifest(top_key: str) -> dict:
    """Build a minimal v1.0 manifest using ``top_key`` for the testbed/fixture section."""
    inner = {
        "module": "testbeds.alpha_b0.testbed:AlphaB0TestBed",
    }
    return {
        "schema": "1.0",
        "package": {
            "type": "validation",
            "version": "0.1.0",
            "framework": ">=0.1.0",
        },
        "product": {
            "slug": "alpha",
            "board": "alpha_b0",
        },
        top_key: inner,
        "stages": {
            "smoke": {
                "directory": "tests/smoke",
            },
        },
    }


def test_manifest_schema_testbed_key() -> None:
    """``testbed:`` is canonical; ``fixture:`` is accepted with a deprecation warning
    for one-minor-version backward compatibility (see corekinect knowledge file).
    """
    from corekinect.manifest.schema import validate_manifest

    ok = validate_manifest(_make_manifest("testbed"))
    assert ok.valid, (
        "Manifest with `testbed:` key failed to validate:\n"
        + "\n".join(f"  - {e}" for e in ok.errors)
    )

    # Legacy `fixture:` key still validates — backward compat for one
    # minor — but must emit a deprecation warning pointing operators
    # at the new key.
    legacy = validate_manifest(_make_manifest("fixture"))
    assert legacy.valid, (
        "Manifest with legacy `fixture:` key failed to validate — the one-minor "
        "backward-compat path is broken:\n"
        + "\n".join(f"  - {e}" for e in legacy.errors)
    )
    warning_str = "\n".join(str(w) for w in legacy.warnings).lower()
    assert "deprecated" in warning_str and "testbed" in warning_str, (
        "Legacy `fixture:` key validated, but no deprecation warning pointed at the "
        "new `testbed:` key:\n" + warning_str
    )


# ---------------------------------------------------------------------------
# 5. Backend endpoint exists at /v2/test-bed-designs (and old path is gone)
# ---------------------------------------------------------------------------

def test_v2_test_bed_designs_endpoint() -> None:
    """The Flask app's URL map must contain ``/v2/test-bed-designs`` and not the old path."""
    # ``v2`` is a module-level Blueprint singleton — once Flask has
    # registered it to *any* app it freezes, and ``add_url_rule`` raises
    # on a subsequent call. Other tests in the suite may have already
    # forced that registration on their own Flask app, so we cannot call
    # ``register_v2_routes`` here unconditionally — the parallel-worker
    # version of this test file would explode the second time around.
    #
    # Either way the route list we care about lives on the blueprint
    # itself: ``v2.deferred_functions`` are the ``add_url_rule`` closures
    # captured at import time. We inspect those when the blueprint is
    # already frozen, and fall back to a fresh Flask app + registration
    # when it isn't.
    from api.v2.router import register_v2_routes, v2  # type: ignore
    from corekinect.utils import Logger  # type: ignore
    from flask import Flask  # type: ignore
    from flask_socketio import SocketIO  # type: ignore

    if v2._got_registered_once:
        # Blueprint already registered — walk its deferred-rule list.
        rules: list[str] = []
        # Each registered rule shows up as a partial; the captured kwargs
        # contain the path. Easier: use the blueprint's own bookkeeping.
        # Flask exposes registered url rules through the app's url_map
        # after registration, so reach for the first app that owns it.
        # `v2.deferred_functions` are pre-registration; `_blueprints` on
        # the app is the post-registration source of truth. We
        # reconstruct paths from the deferred functions' captured args.
        for fn in v2.deferred_functions:
            # bp.add_url_rule populates a closure that calls
            # state.add_url_rule(rule=...). We can't introspect the
            # closure cleanly; instead, rebuild via a throwaway state.
            pass
        # Simpler path: register the blueprint to a fresh Flask app and
        # read its url_map. Flask permits a second registration as long
        # as we don't call add_url_rule again — we don't.
        throwaway = Flask("rename-completeness-probe")
        throwaway.register_blueprint(v2)
        rules = [str(r) for r in throwaway.url_map.iter_rules()]
    else:
        # Blueprint not yet registered — wire it up on a fresh app.
        throwaway = Flask("rename-completeness-probe")
        logger = Logger(log_name="test-rename-completeness")
        socketio = SocketIO()
        register_v2_routes(logger, throwaway, socketio)
        rules = [str(r) for r in throwaway.url_map.iter_rules()]

    has_new = any(r.startswith("/v2/test-bed-designs") for r in rules)
    has_old = any(r.startswith("/v2/fixtures/designs") for r in rules)

    if not has_new or has_old:
        related = sorted(r for r in rules if "design" in r or "fixture" in r)
        pytest.fail(
            "URL map check failed:\n"
            f"  has /v2/test-bed-designs : {has_new}\n"
            f"  has /v2/fixtures/designs : {has_old} (must be False)\n"
            "  related routes registered:\n    - "
            + "\n    - ".join(related)
        )


# ---------------------------------------------------------------------------
# 6. Frontend TS models renamed
# ---------------------------------------------------------------------------

def test_frontend_models_renamed() -> None:
    """models.ts must declare TestBedDesign and not declare FixtureDesign."""
    models_path = _exists(
        REPO_ROOT / "apps" / "frontend" / "app" / "src" / "lib" / "types" / "models.ts"
    )
    text = models_path.read_text(encoding="utf-8")

    assert re.search(r"^\s*export\s+interface\s+TestBedDesign\b", text, re.MULTILINE), (
        f"`export interface TestBedDesign` not found in {models_path.relative_to(REPO_ROOT)}"
    )

    legacy = re.findall(r"^\s*export\s+interface\s+FixtureDesign\b.*$", text, re.MULTILINE)
    if legacy:
        pytest.fail(
            "`export interface FixtureDesign` still present in models.ts:\n  - "
            + "\n  - ".join(legacy)
        )


# ---------------------------------------------------------------------------
# 7. Frontend has no lowercase prose "fixture design(s)"
# ---------------------------------------------------------------------------

LOWERCASE_FIXTURE_DESIGN = re.compile(r"\bfixture\s+designs?\b", re.IGNORECASE)


def _has_jsdoc_marker(line: str) -> bool:
    """Treat lines that look like JSDoc / inline comments as exempt."""
    return _line_is_ts_comment(line)


def test_frontend_no_lowercase_fixture_design_strings() -> None:
    """No non-comment line in the SvelteKit app says 'fixture design(s)' (case-insensitive)."""
    root = _exists(REPO_ROOT / "apps" / "frontend" / "app" / "src")
    violations: List[str] = []

    for path in _walk_files(root, {".svelte", ".ts"}):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        in_block_comment = False
        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            # Track /* ... */ block comments naively.
            if in_block_comment:
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                if "*/" not in stripped:
                    in_block_comment = True
                continue
            if _has_jsdoc_marker(raw):
                continue
            if LOWERCASE_FIXTURE_DESIGN.search(raw):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {stripped}"
                )

    if violations:
        pytest.fail(
            "Lowercase 'fixture design(s)' prose found in frontend "
            f"({len(violations)} hits):\n  - "
            + "\n  - ".join(violations)
        )


# ---------------------------------------------------------------------------
# 8. Knowledge files updated
# ---------------------------------------------------------------------------

KNOWLEDGE_FILES = (
    ".claude/knowledge/glossary.md",
    ".claude/knowledge/prisma/schema-overview.md",
    ".claude/knowledge/apps/frontend/app.md",
    ".claude/knowledge/apps/backend/http-api.md",
)


def test_claude_knowledge_files_updated() -> None:
    """Each .claude knowledge file must mention TestBedDesign."""
    missing: List[Tuple[str, str]] = []
    for rel in KNOWLEDGE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            missing.append((rel, "file not found"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            missing.append((rel, "unreadable"))
            continue
        if "TestBedDesign" not in text:
            missing.append((rel, "no 'TestBedDesign' string"))

    if missing:
        pytest.fail(
            "Knowledge files not refreshed for rename:\n  - "
            + "\n  - ".join(f"{rel}: {reason}" for rel, reason in missing)
        )
