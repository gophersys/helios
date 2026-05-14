"""corectl test — validation test management commands.

Usage:
    corectl test init --product sigma5 --board sigma5_a0
    corectl test init --product sigma5 --board sigma5_a0 --type manufacturing
    corectl test validate [--path .] [--strict]
    corectl test run smoke [--timeout 30]
    corectl test run regression --marker health_check
    corectl test package
    corectl test upload
    corectl test release <package-id>
    corectl test release --version dev-abc12345
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
import yaml

from ..config import get_service_account_key, save_config
from ..api import AuthError, ConcordAPI


def _client(ctx) -> ConcordAPI:
    """Build an authenticated Concord API client for this command context."""
    config = ctx.obj["config"]
    try:
        return ConcordAPI.from_config(
            config,
            save_callback=save_config,
            service_account_key=get_service_account_key(config),
        )
    except AuthError as e:
        import click as _click
        _click.echo(str(e), err=True)
        raise SystemExit(1)


MANIFEST_NAME = "concord.yaml"

# Standard stage directories — convention, not configuration
STANDARD_STAGES = ["smoke", "driver", "integration", "regression", "fuota"]
MANUFACTURING_STAGES = ["manufacturing"]
ALL_STAGES = STANDARD_STAGES + MANUFACTURING_STAGES

# Required files in a valid test project.
# pytest config can live in pytest.ini OR pyproject.toml
REQUIRED_FILES = [
    "concord.yaml",
    "conftest.py",
]

# Framework artifacts — generated/owned by corectl, NOT hand-editable.
# Validation rejects any project with a missing or customized artifact.
# Top-level dirs whose entire contents are framework-managed.
FRAMEWORK_ARTIFACT_DIRS = (".claude", ".devcontainer")
# Top-level files that are also framework-managed. Live at the project
# root because their consumers (git, pre-commit) look for them there.
FRAMEWORK_ARTIFACT_FILES = (".gitattributes", ".pre-commit-config.yaml")
FRAMEWORK_VERSION_MARKER = ".framework-version"


def _framework_version() -> str:
    """Return the installed corekinect version string.

    Hard-fails when corekinect isn't importable. corectl ships in
    lockstep with corekinect — if corekinect can't be imported, the
    install is broken and silently masking that with a fallback would
    let half-set-up environments validate, scaffold, or upload bad
    state. Installer should run ``corectl update`` to fix.
    """
    try:
        import corekinect
    except ImportError as exc:
        raise click.ClickException(
            "corekinect is not importable. corectl ships in lockstep with "
            "corekinect — your install is incomplete. Run `corectl update` "
            "(or reinstall the wheels) and try again."
        ) from exc
    version = getattr(corekinect, "__version__", None)
    if not version:
        raise click.ClickException(
            "corekinect is importable but has no __version__. Reinstall the wheel."
        )
    return version

# Try to import the manifest library (optional — not always installed)
try:
    from corekinect.manifest.loader import load_manifest, find_manifest, load_manifest_raw
    from corekinect.manifest.schema import validate_manifest as schema_validate_manifest
    from corekinect.manifest.types import Manifest

    HAS_MANIFEST_LIB = True
except ImportError:
    HAS_MANIFEST_LIB = False


def _find_manifest_path(project_dir: Path) -> Path:
    """Find the manifest file in project_dir.

    Raises SystemExit if not found.
    """
    manifest_path = project_dir / MANIFEST_NAME
    if manifest_path.exists():
        return manifest_path

    click.echo(f"No {MANIFEST_NAME} found", err=True)
    raise SystemExit(1)


def _load_manifest_yaml(manifest_path: Path) -> dict:
    """Load a manifest file as a raw dict."""
    with open(manifest_path) as f:
        data = yaml.safe_load(f) or {}
    return data


def _get_slug(manifest: dict) -> str:
    """Extract the product slug from a manifest dict."""
    return manifest.get("product", {}).get("slug", "unknown")


def _get_version(manifest: dict) -> str:
    """Extract the package version from a manifest dict."""
    return manifest.get("package", {}).get("version", "0.0.0")


def _get_framework(manifest: dict) -> str:
    """Extract the framework constraint from a manifest dict."""
    return manifest.get("package", {}).get("framework", "unknown")


def _get_package_type(manifest: dict) -> str:
    """Extract the package type from a manifest dict."""
    return manifest.get("package", {}).get("type", "validation").upper()


# =============================================================================
# Validator
# =============================================================================


class ValidationResult:
    """Collects errors and warnings from validation."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self, msg: str) -> None:
        self.info.append(msg)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


def _validate_structure_v2(project_dir: Path, result: ValidationResult) -> dict:
    """Level 1 for v2 manifests: JSON Schema validation + file checks."""

    manifest_path = project_dir / MANIFEST_NAME
    manifest = _load_manifest_yaml(manifest_path)

    # Required files
    for filename in REQUIRED_FILES:
        if (project_dir / filename).exists():
            result.ok(f"{filename}")
        else:
            result.error(f"Missing: {filename}")

    # pyproject.toml (required for runner pip install)
    if (project_dir / "pyproject.toml").exists():
        result.ok("pyproject.toml")
    else:
        result.error("Missing: pyproject.toml — the runner needs this to install the package")

    if not manifest:
        result.error(f"{MANIFEST_NAME} is empty or invalid YAML")
        return manifest

    # JSON Schema validation via the manifest library
    if HAS_MANIFEST_LIB:
        schema_result = schema_validate_manifest(manifest)
        for err in schema_result.errors:
            result.error(f"Schema: {err}")
        for warn in schema_result.warnings:
            result.warn(f"Schema: {warn}")
        if not schema_result.valid:
            return manifest
    else:
        result.warn("corekinect.manifest not installed — skipping JSON Schema validation")
        for fld in ["schema", "package", "product", "fixture"]:
            if fld not in manifest:
                result.error(f"Manifest missing '{fld}' field")

    pkg_type = manifest.get("package", {}).get("type", "validation")

    # Validate stage/step directories exist and have tests
    if pkg_type == "validation":
        stages = manifest.get("stages", {})
        if not stages:
            result.error("No stages defined in manifest")
        for stage_name, stage_cfg in stages.items():
            if isinstance(stage_cfg, dict) and stage_cfg.get("enabled") is False:
                result.ok(f"Stage '{stage_name}' (disabled)")
                continue
            directory = stage_cfg.get("directory", f"tests/{stage_name}") if isinstance(stage_cfg, dict) else f"tests/{stage_name}"
            stage_dir = project_dir / directory
            if stage_dir.is_dir():
                test_files = list(stage_dir.glob("test_*.py"))
                if test_files:
                    result.ok(f"{directory}/ ({len(test_files)} test files)")
                else:
                    result.warn(f"{directory}/ has no test files")
            else:
                result.error(f"Stage '{stage_name}' directory missing: {directory}")
    elif pkg_type == "manufacturing":
        stages = manifest.get("stages", {})
        if not stages:
            result.error("No stages defined in manifest")
        for stage_name, stage_cfg in stages.items():
            directory = stage_cfg.get("directory", f"tests/{stage_name}") if isinstance(stage_cfg, dict) else f"tests/{stage_name}"
            module = stage_cfg.get("module", "") if isinstance(stage_cfg, dict) else ""
            if module:
                module_path = f"{directory}/{module}.py"
                if (project_dir / module_path).exists():
                    result.ok(f"Stage: {stage_name} -> {module_path}")
                else:
                    result.error(f"Stage '{stage_name}' module not found: {module_path}")
            else:
                stage_dir = project_dir / directory
                if stage_dir.is_dir():
                    result.ok(f"Stage: {stage_name} -> {directory}/")
                else:
                    result.error(f"Stage '{stage_name}' directory missing: {directory}")

    # TestBed profile
    testbed = manifest.get("testbed", {})
    profile_path = testbed.get("profile", "")
    if profile_path:
        full_path = project_dir / profile_path
        if full_path.exists():
            result.ok(f"TestBed profile: {profile_path}")
            # Validate fixture YAML content
            try:
                with open(full_path) as f:
                    profile_data = yaml.safe_load(f)
                if not profile_data:
                    result.error(f"TestBed profile is empty: {profile_path}")
                else:
                    if "power" not in profile_data:
                        result.error(f"TestBed profile missing 'power' config: {profile_path}")
                    else:
                        result.ok(f"TestBed profile has power config")
            except Exception as exc:
                result.error(f"TestBed profile invalid YAML: {exc}")
        else:
            result.error(f"TestBed profile not found: {profile_path}")

    # TestBed controller
    controller = testbed.get("controller", "")
    if controller:
        # Convert dotted path to file path
        parts = controller.rsplit(".", 1)
        if len(parts) == 2:
            module_path = parts[0].replace(".", "/") + ".py"
            class_name = parts[1]
            if (project_dir / module_path).exists():
                # Verify the class exists in the file
                content = (project_dir / module_path).read_text()
                if f"class {class_name}" in content:
                    result.ok(f"TestBed controller: {controller}")
                else:
                    result.error(f"TestBed controller class '{class_name}' not found in {module_path}")
            else:
                result.error(f"TestBed controller module not found: {module_path}")

    # Timeout sanity checks
    for stage_name, stage_cfg in (manifest.get("stages", {}) or {}).items():
        if isinstance(stage_cfg, dict):
            timeout = stage_cfg.get("timeout_s", 0)
            if timeout and (timeout < 5 or timeout > 14400):
                result.warn(f"Stage '{stage_name}' timeout {timeout}s outside reasonable range [5, 14400]")

    return manifest


def _validate_semantics(project_dir: Path, manifest: dict, result: ValidationResult) -> None:
    """Level 2: Does the project make sense?"""

    product = manifest.get("product", {})

    device = product.get("device", {})
    dt = device.get("type_id", 0)
    dv = device.get("variant_id", 0)

    if dt == 0 or dv == 0:
        result.warn(f"Device type={dt}, variant={dv} — set these for production use")

    # ── Test-depth: enforce the two-level contract the runner + UI assume ──
    # The reporter's thread-local step counter and the frontend's two-level
    # tree render assume ``def test_*`` functions open at most one
    # ``with report.step(...)`` at a time, and helper functions never open
    # their own step. Violations here would corrupt step indices under the
    # slot-parallel runner and mis-render the UI.
    from corectl.commands.test_depth import validate_project as _validate_depth

    depth_errors = _validate_depth(project_dir)
    if depth_errors:
        for err in depth_errors:
            rel = err.file.relative_to(project_dir) if err.file.is_relative_to(project_dir) else err.file
            result.error(f"{rel}:{err.line}: {err.message}")
    else:
        result.ok("Test depth: all tests respect the two-level step contract")

    # ── Runner contracts: per-test timeouts + step.record usage ──
    # The parallel runner buckets slot execution per top-level test; a
    # missing timeout lets one hung slot dominate the whole panel's wall
    # clock. Empty step blocks render as blank UI cards — almost always a
    # test bug. Scoped to files the manifest actually schedules so E2E
    # harness modules (tests/e2e/…) aren't swept in.
    from corectl.commands.test_contracts import validate_files as _validate_contracts

    stage_files: List[Path] = []
    for stage_cfg in manifest.get("stages", {}).values():
        if not isinstance(stage_cfg, dict):
            continue
        directory = stage_cfg.get("directory")
        module = stage_cfg.get("module")
        if directory and module:
            stage_files.append(project_dir / directory / f"{module}.py")

    contract_violations = _validate_contracts(stage_files) if stage_files else []
    errors = [v for v in contract_violations if v.severity == "error"]
    warnings = [v for v in contract_violations if v.severity == "warning"]
    for v in errors:
        rel = v.file.relative_to(project_dir) if v.file.is_relative_to(project_dir) else v.file
        result.error(f"{rel}:{v.line}: [{v.code}] {v.message}")
    for v in warnings:
        rel = v.file.relative_to(project_dir) if v.file.is_relative_to(project_dir) else v.file
        result.warn(f"{rel}:{v.line}: [{v.code}] {v.message}")
    if stage_files and not errors:
        result.ok(
            "Test contracts: every stage test declares @pytest.mark.timeout"
            + (f" ({len(warnings)} warnings)" if warnings else "")
        )

    # conftest.py must declare autoconf plugin
    conftest_path = project_dir / "conftest.py"
    if conftest_path.exists():
        content = conftest_path.read_text()
        if "corekinect.test.autoconf" in content:
            result.ok("conftest.py loads autoconf plugin")
        elif "corekinect.test.reporter" in content:
            result.ok("conftest.py loads reporter plugin")
        else:
            result.warn("conftest.py does not load corekinect.test.autoconf — multi-slot and lifecycle fixtures unavailable")

    # multi_slot consistency
    testbed = manifest.get("testbed", {})
    pkg_type = manifest.get("package", {}).get("type", "validation")
    multi_slot = testbed.get("multi_slot", False)
    if pkg_type == "manufacturing" and not multi_slot:
        result.warn("Manufacturing package with multi_slot=false — most manufacturing fixtures are multi-slot")

    # Validate the Python fixture file referenced by ``fixture.module``.
    # AST-only — never imports the user's code.
    testbed_module = testbed.get("module", "")
    if testbed_module:
        try:
            from corekinect.testbed.extractor import (
                TestBedExtractionError,
                extract_testbed,
            )
        except ImportError:
            result.warn("corekinect.testbed not installed — skipping fixture extraction")
        else:
            if ":" not in testbed_module:
                result.error(
                    f"fixture.module={testbed_module!r} is malformed "
                    f"(expected 'dotted.path:ClassName')"
                )
            else:
                module_path, _ = testbed_module.split(":", 1)
                fixture_file = project_dir / Path(*module_path.split(".")).with_suffix(".py")
                if not fixture_file.is_file():
                    result.error(
                        f"fixture.module points to {fixture_file.relative_to(project_dir)} — file not found"
                    )
                else:
                    try:
                        extract_testbed(fixture_file.read_text(), source_path=str(fixture_file))
                        result.ok(
                            f"{fixture_file.relative_to(project_dir)} passes fixture validation"
                        )
                    except TestBedExtractionError as exc:
                        result.error(
                            f"{fixture_file.relative_to(project_dir)}: {exc}"
                        )

    # Check pytest markers in pytest.ini or pyproject.toml
    pytest_ini = project_dir / "pytest.ini"
    pyproject = project_dir / "pyproject.toml"
    marker_content = ""
    if pytest_ini.exists():
        marker_content = pytest_ini.read_text()
    elif pyproject.exists():
        marker_content = pyproject.read_text()

    if marker_content:
        stages = manifest.get("stages", {})
        for stage_name, stage_cfg in stages.items():
            if isinstance(stage_cfg, dict):
                for marker in stage_cfg.get("markers", []):
                    if marker not in marker_content:
                        result.warn(f"Stage '{stage_name}' uses marker '{marker}' not in pytest config")


def _validate_compatibility(project_dir: Path, manifest: dict, result: ValidationResult) -> None:
    """Level 3: Will it work with the platform?"""

    # Check framework version
    required_version = _get_framework(manifest)
    try:
        import corekinect
        installed = getattr(corekinect, "__version__", "unknown")
        result.ok(f"corekinect {installed} installed (requires {required_version})")

        # Basic version check (not full semver range parsing)
        if required_version.startswith(">="):
            min_ver = required_version.lstrip(">=").split(",")[0].strip()
            if installed < min_ver:
                result.error(
                    f"corekinect {installed} does not satisfy {required_version}"
                )
    except ImportError:
        result.warn(f"corekinect not installed — cannot verify compatibility")

    # Try pytest collection
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "--timeout=10"],
            capture_output=True, text=True, cwd=str(project_dir), timeout=30,
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().split("\n"):
                if "collected" in line:
                    result.ok(f"pytest: {line.strip()}")
        else:
            # Extract useful error from stderr
            err = proc.stderr.strip().split("\n")
            short_err = err[-1] if err else "unknown error"
            if "ModuleNotFoundError" in proc.stderr:
                result.warn(f"pytest collection needs PYTHONPATH — {short_err}")
            else:
                result.warn(f"pytest collection: {short_err[:100]}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        result.warn("Could not run pytest collection")


# =============================================================================
# Commands
# =============================================================================


@click.group()
def test():
    """Manage validation and manufacturing test projects."""
    pass


@test.command()
@click.option("--product", default=None, help="Product slug (skips the interactive picker)")
@click.option("--board", default=None, help="Board revision (e.g., alpha_b0; skips the picker)")
@click.option("--type", "pkg_type", type=click.Choice(["validation", "manufacturing"]),
              default="validation", help="Package type (default: validation)")
@click.argument("path", default=".", required=False)
@click.pass_context
def init(ctx, product: Optional[str], board: Optional[str], pkg_type: str, path: str):
    """Scaffold a new test project, gated by what the backend actually has.

    The backend is the source of truth for products, board revisions, and
    fixture controllers. ``init`` talks to it up front so the scaffolded
    ``concord.yaml`` can never reference a product that doesn't exist or
    a revision that has no attached fixtures to run against.
    """
    project_dir = Path(path).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    api = _client(ctx)
    product_record = _select_product(api, product)
    revision = _select_board_revision(api, product_record, board)

    board_slug = _revision_slug(product_record, revision)
    board_class = "".join(p.capitalize() for p in board_slug.split("_"))

    ctx_vars = {
        "product": product_record["slug"],
        "board": board_slug,
        "board_class": board_class,
        "testbed_module": f"testbeds.{board_slug}.testbed:{board_class}TestBed",
        "device_type_id": revision.get("deviceType") if revision.get("deviceType") is not None else 0,
        "device_variant_id": revision.get("deviceVariant") if revision.get("deviceVariant") is not None else 0,
        "pkg_type": pkg_type,
        "kind": pkg_type,                          # alias used by .claude/.devcontainer templates
        "framework_version": _framework_version(), # corekinect version at scaffold time
    }

    _render_template_tree(pkg_type, project_dir, ctx_vars)
    fixture_dir = project_dir / "fixtures" / board_slug
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "__init__.py").touch()
    testbed_class = ctx_vars["testbed_module"].split(":", 1)[1]
    (fixture_dir / "fixture.py").write_text(
        _starter_fixture_source(testbed_class, pkg_type),
        encoding="utf-8",
    )

    click.echo("")
    click.echo(f"  Created {pkg_type} project at {project_dir}")
    click.echo(f"    product:  {product_record['slug']}")
    click.echo(f"    board:    {board_slug}  (revision {revision['version']})")
    click.echo("")
    click.echo("  Next:")
    click.echo(f"    cd {project_dir}")
    click.echo(f"    # Edit fixtures/{board_slug}/fixture.py — wire the DUT pinout")
    click.echo(f"    corectl test validate")
    click.echo(f"    corectl test run <stage>")
    click.echo("")


# ─────────────────────────────────────────────────────────────────────────
# Backend-aware product / board-revision selection
# ─────────────────────────────────────────────────────────────────────────


def _select_product(api: ConcordAPI, slug: Optional[str]) -> dict:
    """Fetch products from the backend and return the chosen one.

    If ``slug`` is provided, fail fast when it doesn't exist — never
    silently scaffold against a product the platform doesn't know about.
    Otherwise present an interactive picker.
    """
    resp = api.get("/v2/products?limit=100")
    if not resp.ok:
        click.echo(f"Could not list products: HTTP {resp.status_code}", err=True)
        raise SystemExit(1)
    products = (resp.json().get("data") or {}).get("data") or []
    if not products:
        click.echo("No products registered in the backend. Create one in the web UI first.", err=True)
        raise SystemExit(1)

    if slug:
        for p in products:
            if p.get("slug") == slug:
                return p
        click.echo(f"Unknown product slug: {slug!r}", err=True)
        click.echo("Available: " + ", ".join(sorted(p["slug"] for p in products if p.get("slug"))), err=True)
        raise SystemExit(1)

    click.echo("")
    click.echo("  Products:")
    for i, p in enumerate(products, 1):
        extra = f"  ({p.get('revisions', []) and len(p['revisions'])} revisions)" if p.get("revisions") else ""
        click.echo(f"    [{i}] {p['slug']:<16} {p.get('name', '')}{extra}")
    click.echo("")
    idx = click.prompt("Select product", type=click.IntRange(1, len(products)))
    return products[idx - 1]


def _select_board_revision(api: ConcordAPI, product: dict, board_arg: Optional[str]) -> dict:
    """Pick a board revision. Revisions without configured targets are refused.

    ``targets`` on a BoardRevision are what make it runnable — a
    revision with zero targets has no fixtures wired up, so any test
    project scaffolded against it would fail to run. Better to fail the
    init up front.
    """
    resp = api.get(f"/v2/products/{product['id']}?include=boards.revisions")
    if not resp.ok:
        click.echo(f"Could not fetch product detail: HTTP {resp.status_code}", err=True)
        raise SystemExit(1)
    detail = resp.json().get("data") or {}

    revisions: List[dict] = []
    for board in detail.get("boards") or []:
        board_name = board.get("name", "")
        for rev in board.get("revisions") or []:
            rev_copy = dict(rev)
            rev_copy["_board_name"] = board_name
            revisions.append(rev_copy)

    usable = [r for r in revisions if (r.get("targetCount") or (r.get("targets") and len(r["targets"]))) and r.get("status") != "ARCHIVED"]
    if not usable:
        click.echo(
            f"{product['slug']!r} has no active board revision with at least one "
            "configured target/fixture. Ask an admin to wire one up first.",
            err=True,
        )
        raise SystemExit(1)

    if board_arg:
        for r in usable:
            if _revision_slug(product, r) == board_arg or r["version"] == board_arg:
                return r
        click.echo(f"No usable revision matches {board_arg!r}", err=True)
        click.echo(
            "Available: " + ", ".join(_revision_slug(product, r) for r in usable),
            err=True,
        )
        raise SystemExit(1)

    if len(usable) == 1:
        return usable[0]

    click.echo("")
    click.echo(f"  Board revisions for {product['slug']}:")
    for i, r in enumerate(usable, 1):
        slug_ = _revision_slug(product, r)
        click.echo(f"    [{i}] {slug_:<16} (status: {r.get('status', '?')}, targets: {r.get('targetCount', '?')})")
    click.echo("")
    idx = click.prompt("Select board revision", type=click.IntRange(1, len(usable)))
    return usable[idx - 1]


def _revision_slug(product: dict, revision: dict) -> str:
    """The slug the tests use: ``<product>_<version>`` (e.g. ``alpha_b0``).

    Prefer ``ckBoardsName`` when set (it's the authoritative name from
    the ck_boards repo); fall back to ``<product>_<version>`` so a
    newly-created product without ckBoards wiring still gets a sensible
    directory name.
    """
    ck = (revision.get("ckBoardsName") or "").strip()
    if ck:
        return ck
    return f"{product['slug']}_{revision['version']}"


# ─────────────────────────────────────────────────────────────────────────
# Template tree rendering
# ─────────────────────────────────────────────────────────────────────────


def _render_template_tree(pkg_type: str, dest: Path, ctx_vars: dict) -> None:
    """Copy a template tree into ``dest``, substituting ``{{var}}`` tokens.

    Reads templates out of the installed wheel via importlib.resources,
    so this works whether corectl is installed via pipx (normal path) or
    run from a source checkout (editable install).
    """
    from importlib import resources

    # _shared goes down first so pkg-type templates can override if needed.
    _render_pkg(resources.files("corectl") / "templates" / "_shared", dest, ctx_vars)
    _render_pkg(resources.files("corectl") / "templates" / pkg_type, dest, ctx_vars)


def _render_pkg(src_root, dest: Path, ctx_vars: dict) -> None:
    """Recursively copy ``src_root`` (a Traversable) into ``dest``.

    Rename/skip rules:
      * ``__pycache__`` directories and ``*.pyc`` files are skipped — they
        are bytecode artifacts that pytest leaves behind in the installed
        templates directory and would crash the UTF-8 read pass.
      * Directories starting with ``_`` are assumed to be private and
        skipped (``_shared`` is consumed at the top level).
      * ``__init__.py`` files are copied as-is (Python needs them).
      * Other files pass through ``_substitute``.
    """
    if not src_root.is_dir():
        return
    for entry in src_root.iterdir():
        rel = entry.name
        target = dest / rel
        if rel == "__pycache__" or rel.endswith(".pyc"):
            continue
        if entry.is_dir():
            # _foo dirs under the top level are internal scaffolding.
            if rel.startswith("_") and src_root.name in ("validation", "manufacturing"):
                continue
            target.mkdir(parents=True, exist_ok=True)
            _render_pkg(entry, target, ctx_vars)
            continue
        raw = entry.read_text(encoding="utf-8")
        target.write_text(_substitute(raw, ctx_vars), encoding="utf-8")


def _substitute(raw: str, ctx_vars: dict) -> str:
    """Replace ``{{var}}`` tokens. Unknown tokens are left untouched so
    a typo is visible in the generated file instead of silently dropped.
    """
    out = raw
    for key, value in ctx_vars.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def _starter_fixture_source(class_name: str, pkg_type: str) -> str:
    """Return a runnable starter fixture.py source.

    The starter declares a minimal but valid set of DUT resources so
    ``corectl validate`` passes immediately after ``init``. Edit the
    maps to match the actual DUT pinout.
    """
    del pkg_type  # placeholder if mfg vs validation diverge later
    return f'''"""DUT pinout declaration. Edit the maps to match your hardware."""

from __future__ import annotations

from corekinect.testbed import ADC, GPIO, JLink, Power, UART, TestBed


class {class_name}(TestBed):
    name = "{class_name.lower()}"
    revision = "1.0"

    # Wire-protocol channel numbering (0-indexed).
    adcs = {{
        "battery": ADC(channel=0, signal="VBAT"),
    }}

    gpios = {{
        "boot": GPIO(pin=0, role="LOW = DUT boots normally"),
    }}

    uarts = {{
        "app": UART(port=1, target="app-mcu"),
    }}

    jlinks = {{
        "app": JLink(family="NRF52"),
    }}

    power = {{
        "dut": Power(rail="DUT_PWR"),
    }}
'''


# ═════════════════════════════════════════════════════════════════════════
# Framework artifacts — .claude/ and .devcontainer/
#
# These directories ship with the installed corectl/corekinect wheel
# and are re-rendered into a project on init. The dev does not own them
# — `corectl test validate` fails if anything is missing, drifted, or
# customized; the platform refuses uploads that fail this gate. Use
# `corectl test update` to refresh them when corectl/corekinect is bumped.
# ═════════════════════════════════════════════════════════════════════════


def _project_ctx_vars(project_dir: Path, manifest: dict) -> dict:
    """Re-derive the substitution context for a scaffolded project.

    Used by ``validate`` and ``update`` — both need to re-render the
    framework artifact templates against the project's current shape so
    they can compare or write. Pulls from the local manifest (no backend
    round-trip) and the installed framework version.
    """
    product_slug = (manifest.get("product") or {}).get("slug") or "unknown"
    board_slug = (manifest.get("product") or {}).get("board") or "unknown"
    board_class = "".join(p.capitalize() for p in board_slug.split("_"))
    testbed_module = (manifest.get("testbed") or {}).get(
        "module",
        f"testbeds.{board_slug}.testbed:{board_class}TestBed",
    )
    device = (manifest.get("product") or {}).get("device") or {}
    pkg_type = (manifest.get("package") or {}).get("type", "validation")

    # Prefer the marker on disk over the installed version — it tells us
    # what version the project was last refreshed against, which is the
    # version we should diff against when checking for drift. Fall back
    # to the installed version on first scaffold.
    marker_path = project_dir / ".claude" / FRAMEWORK_VERSION_MARKER
    if marker_path.is_file():
        on_disk_version = marker_path.read_text(encoding="utf-8").strip()
    else:
        on_disk_version = _framework_version()

    return {
        "product": product_slug,
        "board": board_slug,
        "board_class": board_class,
        "testbed_module": testbed_module,
        "device_type_id": device.get("type_id", 0),
        "device_variant_id": device.get("variant_id", 0),
        "pkg_type": pkg_type,
        "kind": pkg_type,
        "framework_version": on_disk_version,
    }


def _iter_framework_artifact_renders(ctx_vars: dict):
    """Yield ``(relative_path, expected_text)`` for every framework artifact.

    Walks the bundled template tree for ``.claude/``, ``.devcontainer/``,
    plus the top-level framework-managed files (``.gitattributes``,
    ``.pre-commit-config.yaml``). Applies token substitution and produces
    the exact bytes that should be on disk in a coherent project. Skips
    ``__pycache__`` and ``*.pyc`` (same as the renderer). Raises
    ``RuntimeError`` if any required artifact is missing from the bundle —
    a half-shipped wheel is a framework bug we want loud, not silent.
    """
    from importlib import resources

    shared_root = resources.files("corectl") / "templates" / "_shared"

    # Top-level files
    for filename in FRAMEWORK_ARTIFACT_FILES:
        f = shared_root / filename
        if not f.is_file():
            raise RuntimeError(
                f"Framework artifact file '{filename}' missing from the corectl wheel "
                f"— the install is incomplete. Reinstall corectl/corekinect."
            )
        yield Path(filename), _substitute(f.read_text(encoding="utf-8"), ctx_vars)

    # Top-level dirs (recursive)
    for top in FRAMEWORK_ARTIFACT_DIRS:
        root = shared_root / top
        if not root.is_dir():
            raise RuntimeError(
                f"Framework artifact directory '{top}' missing from the corectl wheel "
                f"— the install is incomplete. Reinstall corectl/corekinect."
            )
        yield from _walk_artifact_tree(root, Path(top), ctx_vars)


def _walk_artifact_tree(src_root, rel_root: Path, ctx_vars: dict):
    """Helper: recursive walk producing (rel_path, content) pairs."""
    for entry in src_root.iterdir():
        rel = entry.name
        if rel == "__pycache__" or rel.endswith(".pyc"):
            continue
        rel_path = rel_root / rel
        if entry.is_dir():
            yield from _walk_artifact_tree(entry, rel_path, ctx_vars)
            continue
        raw = entry.read_text(encoding="utf-8")
        yield rel_path, _substitute(raw, ctx_vars)


def _validate_framework_artifacts(
    project_dir: Path, manifest: dict, result: ValidationResult
) -> None:
    """Check that every framework artifact is present and unmodified.

    Adds errors to ``result`` for missing files, framework-version
    mismatches, or any byte-level drift from the bundled template. The
    user is expected to run ``corectl test update --apply`` to fix.
    """
    ctx_vars = _project_ctx_vars(project_dir, manifest)
    on_disk_version = ctx_vars["framework_version"]
    installed_version = _framework_version()

    # Version mismatch is a hard failure, not a warning. The on-disk
    # version drives token substitution in _iter_framework_artifact_renders;
    # leaving it unaligned means the byte-comparison still passes but the
    # project ships stale framework artifacts to the platform. The user
    # explicitly chose "fail on drift, no overrides" — apply the same rule
    # to the version marker.
    if on_disk_version != installed_version:
        result.error(
            f"Framework artifacts at v{on_disk_version}; installed framework is "
            f"v{installed_version}. Run 'corectl update' then "
            f"'corectl test update --apply' to refresh."
        )

    try:
        expected = list(_iter_framework_artifact_renders(ctx_vars))
    except RuntimeError as exc:
        result.error(str(exc))
        return
    if not expected:
        result.error("Bundled framework artifacts not found in installed corectl.")
        return

    missing: List[str] = []
    drifted: List[str] = []
    for rel_path, expected_text in expected:
        on_disk = project_dir / rel_path
        if not on_disk.is_file():
            missing.append(str(rel_path))
            continue
        actual_text = on_disk.read_text(encoding="utf-8")
        # Normalize line endings — a Windows clone with autocrlf=true
        # produces CRLF in the working tree and would otherwise fail
        # byte comparison even though no human touched the file.
        if actual_text.replace("\r\n", "\n") != expected_text.replace("\r\n", "\n"):
            drifted.append(str(rel_path))

    if missing:
        for m in missing:
            result.error(f"Framework artifact missing: {m}")
        result.error(
            "Run 'corectl test update --apply' to install missing framework artifacts."
        )
    if drifted:
        for d in drifted:
            result.error(f"Framework artifact drifted from template: {d}")
        result.error(
            "Framework artifacts must not be hand-edited. Run "
            "'corectl test update --apply' to revert, or upstream a change to the "
            "framework if you really need it."
        )
    if not missing and not drifted:
        result.ok(f"Framework artifacts: {len(expected)} files coherent with v{on_disk_version}")

    # Pre-commit hook must be installed. The hook file is generated by
    # `pre-commit install` and we don't byte-compare it (contents depend
    # on the pre-commit version), but absence is fatal — devs must run
    # `pre-commit install` once per clone or the validate gate has no
    # client-side enforcement.
    #
    # Resolve the hooks dir to handle both:
    #   - regular clone: .git is a directory → .git/hooks/
    #   - submodule clone: .git is a "gitdir: ..." pointer file →
    #     resolve the pointer to the parent's .git/modules/<name>/hooks/
    git_meta = project_dir / ".git"
    hook_path: Optional[Path] = None
    if git_meta.is_dir():
        hook_path = git_meta / "hooks" / "pre-commit"
    elif git_meta.is_file():
        content = git_meta.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            target = content.split(":", 1)[1].strip()
            resolved = (project_dir / target).resolve()
            hook_path = resolved / "hooks" / "pre-commit"

    if hook_path is not None:
        if not hook_path.is_file():
            result.error(
                "Pre-commit hook not installed. Run "
                "`pip install pre-commit && pre-commit install` once per clone."
            )
        else:
            result.ok("Pre-commit hook installed")


# ═════════════════════════════════════════════════════════════════════════
# corectl test update — refresh framework artifacts in place
# ═════════════════════════════════════════════════════════════════════════


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--apply", "auto_apply", is_flag=True, help="Write changes without confirmation.")
def update(path: str, auto_apply: bool):
    """Refresh ``.claude/`` and ``.devcontainer/`` from the installed framework.

    Re-renders every framework artifact from the bundled templates,
    using the project's current product/board/kind values for token
    substitution. Shows the per-file diff first; pass ``--apply`` to
    write the changes. Test code, fixtures, manifest, conftest, and
    pyproject are never touched.
    """
    project_dir = Path(path).resolve()
    manifest_path = _find_manifest_path(project_dir)
    manifest = _load_manifest_yaml(manifest_path)

    ctx_vars = _project_ctx_vars(project_dir, manifest)
    # Always render against the installed framework — that's what update is for.
    ctx_vars["framework_version"] = _framework_version()

    expected = list(_iter_framework_artifact_renders(ctx_vars))
    if not expected:
        click.echo("No framework artifact templates found in the installed corectl.", err=True)
        raise SystemExit(1)

    creates: List[Tuple[Path, str]] = []
    updates: List[Tuple[Path, str]] = []
    for rel_path, expected_text in expected:
        on_disk = project_dir / rel_path
        if not on_disk.is_file():
            creates.append((rel_path, expected_text))
            continue
        if on_disk.read_text(encoding="utf-8") != expected_text:
            updates.append((rel_path, expected_text))

    if not creates and not updates:
        click.echo(
            f"Framework artifacts already at v{ctx_vars['framework_version']} — nothing to do."
        )
        return

    click.echo("")
    click.echo(f"  Refreshing framework artifacts to v{ctx_vars['framework_version']}:")
    for rel_path, _ in creates:
        click.echo(click.style(f"    + {rel_path}", fg="green"))
    for rel_path, _ in updates:
        click.echo(click.style(f"    ~ {rel_path}", fg="yellow"))
    click.echo("")
    click.echo(f"  ({len(creates)} new, {len(updates)} updated, "
               f"{len(expected) - len(creates) - len(updates)} unchanged)")
    click.echo("")

    if not auto_apply:
        click.echo("  Re-run with --apply to write these changes.")
        return

    for rel_path, expected_text in creates + updates:
        target = project_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected_text, encoding="utf-8")
        # Preserve executable bit for shell scripts (the bundled templates
        # are not stored with mode bits — re-apply by extension).
        if rel_path.suffix == ".sh":
            target.chmod(0o755)

    click.echo(click.style(
        f"  Wrote {len(creates) + len(updates)} files. "
        f"Run 'corectl test validate' to confirm.",
        fg="green",
    ))


# ═════════════════════════════════════════════════════════════════════════
# corectl test sync — remote → local manifest reconciliation
# ═════════════════════════════════════════════════════════════════════════


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--apply", "auto_apply", is_flag=True, help="Apply changes without confirmation.")
@click.pass_context
def sync(ctx, path: str, auto_apply: bool):
    """Pull the authoritative product / board / fixture info from the
    backend and reconcile the local ``concord.yaml`` with it.

    Sync is **one-way**: backend → local. Test logic in ``tests/`` and
    your fixture YAML are never touched. Only the manifest fields the
    platform owns (product slug, board, fixture controller class path)
    get rewritten.
    """
    project_dir = Path(path).resolve()
    manifest_path = project_dir / MANIFEST_NAME
    if not manifest_path.exists():
        click.echo(f"No {MANIFEST_NAME} in {project_dir}", err=True)
        raise SystemExit(1)

    local = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    slug = (local.get("product") or {}).get("slug")
    if not slug:
        click.echo("Manifest has no product.slug — nothing to sync against.", err=True)
        raise SystemExit(1)

    api = _client(ctx)
    remote_product, remote_revision = _fetch_product_and_revision(api, slug, local)

    diff = _diff_manifest(local, remote_product, remote_revision)
    if not diff:
        click.echo(f"{manifest_path.name} is already in sync with the backend.")
        return

    click.echo("")
    click.echo("  Drift detected — these fields will be updated:")
    for path_, before, after in diff:
        click.echo(f"    {path_}: {before!r}  →  {after!r}")
    click.echo("")

    if not auto_apply:
        if not click.confirm("  Apply changes?", default=True):
            click.echo("  Aborted.", err=True)
            raise SystemExit(1)

    _apply_manifest_diff(local, diff)
    manifest_path.write_text(yaml.safe_dump(local, sort_keys=False), encoding="utf-8")
    click.echo(f"  Wrote {manifest_path}")


def _fetch_product_and_revision(api: ConcordAPI, slug: str, local: dict) -> Tuple[dict, dict]:
    """Pull the product + the revision whose slug matches ``board`` locally.

    Returns (product_dict, revision_dict). Exits if either isn't found —
    the user should run ``corectl test init`` to scaffold against a new
    board instead of silently mutating a manifest.
    """
    resp = api.get(f"/v2/products/by-slug/{slug}")
    if not resp.ok:
        click.echo(f"Backend does not know product {slug!r} (HTTP {resp.status_code}).", err=True)
        raise SystemExit(1)
    product = resp.json().get("data") or {}

    local_board = (local.get("product") or {}).get("board", "")
    resp = api.get(f"/v2/products/{product['id']}?include=boards.revisions")
    if not resp.ok:
        click.echo(f"Could not fetch product detail: HTTP {resp.status_code}", err=True)
        raise SystemExit(1)
    detail = resp.json().get("data") or {}

    for board in detail.get("boards") or []:
        for rev in board.get("revisions") or []:
            if _revision_slug(product, rev) == local_board or rev.get("version") == local_board:
                return detail, rev

    click.echo(
        f"No board revision on {slug!r} matches local board {local_board!r}. "
        "Run `corectl test init` to scaffold against a new revision, or fix "
        "product.board in concord.yaml.",
        err=True,
    )
    raise SystemExit(1)


def _diff_manifest(local: dict, product: dict, revision: dict) -> List[Tuple[str, object, object]]:
    """Build a list of ``(dotted_path, before, after)`` tuples.

    We only compare fields the backend authoritatively owns — anything
    else (stage directories, timeouts, hardware arrays, test packages)
    is the test author's call and sync must leave it alone.
    """
    authoritative = _authoritative_fields(local, product, revision)
    drift: List[Tuple[str, object, object]] = []
    for dotted, desired in authoritative:
        current = _deep_get(local, dotted.split("."))
        if current != desired:
            drift.append((dotted, current, desired))
    return drift


def _authoritative_fields(local: dict, product: dict, revision: dict) -> List[Tuple[str, object]]:
    """The manifest paths + desired values that belong to the backend.

    Kept as an explicit allowlist so new fields don't silently sneak
    into the sync scope — every entry here is a deliberate policy call.
    """
    board_slug = _revision_slug(product, revision)

    # The fixture module reference we KNOW is correct for this board —
    # but only rewrite it if the author hasn't custom-named it (same
    # module prefix). Never clobber a bespoke class name.
    fx = (local.get("testbed") or {})
    module_ref = fx.get("module", "")
    expected_module_prefix = f"testbeds.{board_slug}.testbed:"
    desired_module = module_ref
    if not module_ref or ":" not in module_ref or not module_ref.startswith("fixtures."):
        # Fresh manifest — fill in a reasonable default.
        pkg_type = (local.get("package") or {}).get("type", "validation")
        suffix = "MfgTestBed" if pkg_type == "manufacturing" else "TestBed"
        board_class = "".join(p.capitalize() for p in board_slug.split("_"))
        desired_module = expected_module_prefix + f"{board_class}{suffix}"
    elif not module_ref.startswith(expected_module_prefix):
        # Board changed under us; move the class name across but keep
        # the part after ``:`` (the author's class name) intact.
        last = module_ref.split(":", 1)[1]
        desired_module = expected_module_prefix + last

    return [
        ("product.slug", product["slug"]),
        ("product.board", board_slug),
        ("product.device.type_id", revision.get("deviceType") if revision.get("deviceType") is not None else (local.get("product", {}).get("device", {}) or {}).get("type_id", 0)),
        ("product.device.variant_id", revision.get("deviceVariant") if revision.get("deviceVariant") is not None else (local.get("product", {}).get("device", {}) or {}).get("variant_id", 0)),
        ("fixture.module", desired_module),
    ]


def _deep_get(d: dict, parts: List[str]):
    cur = d
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _deep_set(d: dict, parts: List[str], value) -> None:
    cur = d
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _apply_manifest_diff(local: dict, diff: List[Tuple[str, object, object]]) -> None:
    for dotted, _before, after in diff:
        _deep_set(local, dotted.split("."), after)


# ═════════════════════════════════════════════════════════════════════════
# Drift warning — non-fatal, surfaced by validate / run / upload
# ═════════════════════════════════════════════════════════════════════════


def _warn_if_drifted(ctx, project_dir: Path) -> None:
    """Surface a one-liner if the local manifest has drifted from the backend.

    Never fails the command — the operator may be intentionally running
    against a stale manifest (e.g. reproducing a bug). We just make the
    drift impossible to miss.
    """
    manifest_path = project_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return
    local = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    slug = (local.get("product") or {}).get("slug")
    if not slug:
        return

    try:
        api = _client(ctx)
    except SystemExit:
        # Not authed — skip silently. ``corectl auth login`` will surface it elsewhere.
        return

    try:
        product, revision = _fetch_product_and_revision(api, slug, local)
    except SystemExit:
        return  # Backend disagreement is louder surfaced via explicit `sync`.

    diff = _diff_manifest(local, product, revision)
    if not diff:
        return
    summary = "; ".join(f"{p}: {b!r}→{a!r}" for p, b, a in diff[:3])
    extra = f" (+{len(diff) - 3} more)" if len(diff) > 3 else ""
    click.echo(
        click.style(
            f"  ⚠ manifest drifted from backend ({summary}{extra}). "
            f"Run 'corectl test sync' to update.",
            fg="yellow",
        ),
        err=True,
    )


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.pass_context
def validate(ctx, path: str, strict: bool):
    """Validate a test project — structure, semantics, and compatibility.

    Three validation levels:
      Level 1 (Structure): Files exist, directories match manifest (+ JSON Schema)
      Level 2 (Semantics): Profiles valid, markers defined, IDs set
      Level 3 (Compatibility): Framework version, build labels, pytest collection
    """
    project_dir = Path(path).resolve()
    result = ValidationResult()

    if not (project_dir / MANIFEST_NAME).exists():
        click.echo(f"No {MANIFEST_NAME} found in {project_dir}", err=True)
        raise SystemExit(1)

    click.echo(f"Validating: {project_dir.name}/")
    click.echo()

    # Level 1
    click.echo("Structure:")
    manifest = _validate_structure_v2(project_dir, result)

    # Level 2 (only if structure passed)
    if manifest:
        click.echo()
        click.echo("Semantics:")
        _validate_semantics(project_dir, manifest, result)

    # Level 3 (only if semantics passed)
    if manifest and not result.errors:
        click.echo()
        click.echo("Compatibility:")
        _validate_compatibility(project_dir, manifest, result)

    # Framework artifacts — must be present, version-matched, and unmodified.
    # Runs whenever a manifest exists; failures here block uploads platform-side.
    if manifest:
        click.echo()
        click.echo("Framework artifacts:")
        _validate_framework_artifacts(project_dir, manifest, result)

    # Non-fatal drift check against the backend.
    _warn_if_drifted(ctx, project_dir)

    # Report
    click.echo()
    for msg in result.info:
        click.echo(click.style(f"  ✓ {msg}", fg="green"))
    for msg in result.warnings:
        click.echo(click.style(f"  ⚠ {msg}", fg="yellow"))
    for msg in result.errors:
        click.echo(click.style(f"  ✗ {msg}", fg="red"))

    click.echo()
    if result.errors:
        click.echo(click.style(f"FAILED — {len(result.errors)} errors, {len(result.warnings)} warnings", fg="red"))
        raise SystemExit(1)
    elif result.warnings and strict:
        click.echo(click.style(f"FAILED (strict) — {len(result.warnings)} warnings", fg="yellow"))
        raise SystemExit(1)
    else:
        click.echo(click.style(
            f"PASSED — {len(result.info)} checks, {len(result.warnings)} warnings",
            fg="green",
        ))


@test.command()
@click.argument("stage")
@click.option("--marker", "-m", default=None, help="Pytest marker filter")
@click.option("--timeout", "-t", default=30, type=int, help="Per-test timeout")
@click.argument("path", default=".", required=False)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def run(ctx, stage: str, marker: Optional[str], timeout: int, path: str, verbose: bool):
    """Run tests for a specific stage.

    Examples:
        corectl test run smoke
        corectl test run regression --marker health_check
        corectl test run fuota -m "not fuota_full" -t 900
    """
    project_dir = Path(path).resolve()
    stage_dir = project_dir / "tests" / stage

    if not stage_dir.is_dir():
        click.echo(f"Stage not found: tests/{stage}/", err=True)
        raise SystemExit(1)

    # Surface drift before we burn time spinning up fixtures against a
    # stale manifest. Non-fatal — the operator can still proceed.
    _warn_if_drifted(ctx, project_dir)

    cmd = [sys.executable, "-m", "pytest", f"tests/{stage}/", f"--timeout={timeout}"]
    if verbose:
        cmd.append("-v")
    if marker:
        cmd.extend(["-m", marker])

    click.echo(f"Running {stage} tests...")
    result = subprocess.run(cmd, cwd=str(project_dir))
    raise SystemExit(result.returncode)


@test.command()
@click.argument("path", default=".", required=False)
def package(path: str):
    """Package test project into a tar.gz for upload.

    Creates a .tar.gz file containing the test code, manifest, fixtures,
    and configuration. Excludes caches, logs, .env, and other non-essential files.
    """
    import tarfile
    import hashlib

    project_dir = Path(path).resolve()
    manifest_path = _find_manifest_path(project_dir)

    manifest = _load_manifest_yaml(manifest_path)

    slug = _get_slug(manifest)
    version = _get_version(manifest)
    pkg_type = _get_package_type(manifest).lower()

    output_name = f"{slug}-{pkg_type}-{version}.tar.gz"
    output_path = project_dir / "dist" / output_name
    output_path.parent.mkdir(exist_ok=True)

    # Files to exclude
    excludes = {
        "__pycache__", ".pytest_cache", ".mypy_cache", "logs", "dist",
        ".git", ".env", "node_modules", ".vscode", ".idea",
    }

    def should_include(fpath: str) -> bool:
        parts = Path(fpath).parts
        return not any(part in excludes for part in parts) and not fpath.endswith(".pyc")

    with tarfile.open(str(output_path), "w:gz") as tar:
        for item in sorted(project_dir.rglob("*")):
            rel = item.relative_to(project_dir)
            if should_include(str(rel)) and item.is_file():
                tar.add(str(item), arcname=str(rel))

    # Calculate hash
    sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()[:12]

    size_kb = output_path.stat().st_size / 1024
    click.echo(f"Packaged: {output_name} ({size_kb:.1f} KB, sha256:{sha256})")
    click.echo(f"  Product: {slug}")
    click.echo(f"  Version: {version}")
    click.echo(f"  Type: {pkg_type}")
    click.echo(f"  Path: {output_path}")


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--release", "auto_release", is_flag=True, help="Upload and release in one step (auto-versioned)")
@click.pass_context
def upload(ctx, path: str, auto_release: bool):
    """Upload test package to Concord platform as a development version.

    Auto-generates version from git SHA + timestamp for uniqueness.
    Use --release to upload and promote to released in one step.

    Examples:
        corectl upload                     # dev-abc12345-1713100800
        corectl upload --release           # upload + auto-release
    """
    import tarfile
    import hashlib

    api = _client(ctx)

    project_dir = Path(path).resolve()
    manifest_path = _find_manifest_path(project_dir)

    manifest = _load_manifest_yaml(manifest_path)

    slug = _get_slug(manifest)

    # Surface backend drift BEFORE packaging + uploading — an upload is
    # the costliest pre-run action (network, tarball, server parse), so
    # it's the spot where a drift warning is most useful.
    _warn_if_drifted(ctx, project_dir)

    # ── Pre-upload validation ──
    click.echo("Pre-upload validation...")
    pre_result = ValidationResult()
    _validate_structure_v2(project_dir, pre_result)
    if manifest:
        _validate_semantics(project_dir, manifest, pre_result)

    if pre_result.errors:
        click.echo()
        for msg in pre_result.errors:
            click.echo(click.style(f"  ✗ {msg}", fg="red"))
        for msg in pre_result.warnings:
            click.echo(click.style(f"  ⚠ {msg}", fg="yellow"))
        click.echo()
        click.echo(click.style(
            f"Upload blocked — {len(pre_result.errors)} validation error(s). "
            "Run 'corectl test validate' for details.",
            fg="red",
        ))
        raise SystemExit(1)

    if pre_result.warnings:
        for msg in pre_result.warnings:
            click.echo(click.style(f"  ⚠ {msg}", fg="yellow"))
        click.echo()

    click.echo(click.style("  ✓ Validation passed", fg="green"))
    click.echo()

    # Collect git state for traceability
    git_sha = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, cwd=str(project_dir),
        )
        git_sha = result.stdout.strip()
    except Exception:
        pass

    # Every dev upload is its own immutable row — git SHA + epoch suffix.
    # Dropping the clean-tree shortcut means a re-upload of the same SHA
    # always produces a distinct version, so a TestRun's package
    # reference can never be silently overwritten by a later upload.
    import time as _time
    sha = git_sha or "unknown"
    version = f"dev-{sha}-{int(_time.time())}"

    # Prompt for upload message
    upload_message = click.prompt(
        f"Upload message [{git_sha}]",
        default="",
        show_default=False,
    ).strip()

    status = "DEVELOPMENT"
    package_type = _get_package_type(manifest)

    click.echo(f"Uploading {slug}@{version} ({status}, {package_type})...")

    # Package the project
    excludes = {
        "__pycache__", ".pytest_cache", ".mypy_cache", "logs", "dist",
        ".git", ".env", "node_modules", ".vscode", ".idea",
    }

    import io
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in sorted(project_dir.rglob("*")):
            rel = item.relative_to(project_dir)
            parts = set(rel.parts)
            if not parts.intersection(excludes) and item.is_file() and not str(rel).endswith(".pyc"):
                tar.add(str(item), arcname=str(rel))
    package_bytes = buf.getvalue()

    # Calculate manifest hash
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    # Upload to Concord API
    import json as json_mod

    upload_manifest = {
        "version": version,
        "type": package_type,
        "status": status,
        "frameworkVersion": _get_framework(manifest),
        "productSlug": slug,
        "manifestHash": manifest_hash,
        "manifestVersion": manifest.get("schema", "1.0"),
        "testCount": 0,  # Backend can override from collection
        "message": upload_message,
        "gitSha": git_sha,
    }

    resp = api.post(
        f"/v2/products/{slug}/test-packages",
        files={"package": (f"{slug}-{version}.tar.gz", package_bytes, "application/gzip")},
        data={"manifest": json_mod.dumps(upload_manifest)},
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        package_id = data.get("id", "unknown")
        click.echo(click.style(f"Uploaded: {slug}@{version}", fg="green"))
        click.echo(f"  ID: {package_id}")
        click.echo(f"  Status: {status}")
        click.echo(f"  Type: {package_type}")
        click.echo(f"  Tests: {data.get('testCount', '?')}")

        # Auto-release if --release flag was passed
        if auto_release and package_id != "unknown":
            release_resp = api.post(
                f"/v2/products/{slug}/test-packages/{package_id}/release",
            )
            if release_resp.status_code in (200, 201):
                rel_data = release_resp.json().get("data", {})
                rel_ver = rel_data.get("releasedVersion", rel_data.get("version", version))
                click.echo(click.style(f"  Released as {rel_ver}", fg="green"))
            else:
                click.echo(click.style(
                    f"  Release failed: HTTP {release_resp.status_code} — {release_resp.text[:200]}",
                    fg="yellow",
                ), err=True)
    elif resp.status_code == 409:
        click.echo(click.style(
            f"Version {version} already exists. Re-run to generate a new dev version.",
            fg="red",
        ), err=True)
        raise SystemExit(1)
    else:
        click.echo(click.style(
            f"Upload failed: HTTP {resp.status_code} — {resp.text[:200]}",
            fg="red",
        ), err=True)
        raise SystemExit(1)


@test.command()
@click.argument("package_id", required=False)
@click.option("--version", "dev_version", default=None, help="Dev version to release (e.g., dev-abc12345)")
@click.option("--type", "pkg_type", type=click.Choice(["validation", "manufacturing"]), default=None, help="Package type")
@click.option("--path", "project_path", type=click.Path(exists=True), default=None, help="Project path (to read product slug)")
@click.pass_context
def release(ctx, package_id, dev_version, pkg_type, project_path):
    """Promote a development test package to released.

    The platform auto-assigns the next semver version.

    Usage:
      corectl test release <package-id>
      corectl test release --version dev-abc12345
    """
    api = _client(ctx)

    # Resolve product slug from manifest
    manifest_dir = Path(project_path) if project_path else Path(".")
    manifest_dir = manifest_dir.resolve()
    manifest_path = _find_manifest_path(manifest_dir)
    manifest = _load_manifest_yaml(manifest_path)
    slug = _get_slug(manifest)

    if package_id:
        # Direct ID — use it
        pass
    elif dev_version:
        # Find the package by dev version
        query = f"/v2/products/{slug}/test-packages?status=DEVELOPMENT"
        if pkg_type:
            query += f"&type={pkg_type.upper()}"
        resp = api.get(query)
        if not resp.ok:
            click.echo(f"Failed to list packages: HTTP {resp.status_code}", err=True)
            raise SystemExit(1)

        response_data = resp.json().get("data", {})
        packages = response_data.get("data", []) if isinstance(response_data, dict) else response_data
        match = [p for p in packages if p["version"] == dev_version]
        if not match:
            click.echo(f"No DEVELOPMENT package with version '{dev_version}' found for {slug}", err=True)
            raise SystemExit(1)
        package_id = match[0]["id"]
    else:
        # Interactive — show latest dev packages and prompt
        resp = api.get(f"/v2/products/{slug}/test-packages?status=DEVELOPMENT")
        if not resp.ok:
            click.echo(f"Failed to list packages: HTTP {resp.status_code}", err=True)
            raise SystemExit(1)

        response_data = resp.json().get("data", {})
        packages = response_data.get("data", []) if isinstance(response_data, dict) else response_data
        dev_packages = [p for p in packages if p["status"] == "DEVELOPMENT"]
        if not dev_packages:
            click.echo(f"No DEVELOPMENT packages found for {slug}", err=True)
            raise SystemExit(1)

        click.echo(f"Development packages for {slug}:")
        for i, pkg in enumerate(dev_packages, 1):
            ver = pkg["version"].ljust(20)
            pkg_t = pkg.get("type", "?").ljust(15)
            date = str(pkg.get("createdAt", ""))[:10]
            click.echo(f"  [{i}] {ver} {pkg_t} {date}")

        choice = click.prompt("Select package to release", type=int)
        if choice < 1 or choice > len(dev_packages):
            click.echo("Invalid selection", err=True)
            raise SystemExit(1)
        package_id = dev_packages[choice - 1]["id"]

    # Promote the package
    resp = api.post(
        f"/v2/products/{slug}/test-packages/{package_id}/release",
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        released_version = data.get("releasedVersion", data.get("version", "?"))
        click.echo(click.style(f"Released as version {released_version}", fg="green"))
    elif resp.status_code == 404:
        click.echo(click.style("Package not found", fg="red"), err=True)
        raise SystemExit(1)
    elif resp.status_code == 409:
        click.echo(click.style("Package is already released", fg="red"), err=True)
        raise SystemExit(1)
    elif resp.status_code == 400:
        detail = resp.json().get("message", resp.text[:200])
        click.echo(click.style(f"Cannot release — {detail}", fg="red"), err=True)
        raise SystemExit(1)
    else:
        click.echo(click.style(
            f"Release failed: HTTP {resp.status_code} — {resp.text[:200]}",
            fg="red",
        ), err=True)
        raise SystemExit(1)


@test.command()
@click.argument("path", default=".", required=False)
@click.pass_context
def versions(ctx, path: str):
    """List published test package versions for this product."""
    api = _client(ctx)

    project_dir = Path(path).resolve()
    manifest_path = _find_manifest_path(project_dir)

    manifest = _load_manifest_yaml(manifest_path)
    slug = _get_slug(manifest)

    resp = api.get(f"/v2/products/{slug}/test-packages")

    if not resp.ok:
        click.echo(f"Failed to list versions: HTTP {resp.status_code}", err=True)
        raise SystemExit(1)

    response_data = resp.json().get("data", {})
    packages = response_data.get("data", []) if isinstance(response_data, dict) else response_data
    if not packages:
        click.echo(f"No test packages published for {slug}")
        return

    click.echo(f"Test packages for {slug}:")
    for pkg in packages:
        status_color = "green" if pkg["status"] == "RELEASED" else "yellow"
        ver = pkg["version"].ljust(15)
        status = pkg["status"].ljust(12)
        tests = str(pkg.get("testCount", "?")).rjust(3)
        date = str(pkg.get("createdAt", ""))[:10]
        click.echo(f"  {click.style(ver, fg=status_color)} {status} {tests} tests  {date}")
