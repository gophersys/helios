"""corectl test — validation test management commands.

Usage:
    corectl test init --product sigma5 --board sigma5_a0
    corectl test validate [--path .] [--strict]
    corectl test run smoke [--timeout 30]
    corectl test run nightly --marker health_check
    corectl test package
    corectl test upload --env staging
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import click
import yaml

from ..config import get_api_url, get_tls_verify, require_auth
from ..api import ConcordAPI


MANIFEST_NAME = "concord.test.yaml"

# Standard stage directories — convention, not configuration
STANDARD_STAGES = ["smoke", "silicon", "integration", "nightly", "fuota"]

# Required files in a valid test project
REQUIRED_FILES = [
    "concord.test.yaml",
    "conftest.py",
    "pytest.ini",
]


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


def _validate_structure(project_dir: Path, result: ValidationResult) -> dict:
    """Level 1: Does the project look right?"""

    # Required files
    for filename in REQUIRED_FILES:
        if (project_dir / filename).exists():
            result.ok(f"{filename}")
        else:
            result.error(f"Missing: {filename}")

    # pyproject.toml (recommended, not required)
    if (project_dir / "pyproject.toml").exists():
        result.ok("pyproject.toml")
    else:
        result.warn("No pyproject.toml — needed for standalone installation")

    # Manifest
    manifest = {}
    manifest_path = project_dir / MANIFEST_NAME
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or {}

    if not manifest:
        result.error(f"{MANIFEST_NAME} is empty or invalid YAML")
        return manifest

    # Required manifest fields
    for field in ["version", "framework", "product"]:
        if field not in manifest:
            result.error(f"Manifest missing '{field}' field")

    product = manifest.get("product", {})
    for field in ["name", "board"]:
        if field not in product:
            result.error(f"Manifest product missing '{field}' field")

    # Stage directories
    stages = manifest.get("stages", {})
    enabled_count = 0
    for stage_name, enabled in stages.items():
        if stage_name not in STANDARD_STAGES:
            result.warn(f"Non-standard stage: '{stage_name}'")
        if enabled:
            enabled_count += 1
            stage_dir = project_dir / "tests" / stage_name
            if stage_dir.is_dir():
                test_files = list(stage_dir.glob("test_*.py"))
                if test_files:
                    result.ok(f"tests/{stage_name}/ ({len(test_files)} test files)")
                else:
                    result.warn(f"tests/{stage_name}/ has no test files")
            else:
                result.error(f"Stage '{stage_name}' enabled but tests/{stage_name}/ missing")

    if enabled_count == 0:
        result.error("No stages enabled in manifest")

    # Fixture profiles — check for YAML (new) and JSON (legacy)
    fixtures_dir = project_dir / "fixtures"
    if fixtures_dir.is_dir():
        yaml_profiles = list(fixtures_dir.glob("*/fixture.yaml"))
        json_profiles = list(fixtures_dir.glob("*.json"))
        total = len(yaml_profiles) + len(json_profiles)
        if total:
            result.ok(f"fixtures/ ({total} profiles)")
        else:
            result.warn("fixtures/ has no profiles (*.json or */fixture.yaml)")
    else:
        result.warn("No fixtures/ directory")

    return manifest


def _validate_semantics(project_dir: Path, manifest: dict, result: ValidationResult) -> None:
    """Level 2: Does the project make sense?"""

    product = manifest.get("product", {})

    # Device type/variant should be non-zero for real products
    dt = product.get("device_type_id", 0)
    dv = product.get("device_variant_id", 0)
    if dt == 0 or dv == 0:
        result.warn(f"Device type={dt}, variant={dv} — set these for production use")

    # Validate fixture profiles (JSON legacy + YAML new)
    fixtures_dir = project_dir / "fixtures"
    if fixtures_dir.is_dir():
        # JSON profiles (legacy)
        for profile_path in fixtures_dir.glob("*.json"):
            try:
                import json
                with open(profile_path) as f:
                    profile_data = json.load(f)
                if "capabilities" not in profile_data:
                    result.warn(f"{profile_path.name}: missing capabilities list")
                if "power" not in profile_data:
                    result.warn(f"{profile_path.name}: missing power config")
            except Exception as exc:
                result.error(f"{profile_path.name}: invalid JSON -- {exc}")

        # YAML profiles (new pattern: fixtures/<name>/fixture.yaml)
        for yaml_path in fixtures_dir.glob("*/fixture.yaml"):
            try:
                with open(yaml_path) as f:
                    profile_data = yaml.safe_load(f)
                if not profile_data:
                    result.error(f"{yaml_path}: empty YAML")
                    continue
                if "capabilities" not in profile_data:
                    result.warn(f"{yaml_path.parent.name}/fixture.yaml: missing capabilities list")
                if "power" not in profile_data:
                    result.warn(f"{yaml_path.parent.name}/fixture.yaml: missing power config")
                else:
                    result.ok(f"{yaml_path.parent.name}/fixture.yaml passes basic validation")
            except Exception as exc:
                result.error(f"{yaml_path.parent.name}/fixture.yaml: invalid YAML -- {exc}")

    # Check pytest markers in pytest.ini
    pytest_ini = project_dir / "pytest.ini"
    if pytest_ini.exists():
        ini_content = pytest_ini.read_text()
        stages = manifest.get("stages", {})

        if stages.get("nightly") and "health_check" not in ini_content:
            result.warn("Nightly enabled but 'health_check' marker not in pytest.ini")
        if stages.get("fuota") and "fuota_fast" not in ini_content:
            result.warn("FUOTA enabled but 'fuota_fast' marker not in pytest.ini")


def _validate_compatibility(project_dir: Path, manifest: dict, result: ValidationResult) -> None:
    """Level 3: Will it work with the platform?"""

    # Check framework version
    required_version = manifest.get("framework", "")
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

    # Check stage build labels
    try:
        from corekinect.stages import get_required_labels, Stage

        stages = manifest.get("stages", {})
        for stage_name, enabled in stages.items():
            if not enabled:
                continue
            try:
                stage = Stage(stage_name)
                labels = get_required_labels(stage)
                result.ok(f"{stage_name} requires {len(labels)} builds: {labels}")
            except (ValueError, KeyError):
                pass  # Non-standard stage, skip
    except ImportError:
        pass  # Framework not installed

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
    """Manage validation test projects."""
    pass


@test.command()
@click.option("--product", prompt="Product name", help="Product name (e.g., sigma5)")
@click.option("--board", prompt="Board name", help="Board revision (e.g., sigma5_a0)")
@click.argument("path", default=".", required=False)
def init(product: str, board: str, path: str):
    """Scaffold a new validation test project."""
    project_dir = Path(path)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (project_dir / "fixtures").mkdir(exist_ok=True)
    (project_dir / "scripts").mkdir(exist_ok=True)
    (project_dir / "deploy").mkdir(exist_ok=True)
    (project_dir / "tests" / "common").mkdir(parents=True, exist_ok=True)

    for stage in STANDARD_STAGES:
        stage_dir = project_dir / "tests" / stage
        stage_dir.mkdir(exist_ok=True)
        (stage_dir / "__init__.py").touch()
        (stage_dir / "conftest.py").write_text(
            f'"""Stage {STANDARD_STAGES.index(stage) + 1}: {stage.title()} tests."""\n'
        )

    # Create manifest
    manifest = {
        "version": 1,
        "framework": ">=0.2.0",
        "product": {
            "name": product,
            "board": board,
            "device_type_id": 0,
            "device_variant_id": 0,
        },
        "stages": {stage: (stage in ["smoke", "nightly", "fuota"]) for stage in STANDARD_STAGES},
    }
    (project_dir / MANIFEST_NAME).write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False)
    )

    # Create basic files
    (project_dir / "tests" / "__init__.py").touch()
    (project_dir / "tests" / "common" / "__init__.py").touch()

    (project_dir / "pytest.ini").write_text(
        f"[pytest]\ntestpaths = tests\npython_files = test_*.py\n\n"
        f"markers =\n"
        f"    health_check: fast post-FUOTA verification tests\n"
        f"    fuota_fast: fast FUOTA gate test\n"
        f"    fuota_full: comprehensive FUOTA tests\n"
        f"    corecloud: requires CoreCloud connectivity\n"
        f"    gnss: requires GPS signal\n"
    )

    (project_dir / "pyproject.toml").write_text(
        f'[project]\nname = "concord-validation-{product}"\n'
        f'version = "0.1.0"\n'
        f'dependencies = ["corekinect>=0.2.0"]\n'
    )

    (project_dir / "conftest.py").write_text(
        f'"""Root pytest fixtures for {product} validation tests.\n\n'
        f'See the Alpha validation app for reference patterns.\n'
        f'"""\n'
    )

    click.echo(f"Created {product} validation project:")
    click.echo(f"  {MANIFEST_NAME}")
    click.echo(f"  tests/ with {sum(1 for s in manifest['stages'].values() if s)} enabled stages")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Set device_type_id and device_variant_id in {MANIFEST_NAME}")
    click.echo(f"  2. Create fixtures/{product}_{board}.json")
    click.echo(f"  3. Write tests in tests/smoke/")
    click.echo(f"  4. corectl test validate")


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
def validate(path: str, strict: bool):
    """Validate a test project — structure, semantics, and compatibility.

    Three validation levels:
      Level 1 (Structure): Files exist, directories match manifest
      Level 2 (Semantics): Profiles valid, markers defined, IDs set
      Level 3 (Compatibility): Framework version, build labels, pytest collection
    """
    project_dir = Path(path).resolve()
    result = ValidationResult()

    click.echo(f"Validating: {project_dir.name}/")
    click.echo()

    # Level 1
    click.echo("Structure:")
    manifest = _validate_structure(project_dir, result)

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
def run(stage: str, marker: Optional[str], timeout: int, path: str, verbose: bool):
    """Run tests for a specific stage.

    Examples:
        corectl test run smoke
        corectl test run nightly --marker health_check
        corectl test run fuota -m "not fuota_full" -t 900
    """
    project_dir = Path(path).resolve()
    stage_dir = project_dir / "tests" / stage

    if not stage_dir.is_dir():
        click.echo(f"Stage not found: tests/{stage}/", err=True)
        raise SystemExit(1)

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
    manifest_path = project_dir / MANIFEST_NAME

    if not manifest_path.exists():
        click.echo(f"{MANIFEST_NAME} not found", err=True)
        raise SystemExit(1)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    product = manifest.get("product", {})
    slug = product.get("name", "unknown")
    version = manifest.get("test_version", "dev")

    output_name = f"{slug}-validation-{version}.tar.gz"
    output_path = project_dir / "dist" / output_name
    output_path.parent.mkdir(exist_ok=True)

    # Files to exclude
    excludes = {
        "__pycache__", ".pytest_cache", ".mypy_cache", "logs", "dist",
        ".git", ".env", "node_modules", ".vscode", ".idea",
    }

    def should_include(path: str) -> bool:
        parts = Path(path).parts
        return not any(part in excludes for part in parts) and not path.endswith(".pyc")

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
    click.echo(f"  Path: {output_path}")


@test.command()
@click.option("--release", is_flag=True, help="Upload as immutable release (uses test_version from manifest)")
@click.option("--version", "version_override", default=None, help="Explicit version override")
@click.argument("path", default=".", required=False)
@click.pass_context
def upload(ctx, release: bool, version_override: Optional[str], path: str):
    """Upload test package to Concord platform.

    Development uploads (default):
        Auto-generates version from git SHA. Mutable — overwrites previous.

    Release uploads (--release):
        Uses test_version from concord.test.yaml. Immutable — cannot overwrite.

    Examples:
        corectl test upload                    # dev-abc12345
        corectl test upload --release          # 1.2.0 (from manifest)
        corectl test upload --version 1.3.0    # explicit override
    """
    import tarfile
    import hashlib

    config = ctx.obj["config"]
    token = require_auth(config)
    api_url = get_api_url(config)

    project_dir = Path(path).resolve()
    manifest_path = project_dir / MANIFEST_NAME

    if not manifest_path.exists():
        click.echo(f"{MANIFEST_NAME} not found — run 'corectl test init' first", err=True)
        raise SystemExit(1)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    product = manifest.get("product", {})
    slug = product.get("name", "unknown")

    # Determine version
    if version_override:
        version = version_override
    elif release:
        version = manifest.get("test_version")
        if not version:
            click.echo("No test_version in manifest — set it or use --version", err=True)
            raise SystemExit(1)
    else:
        # Development version from git SHA
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short=8", "HEAD"],
                capture_output=True, text=True, cwd=str(project_dir),
            )
            sha = result.stdout.strip() or "unknown"
        except Exception:
            sha = "unknown"
        version = f"dev-{sha}"

    status = "RELEASED" if release else "DEVELOPMENT"

    click.echo(f"Uploading {slug}@{version} ({status})...")

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
    import requests

    api = ConcordAPI(api_url, token, tls_verify=get_tls_verify(ctx.obj["config"]))

    import json as json_mod

    upload_manifest = {
        "version": version,
        "status": status,
        "frameworkVersion": manifest.get("framework", "unknown"),
        "productSlug": slug,
        "manifestHash": manifest_hash,
        "stagesEnabled": manifest.get("stages", {}),
        "testCount": 0,  # Backend can override from collection
    }

    resp = requests.post(
        f"{api_url}/v2/products/{slug}/test-packages",
        headers={"Authorization": f"ApiKey {token}"},
        files={"package": (f"{slug}-{version}.tar.gz", package_bytes, "application/gzip")},
        data={"manifest": json_mod.dumps(upload_manifest)},
        verify=False,  # Self-signed certs in staging
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        click.echo(click.style(f"Uploaded: {slug}@{version}", fg="green"))
        click.echo(f"  ID: {data.get('id', 'unknown')}")
        click.echo(f"  Status: {status}")
        click.echo(f"  Tests: {data.get('testCount', '?')}")
    elif resp.status_code == 409:
        click.echo(click.style(
            f"Version {version} already exists and is RELEASED (immutable). "
            f"Bump test_version in {MANIFEST_NAME} or use a different version.",
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
@click.argument("path", default=".", required=False)
@click.pass_context
def versions(ctx, path: str):
    """List published test package versions for this product."""
    config = ctx.obj["config"]
    token = require_auth(config)
    api_url = get_api_url(config)

    project_dir = Path(path).resolve()
    manifest_path = project_dir / MANIFEST_NAME

    if not manifest_path.exists():
        click.echo(f"{MANIFEST_NAME} not found", err=True)
        raise SystemExit(1)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    product = manifest.get("product", {})
    slug = product.get("name", "unknown")

    api = ConcordAPI(api_url, token, tls_verify=get_tls_verify(ctx.obj["config"]))
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
