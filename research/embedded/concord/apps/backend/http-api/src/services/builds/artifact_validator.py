"""Artifact validation for build runs.

Validates that all required artifacts exist per a build run's stage buildMatrix
before allowing validation to proceed. This is a HARD GATE — missing artifacts
cause the build run to fail.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_SKIP_RESULT = {"valid": True, "builds": [], "missing": []}


def validate_build_run_artifacts(db, build_run_id: str) -> Dict[str, Any]:
    """Validate that all required artifacts exist for a build run's builds.

    Returns a structured report: {"valid": bool, "builds": [...], "missing": [...]}
    """
    build_run = db.buildrun.find_unique(
        where={"id": build_run_id},
        include={"builds": {"include": {"artifacts": True}}, "product": True},
    )
    if not build_run:
        logger.warning("Build run not found for artifact validation: %s", build_run_id)
        return _SKIP_RESULT

    context = _load_validation_context(db, build_run, build_run_id)
    if context is None:
        return _SKIP_RESULT

    build_matrix, targets, requires_cfw, builds_by_label = context
    return _run_artifact_checks(build_run_id, build_matrix, targets, requires_cfw, builds_by_label)


def _load_validation_context(db, build_run, build_run_id: str):
    """Load stage config, build matrix, and targets. Returns None if validation should be skipped."""
    stage_config = None
    if getattr(build_run, "stageConfigId", None):
        stage_config = db.productstageconfig.find_unique(where={"id": build_run.stageConfigId})
    if not stage_config:
        logger.info("No stageConfig for build run %s, skipping artifact validation", build_run_id)
        return None

    build_matrix = _parse_build_matrix(stage_config)
    if not build_matrix:
        logger.info("No buildMatrix in stageConfig for build run %s, skipping", build_run_id)
        return None

    targets = _parse_product_targets(getattr(build_run, "product", None))
    if not targets:
        logger.info("No buildConfig targets for build run %s product, skipping", build_run_id)
        return None

    requires_cfw = getattr(stage_config, "requiresFuota", False) or (getattr(stage_config, "stage", 0) >= 4)

    builds_by_label: Dict[str, Any] = {}
    for build in (build_run.builds or []):
        label = getattr(build, "matrixLabel", None)
        if label:
            builds_by_label[label] = build

    return build_matrix, targets, requires_cfw, builds_by_label


def _run_artifact_checks(build_run_id, build_matrix, targets, requires_cfw, builds_by_label):
    """Run artifact checks for each build matrix entry and compile the report."""
    result_builds: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for entry in build_matrix:
        label = entry.get("label") or entry.get("role", "").upper()
        build_report = _check_build_artifacts(
            label=label,
            build=builds_by_label.get(label),
            targets=targets,
            requires_cfw=requires_cfw,
        )
        result_builds.append(build_report)
        missing.extend(build_report.pop("_missing", []))

    valid = len(missing) == 0
    if not valid:
        logger.warning("Build run %s artifact validation FAILED: %d missing artifacts", build_run_id, len(missing))
        for m in missing:
            logger.warning("  Missing: label=%s role=%s type=%s", m["label"], m["role"], m["artifactType"])
    else:
        logger.info("Build run %s artifact validation passed (%d builds)", build_run_id, len(result_builds))

    return {"valid": valid, "builds": result_builds, "missing": missing}


def _parse_build_matrix(stage_config) -> Optional[List[Dict[str, Any]]]:
    """Parse the buildMatrix from a ProductStageConfig.

    buildMatrix can be a JSON list or already-parsed list. Each entry should
    have at least a 'role' or 'label' field.
    """
    raw = getattr(stage_config, "buildMatrix", None)
    if not raw:
        return None

    if isinstance(raw, list):
        return raw

    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _parse_product_targets(product) -> Optional[List[Dict[str, str]]]:
    """Parse the targets array from a Product's buildConfig.

    buildConfig is a JSON field with structure:
        {"targets": [{"role": "app", "processor": "nrf52840", "appId": 109}, ...]}
    """
    if not product:
        return None

    build_config = getattr(product, "buildConfig", None)
    if not build_config:
        return None

    if isinstance(build_config, str):
        try:
            build_config = json.loads(build_config)
        except (json.JSONDecodeError, TypeError):
            return None

    if isinstance(build_config, dict):
        targets = build_config.get("targets")
        if isinstance(targets, list) and len(targets) > 0:
            return targets

    return None


def _all_missing_report(label: str, build_id, status, targets, requires_cfw):
    """Build a report where all artifacts are missing (build absent or failed)."""
    missing = []
    for t in targets:
        role = t.get("role", "unknown")
        missing.append({"label": label, "role": role, "artifactType": "plaintextHex"})
        if requires_cfw:
            missing.append({"label": label, "role": role, "artifactType": "encryptedCfw"})
    missing.append({"label": label, "role": "all", "artifactType": "manifest"})
    return {
        "label": label,
        "buildId": build_id,
        "status": status,
        "artifacts": {
            "plaintextHex": {t.get("role", "unknown"): False for t in targets},
            "encryptedCfw": {t.get("role", "unknown"): False for t in targets},
            "manifest": False,
        },
        "complete": False,
        "_missing": missing,
    }


def _index_artifacts(artifacts):
    """Build a set of (role, artifactType) pairs and detect manifest presence."""
    artifact_index = set()
    has_manifest = False
    for a in artifacts:
        a_type = getattr(a, "artifactType", None)
        if a_type:
            artifact_index.add((getattr(a, "role", None), a_type))
        a_name = getattr(a, "name", "")
        if a_type == "manifest" or a_name.endswith("build.json"):
            has_manifest = True
    return artifact_index, has_manifest


def _check_build_artifacts(
    label: str,
    build: Any,
    targets: List[Dict[str, str]],
    requires_cfw: bool,
) -> Dict[str, Any]:
    """Check a single build's artifacts against expected targets."""
    if not build:
        return _all_missing_report(label, None, None, targets, requires_cfw)

    build_status = getattr(build, "status", None)
    build_id = getattr(build, "id", None)

    if build_status not in ("SUCCESS", "CACHED"):
        return _all_missing_report(label, build_id, build_status, targets, requires_cfw)

    # Build succeeded — check artifacts
    artifacts = getattr(build, "artifacts", []) or []
    artifact_index, has_manifest = _index_artifacts(artifacts)

    missing_items: List[Dict[str, str]] = []
    hex_status = {}
    cfw_status = {}

    for t in targets:
        role = t.get("role", "unknown")
        processor = t.get("processor", "")

        has_hex = (
            (role, "plaintextHex") in artifact_index
            or (processor, "plaintextHex") in artifact_index
            or _has_artifact_by_pattern(artifacts, role, processor, "plaintextHex", ".hex")
        )
        hex_status[role] = has_hex
        if not has_hex:
            missing_items.append({"label": label, "role": role, "artifactType": "plaintextHex"})

        if requires_cfw:
            has_cfw = (
                (role, "encryptedCfw") in artifact_index
                or (processor, "encryptedCfw") in artifact_index
                or _has_artifact_by_pattern(artifacts, role, processor, "encryptedCfw", ".cfw")
            )
            cfw_status[role] = has_cfw
            if not has_cfw:
                missing_items.append({"label": label, "role": role, "artifactType": "encryptedCfw"})
        else:
            cfw_status[role] = True

    if not has_manifest:
        missing_items.append({"label": label, "role": "all", "artifactType": "manifest"})

    return {
        "label": label,
        "buildId": build_id,
        "status": build_status,
        "artifacts": {"plaintextHex": hex_status, "encryptedCfw": cfw_status, "manifest": has_manifest},
        "complete": len(missing_items) == 0,
        "_missing": missing_items,
    }


def _has_artifact_by_pattern(
    artifacts: list,
    role: str,
    processor: str,
    artifact_type: str,
    extension: str,
) -> bool:
    """Fallback check: look for artifacts matching by name pattern.

    Artifact names follow patterns like:
        - 0.8.3_release_app_nrf52840.hex
        - 109.0.8.3-BM.cfw
        - build.json

    This handles cases where role/artifactType metadata wasn't set on upload.
    """
    for a in artifacts:
        name = getattr(a, "name", "") or ""
        if not name.endswith(extension):
            continue

        # Check if the artifact name contains the role or processor
        name_lower = name.lower()
        if role and role.lower() in name_lower:
            return True
        if processor and processor.lower() in name_lower:
            return True

    return False


def format_missing_artifacts_message(missing: List[Dict[str, str]]) -> str:
    """Format a human-readable error message for missing artifacts."""
    if not missing:
        return ""

    lines = ["Artifact validation failed. Missing artifacts:"]
    for m in missing:
        lines.append(f"  - {m['label']}: {m['artifactType']} (role={m['role']})")

    return "\n".join(lines)
