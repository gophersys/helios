"""Artifact validation for build pipelines.

Validates that all required artifacts exist per a pipeline's stage buildMatrix
before allowing validation to proceed. This is a HARD GATE — missing artifacts
cause the pipeline to fail.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def validate_pipeline_artifacts(db, pipeline_id: str) -> Dict[str, Any]:
    """Validate that all required artifacts exist for a pipeline's builds.

    Loads the pipeline with builds+artifacts, the stage config, and the product's
    buildConfig targets. For each build in the stage's buildMatrix, checks that
    the corresponding BuildJob exists, succeeded, and has all required artifacts
    for each target processor.

    Returns a structured report:
        {
            "valid": True/False,
            "builds": [...],
            "missing": [...]
        }
    """
    pipeline = db.pipelinerun.find_unique(
        where={"id": pipeline_id},
        include={
            "builds": {"include": {"artifacts": True}},
            "product": True,
        },
    )
    if not pipeline:
        logger.warning("Pipeline not found for artifact validation: %s", pipeline_id)
        return {"valid": True, "builds": [], "missing": []}

    # Load stage config if linked
    stage_config = None
    if getattr(pipeline, "stageConfigId", None):
        stage_config = db.productstageconfig.find_unique(
            where={"id": pipeline.stageConfigId},
        )

    # If no stage config, skip validation (nothing to check against)
    if not stage_config:
        logger.info("No stageConfig for pipeline %s, skipping artifact validation", pipeline_id)
        return {"valid": True, "builds": [], "missing": []}

    # Parse buildMatrix from stage config
    build_matrix = _parse_build_matrix(stage_config)
    if not build_matrix:
        logger.info("No buildMatrix in stageConfig for pipeline %s, skipping", pipeline_id)
        return {"valid": True, "builds": [], "missing": []}

    # Parse product targets from buildConfig
    product = getattr(pipeline, "product", None)
    targets = _parse_product_targets(product)
    if not targets:
        logger.info("No buildConfig targets for pipeline %s product, skipping", pipeline_id)
        return {"valid": True, "builds": [], "missing": []}

    # Determine if CFW is required
    requires_cfw = getattr(stage_config, "requiresFuota", False) or (
        getattr(stage_config, "stage", 0) >= 4
    )

    # Index builds by matrixLabel
    builds_by_label: Dict[str, Any] = {}
    for build in (pipeline.builds or []):
        label = getattr(build, "matrixLabel", None)
        if label:
            builds_by_label[label] = build

    result_builds: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for entry in build_matrix:
        label = entry.get("label") or entry.get("role", "").upper()
        build = builds_by_label.get(label)

        build_report = _check_build_artifacts(
            label=label,
            build=build,
            targets=targets,
            requires_cfw=requires_cfw,
        )

        result_builds.append(build_report)
        missing.extend(build_report.pop("_missing", []))

    valid = len(missing) == 0

    if not valid:
        logger.warning(
            "Pipeline %s artifact validation FAILED: %d missing artifacts",
            pipeline_id, len(missing),
        )
        for m in missing:
            logger.warning("  Missing: label=%s role=%s type=%s", m["label"], m["role"], m["artifactType"])
    else:
        logger.info("Pipeline %s artifact validation passed (%d builds)", pipeline_id, len(result_builds))

    return {
        "valid": valid,
        "builds": result_builds,
        "missing": missing,
    }


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


def _check_build_artifacts(
    label: str,
    build: Any,
    targets: List[Dict[str, str]],
    requires_cfw: bool,
) -> Dict[str, Any]:
    """Check a single build's artifacts against expected targets.

    Returns a build report dict with an internal '_missing' list that the
    caller pops off to aggregate.
    """
    missing_items: List[Dict[str, str]] = []

    if not build:
        # Build not found at all
        for t in targets:
            role = t.get("role", "unknown")
            missing_items.append({"label": label, "role": role, "artifactType": "plaintextHex"})
            if requires_cfw:
                missing_items.append({"label": label, "role": role, "artifactType": "encryptedCfw"})
        missing_items.append({"label": label, "role": "all", "artifactType": "manifest"})

        return {
            "label": label,
            "buildId": None,
            "status": None,
            "artifacts": {
                "plaintextHex": {t.get("role", "unknown"): False for t in targets},
                "encryptedCfw": {t.get("role", "unknown"): False for t in targets},
                "manifest": False,
            },
            "complete": False,
            "_missing": missing_items,
        }

    build_status = getattr(build, "status", None)
    build_id = getattr(build, "id", None)

    # Build exists but didn't succeed
    if build_status not in ("SUCCESS", "CACHED"):
        for t in targets:
            role = t.get("role", "unknown")
            missing_items.append({"label": label, "role": role, "artifactType": "plaintextHex"})
            if requires_cfw:
                missing_items.append({"label": label, "role": role, "artifactType": "encryptedCfw"})
        missing_items.append({"label": label, "role": "all", "artifactType": "manifest"})

        return {
            "label": label,
            "buildId": build_id,
            "status": build_status,
            "artifacts": {
                "plaintextHex": {t.get("role", "unknown"): False for t in targets},
                "encryptedCfw": {t.get("role", "unknown"): False for t in targets},
                "manifest": False,
            },
            "complete": False,
            "_missing": missing_items,
        }

    # Build succeeded — check artifacts
    artifacts = getattr(build, "artifacts", []) or []

    # Index artifacts by (role, artifactType)
    artifact_index = set()
    has_manifest = False
    for a in artifacts:
        a_role = getattr(a, "role", None)
        a_type = getattr(a, "artifactType", None)
        a_name = getattr(a, "name", "")

        if a_type:
            artifact_index.add((a_role, a_type))
        # Also detect manifest by name pattern (build.json)
        if a_type == "manifest" or a_name.endswith("build.json") or a_name == "build.json":
            has_manifest = True

    hex_status = {}
    cfw_status = {}

    for t in targets:
        role = t.get("role", "unknown")
        processor = t.get("processor", "")

        # Check plaintextHex — match by role or processor
        has_hex = (
            (role, "plaintextHex") in artifact_index
            or (processor, "plaintextHex") in artifact_index
            or _has_artifact_by_pattern(artifacts, role, processor, "plaintextHex", ".hex")
        )
        hex_status[role] = has_hex
        if not has_hex:
            missing_items.append({"label": label, "role": role, "artifactType": "plaintextHex"})

        # Check encryptedCfw (only if required)
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
            cfw_status[role] = True  # Not required, mark as present

    # Check manifest
    if not has_manifest:
        missing_items.append({"label": label, "role": "all", "artifactType": "manifest"})

    complete = len(missing_items) == 0

    return {
        "label": label,
        "buildId": build_id,
        "status": build_status,
        "artifacts": {
            "plaintextHex": hex_status,
            "encryptedCfw": cfw_status,
            "manifest": has_manifest,
        },
        "complete": complete,
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
