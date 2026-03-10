"""Stage 4 build matrix configuration and generation.

Stage 4 validation requires 8 firmware builds producing 16 CFW files:

| # | Label          | Source       | Git Ref   | Variant | Version | Purpose                    |
|---|----------------|--------------|-----------|---------|---------|----------------------------|
| 0 | MFG_BASE       | alpha_mfg_fw | main      | mfg     | N       | Starting point (J-Link)    |
| 1 | MFG_BUMP       | alpha_mfg_fw | main      | mfg     | N+1     | FUOTA sanity (same code)   |
| 2 | FUT_DEBUG_A    | alpha_fw     | PR branch | debug   | M       | Firmware Under Test (debug)|
| 3 | FUT_DEBUG_B    | alpha_fw     | PR branch | debug   | M+1     | FUOTA on debug FW          |
| 4 | FUT_RELEASE_A  | alpha_fw     | PR branch | release | M+2     | Release FW (FUOTA from debug)|
| 5 | FUT_RELEASE_B  | alpha_fw     | PR branch | release | M+3     | FUOTA on release FW        |
| 6 | MAIN_BASELINE  | alpha_fw     | main      | release | K       | Current production baseline|
| 7 | MAIN_MERGED    | alpha_fw     | merge sim | release | K+1     | Field upgrade path         |

Each build produces 2 CFW files (app + comms) = 16 total.

Version flow for FUOTA compatibility (versions must monotonically increase):
- MFG: N → N+1 (sanity test)
- Debug→Release: M → M+1 → M+2 → M+3 (full FUOTA chain)
- Main: K → K+1 (field upgrade test)

Note: FUT_RELEASE_A is M+2 (not M) so Debug→Release FUOTA works.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MatrixLabel(str, Enum):
    """Stage 4 build matrix labels."""
    MFG_BASE = "MFG_BASE"          # Manufacturing FW baseline (J-Link flash)
    MFG_BUMP = "MFG_BUMP"          # Manufacturing FW version bump (FUOTA sanity)
    FUT_DEBUG_A = "FUT_DEBUG_A"    # Firmware Under Test - debug variant
    FUT_DEBUG_B = "FUT_DEBUG_B"    # FUT debug version bump
    FUT_RELEASE_A = "FUT_RELEASE_A"  # FUT release variant (shipping binary)
    FUT_RELEASE_B = "FUT_RELEASE_B"  # FUT release version bump
    MAIN_BASELINE = "MAIN_BASELINE"  # Current main branch release
    MAIN_MERGED = "MAIN_MERGED"      # Simulated merge result


@dataclass
class BuildSpec:
    """Specification for a single build in the matrix."""
    label: MatrixLabel
    index: int
    firmware_type: str  # "alpha_fw" or "alpha_mfg_fw"
    variant: str        # "mfg", "debug", or "release"
    git_ref: str        # branch name or commit SHA
    ref_type: str       # "main", "pr", or "merge"
    is_version_bump: bool
    base_label: Optional[MatrixLabel] = None  # Label of the base build for version bumps


# Stage 4 matrix definition - order matters for build dependencies
# Version chain: DEBUG_A(M) → DEBUG_B(M+1) → RELEASE_A(M+2) → RELEASE_B(M+3)
STAGE4_MATRIX: List[BuildSpec] = [
    # Manufacturing firmware (from main branch)
    BuildSpec(MatrixLabel.MFG_BASE, 0, "{product}_mfg_fw", "mfg", "main", "main", False),
    BuildSpec(MatrixLabel.MFG_BUMP, 1, "{product}_mfg_fw", "mfg", "main", "main", True, MatrixLabel.MFG_BASE),

    # Firmware Under Test - debug (from PR branch)
    BuildSpec(MatrixLabel.FUT_DEBUG_A, 2, "{product}_fw", "debug", "pr", "pr", False),
    BuildSpec(MatrixLabel.FUT_DEBUG_B, 3, "{product}_fw", "debug", "pr", "pr", True, MatrixLabel.FUT_DEBUG_A),

    # Firmware Under Test - release (from PR branch)
    # RELEASE_A version bumps from DEBUG_B so FUOTA debug→release works
    BuildSpec(MatrixLabel.FUT_RELEASE_A, 4, "{product}_fw", "release", "pr", "pr", True, MatrixLabel.FUT_DEBUG_B),
    BuildSpec(MatrixLabel.FUT_RELEASE_B, 5, "{product}_fw", "release", "pr", "pr", True, MatrixLabel.FUT_RELEASE_A),

    # Main branch baseline (current production)
    BuildSpec(MatrixLabel.MAIN_BASELINE, 6, "{product}_fw", "release", "main", "main", False),
    BuildSpec(MatrixLabel.MAIN_MERGED, 7, "{product}_fw", "release", "merge", "merge", True, MatrixLabel.MAIN_BASELINE),
]


@dataclass
class Stage4MatrixConfig:
    """Configuration for a Stage 4 build matrix."""
    product: str              # Base product name (alpha, sigma5)
    board: str                # Board variant (alpha_b0)
    main_branch: str          # Main branch name (main, master)
    main_commit: str          # Main branch commit SHA
    pr_branch: str            # PR branch name
    pr_commit: str            # PR branch commit SHA
    merge_commit: Optional[str] = None  # Simulated merge commit (optional)
    mtib_rev: str = "1.2"     # MTIB hardware revision

    # Version tracking - these get populated as builds complete
    mfg_base_version: Optional[str] = None
    fut_base_version: Optional[str] = None
    main_base_version: Optional[str] = None


def generate_stage4_builds(config: Stage4MatrixConfig) -> List[Dict[str, Any]]:
    """Generate build job specs for Stage 4 matrix.

    Returns a list of build job data dicts ready for database insertion.
    """
    builds = []

    for spec in STAGE4_MATRIX:
        # Resolve firmware type
        fw_type = spec.firmware_type.format(product=config.product)
        is_mfg_fw = "_mfg_fw" in fw_type

        # Resolve git ref and branch
        # MFG firmware uses actual 'main' branch (separate repo, separate versioning)
        # Production firmware uses concord-main (the unprotected working branch)
        if is_mfg_fw:
            # MFG builds always use the actual main branch of the separate mfg repo
            git_ref = None  # Use HEAD of main
            branch = "main"
        elif spec.ref_type == "pr":
            git_ref = config.pr_commit
            branch = config.pr_branch
        elif spec.ref_type == "merge":
            # MAIN_MERGED simulates merging PR to main
            git_ref = config.merge_commit or config.pr_commit
            branch = config.pr_branch
        else:
            # For production firmware, use concord-main as the "main" branch
            git_ref = config.main_commit or config.pr_commit
            branch = config.pr_branch  # concord-main

        # Version bump builds start BLOCKED until their base build completes
        initial_status = "BLOCKED" if spec.is_version_bump else "QUEUED"

        build = {
            "product": fw_type,
            "board": config.board,
            "target": "nrf52840",  # Primary target
            "variant": spec.variant,
            "mtibRev": config.mtib_rev,
            "branch": branch,
            "commitSha": git_ref,
            "status": initial_status,
            "matrixLabel": spec.label.value,
            "matrixIndex": spec.index,
            "versionBump": spec.is_version_bump,
            # baseLabel used to resolve baseJobId after all builds created
            "baseLabel": spec.base_label.value if spec.base_label else None,
        }

        builds.append(build)

    return builds


def get_build_dependencies() -> Dict[MatrixLabel, MatrixLabel]:
    """Return mapping of version-bumped builds to their base builds.

    Returns dict like {MFG_BUMP: MFG_BASE, FUT_DEBUG_B: FUT_DEBUG_A, ...}
    """
    deps = {}
    for spec in STAGE4_MATRIX:
        if spec.is_version_bump and spec.base_label:
            deps[spec.label] = spec.base_label
    return deps


def get_fuota_transitions() -> List[Tuple[MatrixLabel, MatrixLabel, str]]:
    """Return the FUOTA transition sequence for Stage 4.

    Returns list of (from_label, to_label, purpose) tuples.
    """
    return [
        (MatrixLabel.MFG_BASE, MatrixLabel.MFG_BUMP, "FUOTA sanity (same code, bumped version)"),
        (MatrixLabel.MFG_BUMP, MatrixLabel.FUT_DEBUG_A, "Factory transition (mfg → prod debug)"),
        (MatrixLabel.FUT_DEBUG_A, MatrixLabel.FUT_DEBUG_B, "FUOTA on debug production FW"),
        (MatrixLabel.FUT_DEBUG_B, MatrixLabel.FUT_RELEASE_A, "Debug → release transition"),
        (MatrixLabel.FUT_RELEASE_A, MatrixLabel.FUT_RELEASE_B, "FUOTA on release production FW"),
        (MatrixLabel.MAIN_BASELINE, MatrixLabel.MAIN_MERGED, "Field upgrade path simulation"),
    ]


def calculate_expected_builds(mode: str = "stage4") -> int:
    """Calculate expected number of builds for a pipeline mode."""
    if mode == "stage4":
        return len(STAGE4_MATRIX)  # 8 builds
    else:  # quick
        return len(QUICK_MATRIX)  # 2 builds


# ─────────────────────────────────────────────────────────────────────────────
# Simplified "quick" modes for faster iteration
# ─────────────────────────────────────────────────────────────────────────────

QUICK_MATRIX: List[BuildSpec] = [
    # Just build FUT debug + release for quick PR validation
    BuildSpec(MatrixLabel.FUT_DEBUG_A, 0, "{product}_fw", "debug", "pr", "pr", False),
    BuildSpec(MatrixLabel.FUT_RELEASE_A, 1, "{product}_fw", "release", "pr", "pr", False),
]


def generate_quick_builds(config: Stage4MatrixConfig) -> List[Dict[str, Any]]:
    """Generate minimal build set for quick PR validation (2 builds)."""
    builds = []

    for spec in QUICK_MATRIX:
        fw_type = spec.firmware_type.format(product=config.product)

        build = {
            "product": fw_type,
            "board": config.board,
            "target": "nrf52840",
            "variant": spec.variant,
            "mtibRev": config.mtib_rev,
            "branch": config.pr_branch,
            "commitSha": config.pr_commit,
            "status": "QUEUED",
            "matrixLabel": spec.label.value,
            "matrixIndex": spec.index,
            "versionBump": False,
        }
        builds.append(build)

    return builds
