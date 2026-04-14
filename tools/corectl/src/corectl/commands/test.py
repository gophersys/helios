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
    corectl test migrate
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
import yaml

from ..config import get_api_url, get_tls_verify, require_auth
from ..api import ConcordAPI


MANIFEST_NAME = "concord.yaml"
LEGACY_MANIFEST_NAME = "concord.test.yaml"

# Standard stage directories — convention, not configuration
STANDARD_STAGES = ["smoke", "driver", "integration", "regression", "fuota"]
MANUFACTURING_STAGES = ["manufacturing"]
ALL_STAGES = STANDARD_STAGES + MANUFACTURING_STAGES

# Required files in a valid test project (v2)
# pytest config can live in pytest.ini OR pyproject.toml
REQUIRED_FILES_V2 = [
    "concord.yaml",
    "conftest.py",
]

# Required files for legacy v1 projects
REQUIRED_FILES_V1 = [
    "concord.test.yaml",
    "conftest.py",
]

# Try to import the manifest library (optional — not always installed)
try:
    from corekinect.manifest.loader import load_manifest, find_manifest, load_manifest_raw
    from corekinect.manifest.schema import validate_manifest as schema_validate_manifest
    from corekinect.manifest.types import Manifest

    HAS_MANIFEST_LIB = True
except ImportError:
    HAS_MANIFEST_LIB = False


def _find_manifest_path(project_dir: Path) -> Tuple[Path, bool]:
    """Find the manifest file in project_dir.

    Returns (path, is_v2) — looks for concord.yaml first, then concord.test.yaml.
    Raises SystemExit if neither is found.
    """
    v2_path = project_dir / MANIFEST_NAME
    if v2_path.exists():
        return v2_path, True

    v1_path = project_dir / LEGACY_MANIFEST_NAME
    if v1_path.exists():
        return v1_path, False

    click.echo(f"No {MANIFEST_NAME} or {LEGACY_MANIFEST_NAME} found", err=True)
    raise SystemExit(1)


def _load_manifest_yaml(manifest_path: Path) -> dict:
    """Load a manifest file as a raw dict."""
    with open(manifest_path) as f:
        data = yaml.safe_load(f) or {}
    return data


def _warn_legacy():
    """Print a migration warning for v1 manifests."""
    click.echo(click.style(
        f"  ⚠ Using legacy {LEGACY_MANIFEST_NAME} — run 'corectl test migrate' to upgrade to {MANIFEST_NAME}",
        fg="yellow",
    ))


def _get_slug(manifest: dict, is_v2: bool) -> str:
    """Extract the product slug from a manifest dict."""
    if is_v2:
        return manifest.get("product", {}).get("slug", "unknown")
    return manifest.get("product", {}).get("name", "unknown")


def _get_version(manifest: dict, is_v2: bool) -> str:
    """Extract the package version from a manifest dict."""
    if is_v2:
        return manifest.get("package", {}).get("version", "0.0.0")
    return manifest.get("test_version", manifest.get("version", "dev"))


def _get_framework(manifest: dict, is_v2: bool) -> str:
    """Extract the framework constraint from a manifest dict."""
    if is_v2:
        return manifest.get("package", {}).get("framework", "unknown")
    return manifest.get("framework", "unknown")


def _get_package_type(manifest: dict, is_v2: bool) -> str:
    """Extract or detect the package type."""
    if is_v2:
        return manifest.get("package", {}).get("type", "validation").upper()
    # v1: auto-detect from stages
    stages = manifest.get("stages", {})
    has_manufacturing = stages.get("manufacturing", False)
    has_validation = any(stages.get(s, False) for s in STANDARD_STAGES)
    if has_manufacturing and not has_validation:
        return "MANUFACTURING"
    return "VALIDATION"


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
    for filename in REQUIRED_FILES_V2:
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
        steps = manifest.get("steps", []) or manifest.get("stages", {})
        if not steps:
            result.error("No steps/stages defined in manifest")
        if isinstance(steps, list):
            for step in steps:
                module = step.get("module", "")
                # Verify the module file exists
                module_path = module.replace(".", "/") + ".py"
                if (project_dir / module_path).exists():
                    result.ok(f"Step: {step.get('name', '?')} -> {module}")
                else:
                    result.error(f"Step '{step.get('name', '?')}' module not found: {module_path}")
        elif isinstance(steps, dict):
            for stage_name, stage_cfg in steps.items():
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

    # Fixture profile
    fixture = manifest.get("fixture", {})
    profile_path = fixture.get("profile", "")
    if profile_path:
        full_path = project_dir / profile_path
        if full_path.exists():
            result.ok(f"Fixture profile: {profile_path}")
            # Validate fixture YAML content
            try:
                with open(full_path) as f:
                    profile_data = yaml.safe_load(f)
                if not profile_data:
                    result.error(f"Fixture profile is empty: {profile_path}")
                else:
                    if "power" not in profile_data:
                        result.error(f"Fixture profile missing 'power' config: {profile_path}")
                    else:
                        result.ok(f"Fixture profile has power config")
            except Exception as exc:
                result.error(f"Fixture profile invalid YAML: {exc}")
        else:
            result.error(f"Fixture profile not found: {profile_path}")

    # Fixture controller
    controller = fixture.get("controller", "")
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
                    result.ok(f"Fixture controller: {controller}")
                else:
                    result.error(f"Fixture controller class '{class_name}' not found in {module_path}")
            else:
                result.error(f"Fixture controller module not found: {module_path}")

    # Timeout sanity checks
    for stage_name, stage_cfg in (manifest.get("stages", {}) or {}).items():
        if isinstance(stage_cfg, dict):
            timeout = stage_cfg.get("timeout_s", 0)
            if timeout and (timeout < 5 or timeout > 14400):
                result.warn(f"Stage '{stage_name}' timeout {timeout}s outside reasonable range [5, 14400]")
    for step in (manifest.get("steps", []) or []):
        if isinstance(step, dict):
            timeout = step.get("timeout_s", 0)
            if timeout and (timeout < 5 or timeout > 14400):
                result.warn(f"Step '{step.get('name', '?')}' timeout {timeout}s outside reasonable range [5, 14400]")

    return manifest


def _validate_structure_v1(project_dir: Path, result: ValidationResult) -> dict:
    """Level 1 for v1 (legacy) manifests: original structure checks."""

    # Required files
    for filename in REQUIRED_FILES_V1:
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
    manifest_path = project_dir / LEGACY_MANIFEST_NAME
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or {}

    if not manifest:
        result.error(f"{LEGACY_MANIFEST_NAME} is empty or invalid YAML")
        return manifest

    # Required manifest fields
    for fld in ["version", "framework", "product"]:
        if fld not in manifest:
            result.error(f"Manifest missing '{fld}' field")

    product = manifest.get("product", {})
    for fld in ["name", "board"]:
        if fld not in product:
            result.error(f"Manifest product missing '{fld}' field")

    # Stage directories
    stages = manifest.get("stages", {})
    enabled_count = 0
    for stage_name, enabled in stages.items():
        if stage_name not in ALL_STAGES:
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


def _validate_semantics(project_dir: Path, manifest: dict, is_v2: bool, result: ValidationResult) -> None:
    """Level 2: Does the project make sense?"""

    product = manifest.get("product", {})

    if is_v2:
        device = product.get("device", {})
        dt = device.get("type_id", 0)
        dv = device.get("variant_id", 0)
    else:
        dt = product.get("device_type_id", 0)
        dv = product.get("device_variant_id", 0)

    if dt == 0 or dv == 0:
        result.warn(f"Device type={dt}, variant={dv} — set these for production use")

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
    if is_v2:
        fixture = manifest.get("fixture", {})
        pkg_type = manifest.get("package", {}).get("type", "validation")
        multi_slot = fixture.get("multi_slot", False)
        if pkg_type == "manufacturing" and not multi_slot:
            result.warn("Manufacturing package with multi_slot=false — most manufacturing fixtures are multi-slot")

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

    # Check pytest markers in pytest.ini or pyproject.toml
    pytest_ini = project_dir / "pytest.ini"
    pyproject = project_dir / "pyproject.toml"
    marker_content = ""
    if pytest_ini.exists():
        marker_content = pytest_ini.read_text()
    elif pyproject.exists():
        marker_content = pyproject.read_text()

    if marker_content:
        if is_v2:
            # v2: check markers declared in stage configs
            stages = manifest.get("stages", {})
            for stage_name, stage_cfg in stages.items():
                if isinstance(stage_cfg, dict):
                    for marker in stage_cfg.get("markers", []):
                        if marker not in marker_content:
                            result.warn(f"Stage '{stage_name}' uses marker '{marker}' not in pytest config")
        else:
            # v1: hardcoded marker checks
            stages = manifest.get("stages", {})
            if stages.get("regression") and "health_check" not in marker_content:
                result.warn("Regression enabled but 'health_check' marker not in pytest config")
            if stages.get("fuota") and "fuota_fast" not in marker_content:
                result.warn("FUOTA enabled but 'fuota_fast' marker not in pytest config")


def _validate_compatibility(project_dir: Path, manifest: dict, is_v2: bool, result: ValidationResult) -> None:
    """Level 3: Will it work with the platform?"""

    # Check framework version
    required_version = _get_framework(manifest, is_v2)
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

    # Check stage build labels (v1 only — v2 stages are self-describing)
    if not is_v2:
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
    """Manage validation and manufacturing test projects."""
    pass


@test.command()
@click.option("--product", prompt="Product name", help="Product name (e.g., sigma5)")
@click.option("--board", prompt="Board name", help="Board revision (e.g., sigma5_a0)")
@click.option("--type", "pkg_type", type=click.Choice(["validation", "manufacturing"]),
              default="validation", help="Package type (default: validation)")
@click.argument("path", default=".", required=False)
def init(product: str, board: str, pkg_type: str, path: str):
    """Scaffold a new test project (validation or manufacturing)."""
    project_dir = Path(path)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Board class name: alpha_b0 -> AlphaB0
    board_class = "".join(part.capitalize() for part in board.split("_"))

    if pkg_type == "manufacturing":
        _init_manufacturing(project_dir, product, board, board_class)
    else:
        _init_validation(project_dir, product, board, board_class)


def _init_validation(project_dir: Path, product: str, board: str, board_class: str):
    """Scaffold a validation test project with v2 manifest."""

    # Create directory structure
    (project_dir / "fixtures" / board).mkdir(parents=True, exist_ok=True)
    (project_dir / "scripts").mkdir(exist_ok=True)
    (project_dir / "deploy").mkdir(exist_ok=True)
    (project_dir / "tests" / "common").mkdir(parents=True, exist_ok=True)

    enabled_stages = ["smoke", "regression", "fuota"]
    for stage in enabled_stages:
        stage_dir = project_dir / "tests" / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "__init__.py").touch()
        (stage_dir / "conftest.py").write_text(
            f'"""Stage: {stage.title()} tests."""\n'
        )

    # Create v2 manifest as a formatted YAML string for readable output
    manifest_text = (
        f'schema: "2.0"\n'
        f'\n'
        f'package:\n'
        f'  type: validation\n'
        f'  version: "0.1.0"\n'
        f'  framework: ">=0.3.0"\n'
        f'\n'
        f'product:\n'
        f'  slug: {product}\n'
        f'  board: {board}\n'
        f'  device:\n'
        f'    type_id: 0\n'
        f'    variant_id: 0\n'
        f'\n'
        f'fixture:\n'
        f'  controller: fixtures.{board}.controller.{board_class}Fixture\n'
        f'  profile: fixtures/{board}/fixture.yaml\n'
        f'\n'
        f'stages:\n'
        f'  smoke:\n'
        f'    directory: tests/smoke\n'
        f'    timeout_s: 120\n'
        f'    hardware: [power]\n'
        f'  regression:\n'
        f'    directory: tests/regression\n'
        f'    timeout_s: 600\n'
        f'    hardware: [power]\n'
        f'  fuota:\n'
        f'    directory: tests/fuota\n'
        f'    timeout_s: 1800\n'
        f'    hardware: [power]\n'
    )
    (project_dir / MANIFEST_NAME).write_text(manifest_text)

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
        f'dependencies = ["corekinect>=0.3.0"]\n'
    )

    (project_dir / "conftest.py").write_text(
        'pytest_plugins = ["corekinect.test.autoconf"]\n'
    )

    click.echo(f"Created {product} validation project:")
    click.echo(f"  {MANIFEST_NAME}")
    click.echo(f"  tests/ with {len(enabled_stages)} stages: {', '.join(enabled_stages)}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Set device type_id and variant_id in {MANIFEST_NAME}")
    click.echo(f"  2. Create fixtures/{board}/fixture.yaml")
    click.echo(f"  3. Write tests in tests/smoke/")
    click.echo(f"  4. corectl test validate")


def _init_manufacturing(project_dir: Path, product: str, board: str, board_class: str):
    """Scaffold a manufacturing test project with v2 manifest."""

    # Create directory structure
    (project_dir / "fixtures" / board).mkdir(parents=True, exist_ok=True)
    (project_dir / "scripts").mkdir(exist_ok=True)
    (project_dir / "deploy").mkdir(exist_ok=True)
    (project_dir / "tests" / "manufacturing").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests" / "manufacturing" / "__init__.py").touch()

    # Create v2 manufacturing manifest
    manifest_text = (
        f'schema: "2.0"\n'
        f'\n'
        f'package:\n'
        f'  type: manufacturing\n'
        f'  version: "0.1.0"\n'
        f'  framework: ">=0.3.0"\n'
        f'\n'
        f'product:\n'
        f'  slug: {product}\n'
        f'  board: {board}\n'
        f'\n'
        f'fixture:\n'
        f'  controller: fixtures.{board}.controller.{board_class}MfgFixture\n'
        f'  profile: fixtures/{board}/fixture.yaml\n'
        f'  multi_slot: true\n'
        f'\n'
        f'steps:\n'
        f'  - name: Electrical\n'
        f'    module: tests.manufacturing.test_electrical\n'
        f'    timeout_s: 30\n'
        f'  - name: Flash Firmware\n'
        f'    module: tests.manufacturing.test_flash\n'
        f'    timeout_s: 120\n'
        f'  - name: POST\n'
        f'    module: tests.manufacturing.test_post\n'
        f'    timeout_s: 300\n'
    )
    (project_dir / MANIFEST_NAME).write_text(manifest_text)

    # Create basic files
    (project_dir / "tests" / "__init__.py").touch()

    (project_dir / "pytest.ini").write_text(
        f"[pytest]\ntestpaths = tests\npython_files = test_*.py\n"
    )

    (project_dir / "pyproject.toml").write_text(
        f'[project]\nname = "concord-manufacturing-{product}"\n'
        f'version = "0.1.0"\n'
        f'dependencies = ["corekinect>=0.3.0"]\n'
    )

    (project_dir / "conftest.py").write_text(
        'pytest_plugins = ["corekinect.test.autoconf"]\n'
    )

    click.echo(f"Created {product} manufacturing project:")
    click.echo(f"  {MANIFEST_NAME}")
    click.echo(f"  3 steps: Electrical, Flash Firmware, POST")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Create fixtures/{board}/fixture.yaml")
    click.echo(f"  2. Write tests in tests/manufacturing/")
    click.echo(f"  3. corectl test validate")


@test.command()
@click.argument("path", default=".", required=False)
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
def validate(path: str, strict: bool):
    """Validate a test project — structure, semantics, and compatibility.

    Three validation levels:
      Level 1 (Structure): Files exist, directories match manifest (+ JSON Schema for v2)
      Level 2 (Semantics): Profiles valid, markers defined, IDs set
      Level 3 (Compatibility): Framework version, build labels, pytest collection
    """
    project_dir = Path(path).resolve()
    result = ValidationResult()

    # Detect manifest version
    is_v2 = (project_dir / MANIFEST_NAME).exists()
    is_v1 = (project_dir / LEGACY_MANIFEST_NAME).exists()

    if not is_v2 and not is_v1:
        click.echo(f"No {MANIFEST_NAME} or {LEGACY_MANIFEST_NAME} found in {project_dir}", err=True)
        raise SystemExit(1)

    click.echo(f"Validating: {project_dir.name}/")
    if is_v1 and not is_v2:
        _warn_legacy()
    click.echo()

    # Level 1
    click.echo("Structure:")
    if is_v2:
        manifest = _validate_structure_v2(project_dir, result)
    else:
        manifest = _validate_structure_v1(project_dir, result)

    # Level 2 (only if structure passed)
    if manifest:
        click.echo()
        click.echo("Semantics:")
        _validate_semantics(project_dir, manifest, is_v2, result)

    # Level 3 (only if semantics passed)
    if manifest and not result.errors:
        click.echo()
        click.echo("Compatibility:")
        _validate_compatibility(project_dir, manifest, is_v2, result)

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
        corectl test run regression --marker health_check
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
    manifest_path, is_v2 = _find_manifest_path(project_dir)

    if not is_v2:
        _warn_legacy()

    manifest = _load_manifest_yaml(manifest_path)

    slug = _get_slug(manifest, is_v2)
    version = _get_version(manifest, is_v2)
    pkg_type = _get_package_type(manifest, is_v2).lower()

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

    config = ctx.obj["config"]
    token = require_auth(config)
    api_url = get_api_url(config)

    project_dir = Path(path).resolve()
    manifest_path, is_v2 = _find_manifest_path(project_dir)

    if not is_v2:
        _warn_legacy()

    manifest = _load_manifest_yaml(manifest_path)

    slug = _get_slug(manifest, is_v2)

    # ── Pre-upload validation ──
    click.echo("Pre-upload validation...")
    pre_result = ValidationResult()
    if is_v2:
        _validate_structure_v2(project_dir, pre_result)
    else:
        _validate_structure_v1(project_dir, pre_result)
    if manifest:
        _validate_semantics(project_dir, manifest, is_v2, pre_result)

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

    # Collect git state for traceability + version generation
    git_sha = ""
    git_dirty = False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, cwd=str(project_dir),
        )
        git_sha = result.stdout.strip()
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(project_dir),
        )
        git_dirty = bool(result.stdout.strip())
    except Exception:
        pass

    # Development version: git SHA + epoch suffix for uniqueness on dirty trees
    sha = git_sha or "unknown"
    if git_dirty:
        import time as _time
        epoch = int(_time.time())
        version = f"dev-{sha}-{epoch}"
    else:
        version = f"dev-{sha}"

    # Prompt for upload message
    dirty_hint = " (dirty)" if git_dirty else ""
    upload_message = click.prompt(
        f"Upload message [{git_sha}{dirty_hint}]",
        default="",
        show_default=False,
    ).strip()

    status = "DEVELOPMENT"
    package_type = _get_package_type(manifest, is_v2)

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
    import requests

    api = ConcordAPI(api_url, token, tls_verify=get_tls_verify(ctx.obj["config"]))

    import json as json_mod

    # Build stages/steps info for the upload payload
    if is_v2:
        pkg_type_str = manifest.get("package", {}).get("type", "validation")
        if pkg_type_str == "validation":
            stages_enabled = {name: True for name in manifest.get("stages", {}).keys()}
        else:
            stages_enabled = {step["name"]: True for step in manifest.get("steps", [])}
    else:
        stages_enabled = manifest.get("stages", {})

    upload_manifest = {
        "version": version,
        "type": package_type,
        "status": status,
        "frameworkVersion": _get_framework(manifest, is_v2),
        "productSlug": slug,
        "manifestHash": manifest_hash,
        "stagesEnabled": stages_enabled,
        "testCount": 0,  # Backend can override from collection
        "message": upload_message,
        "gitSha": git_sha,
        "gitDirty": git_dirty,
    }

    # Add schema version for v2 manifests
    if is_v2:
        upload_manifest["schemaVersion"] = manifest.get("schema", "2.0")

    resp = requests.post(
        f"{api_url}/v2/products/{slug}/test-packages",
        headers={"Authorization": f"ApiKey {token}"},
        files={"package": (f"{slug}-{version}.tar.gz", package_bytes, "application/gzip")},
        data={"manifest": json_mod.dumps(upload_manifest)},
        verify=False,  # Self-signed certs in staging
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
            release_resp = requests.post(
                f"{api_url}/v2/products/{slug}/test-packages/{package_id}/release",
                headers={"Authorization": f"ApiKey {token}"},
                verify=False,
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
    import requests

    config = ctx.obj["config"]
    token = require_auth(config)
    api_url = get_api_url(config)
    api = ConcordAPI(api_url, token, tls_verify=get_tls_verify(config))

    # Resolve product slug from manifest
    manifest_dir = Path(project_path) if project_path else Path(".")
    manifest_dir = manifest_dir.resolve()
    manifest_path, is_v2 = _find_manifest_path(manifest_dir)
    manifest = _load_manifest_yaml(manifest_path)
    slug = _get_slug(manifest, is_v2)

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
    resp = requests.post(
        f"{api_url}/v2/products/{slug}/test-packages/{package_id}/release",
        headers={"Authorization": f"ApiKey {token}"},
        verify=False,
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
    config = ctx.obj["config"]
    token = require_auth(config)
    api_url = get_api_url(config)

    project_dir = Path(path).resolve()
    manifest_path, is_v2 = _find_manifest_path(project_dir)

    if not is_v2:
        _warn_legacy()

    manifest = _load_manifest_yaml(manifest_path)
    slug = _get_slug(manifest, is_v2)

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


@test.command()
@click.argument("path", default=".", required=False)
def migrate(path: str):
    """Migrate concord.test.yaml (v1) to concord.yaml (v2).

    Reads the legacy manifest, converts it to v2 format, and writes concord.yaml.
    Does NOT delete the old file — remove it manually after verifying.
    """
    project_dir = Path(path).resolve()
    v1_path = project_dir / LEGACY_MANIFEST_NAME
    v2_path = project_dir / MANIFEST_NAME

    if v2_path.exists():
        click.echo(f"{MANIFEST_NAME} already exists — migration not needed", err=True)
        raise SystemExit(1)

    if not v1_path.exists():
        click.echo(f"{LEGACY_MANIFEST_NAME} not found — nothing to migrate", err=True)
        raise SystemExit(1)

    with open(v1_path) as f:
        v1 = yaml.safe_load(f) or {}

    if not v1:
        click.echo(f"{LEGACY_MANIFEST_NAME} is empty or invalid", err=True)
        raise SystemExit(1)

    # Extract v1 fields
    product = v1.get("product", {})
    slug = product.get("name", "unknown")
    board = product.get("board", "unknown")
    device_type_id = product.get("device_type_id", 0)
    device_variant_id = product.get("device_variant_id", 0)
    test_version = v1.get("test_version", v1.get("version", "0.1.0"))
    framework = v1.get("framework", ">=0.3.0")

    # Auto-detect package type from v1 stages
    v1_stages = v1.get("stages", {})
    has_manufacturing = v1_stages.get("manufacturing", False)
    has_validation = any(v1_stages.get(s, False) for s in STANDARD_STAGES)
    if has_manufacturing and not has_validation:
        pkg_type = "manufacturing"
    else:
        pkg_type = "validation"

    # Board class name: alpha_b0 -> AlphaB0
    board_class = "".join(part.capitalize() for part in board.split("_"))

    # Ensure framework has >= prefix
    if framework and not framework.startswith(">="):
        framework = f">={framework}"

    # Ensure version is a string
    test_version = str(test_version)
    # If version is just an int like "1", make it semver-ish
    if test_version.count(".") == 0:
        test_version = f"{test_version}.0.0"
    elif test_version.count(".") == 1:
        test_version = f"{test_version}.0"

    # Build v2 manifest
    lines = [
        f'schema: "2.0"',
        f'',
        f'package:',
        f'  type: {pkg_type}',
        f'  version: "{test_version}"',
        f'  framework: "{framework}"',
        f'',
        f'product:',
        f'  slug: {slug}',
        f'  board: {board}',
        f'  device:',
        f'    type_id: {device_type_id}',
        f'    variant_id: {device_variant_id}',
        f'',
        f'fixture:',
        f'  controller: fixtures.{board}.controller.{board_class}Fixture',
        f'  profile: fixtures/{board}/fixture.yaml',
    ]

    if pkg_type == "manufacturing":
        # Add multi_slot under fixture block before closing it
        lines.append(f'  multi_slot: true')

    if pkg_type == "validation":
        lines.append('')
        lines.append('stages:')

        # Default timeouts per stage
        default_timeouts = {
            "smoke": 120,
            "driver": 300,
            "integration": 600,
            "regression": 600,
            "fuota": 1800,
        }

        for stage_name, enabled in v1_stages.items():
            if stage_name == "manufacturing":
                continue
            if not enabled:
                continue
            timeout = default_timeouts.get(stage_name, 300)
            lines.append(f'  {stage_name}:')
            lines.append(f'    directory: tests/{stage_name}')
            lines.append(f'    timeout_s: {timeout}')
            lines.append(f'    hardware: [power]')
    else:
        # Manufacturing — create default steps
        lines.append('')
        lines.append('steps:')
        lines.append('  - name: Manufacturing Test')
        lines.append('    module: tests.manufacturing.test_mfg')
        lines.append('    timeout_s: 300')

    lines.append('')  # trailing newline

    v2_text = '\n'.join(lines)
    v2_path.write_text(v2_text)

    click.echo(f"Migrated {LEGACY_MANIFEST_NAME} -> {MANIFEST_NAME}")
    click.echo()
    click.echo(f"  Product: {slug}")
    click.echo(f"  Board: {board}")
    click.echo(f"  Type: {pkg_type}")
    click.echo(f"  Version: {test_version}")
    click.echo()

    # Show the generated file
    click.echo("Generated concord.yaml:")
    click.echo(click.style("--- ", fg="cyan"))
    for line in v2_text.splitlines():
        click.echo(click.style(f"  {line}", fg="cyan"))
    click.echo(click.style("--- ", fg="cyan"))

    click.echo()
    click.echo(f"Review the output, then delete {LEGACY_MANIFEST_NAME} when satisfied:")
    click.echo(f"  rm {LEGACY_MANIFEST_NAME}")
    click.echo(f"  corectl test validate")
