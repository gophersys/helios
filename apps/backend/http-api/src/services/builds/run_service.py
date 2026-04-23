"""Build run business logic — matrix expansion, build creation, completion, validation trigger.

Extracted from api/v2/builds/build_runs.py to keep handlers thin.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import Json
from flask import g

from src.lib.audit import log_audit
from src.services.database.prisma import get_db_client

from src.api.v2.builds.build_cache import compute_build_fingerprint, find_cached_build
from src.api.v2.runs.manual import create_kubernetes_job
from src.services.builds.artifact_validator import (
    validate_build_run_artifacts,
    format_missing_artifacts_message,
)
from src.services.builds.promotion import promote_build_run_to_firmware, create_asset_set_from_build_run
from corekinect.stages import Stage

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────


def safe_product_str(obj, target: str | None = None) -> str | None:
    """Safely extract product slug string from a model field that could be a string or relation."""
    if isinstance(obj, str):
        return obj
    if obj and hasattr(obj, "slug"):
        return obj.slug or obj.name
    return None


def derive_build_product_slug(b) -> str:
    """Get product slug from build for session metadata."""
    product = getattr(b, "product", None)
    if isinstance(product, str):
        return product
    if product and hasattr(product, "slug"):
        return product.slug or product.name
    return getattr(b, "productId", "unknown")


def get_system_user_id(db) -> str:
    """Get or create system user for automated actions."""
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.create(data={"name": "System", "email": "system@concord.local"})
    return system_user.id


# ── Serializers ──────────────────────────────────────────────────────────


def serialize_build_run(p) -> Dict[str, Any]:
    """Serialize a BuildRun for API response."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
        "productId": getattr(p, "productId", None),
        "board": p.board,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "stage": getattr(p, "stage", None),
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "validationRunId": p.validationRunId,
        "matrixMode": getattr(p, "matrixMode", None),
        "autoRunStage": p.autoRunStage,
        "recipeVersionId": getattr(p, "recipeVersionId", None),
        "buildMatrix": p.buildMatrix if hasattr(p, "buildMatrix") else None,
        "triggerData": p.triggerData if hasattr(p, "triggerData") else None,
        # PR context
        "prNumber": getattr(p, "prNumber", None),
        "prTitle": getattr(p, "prTitle", None),
        "prAuthor": getattr(p, "prAuthor", None),
        "sourceBranch": getattr(p, "sourceBranch", None),
        "targetBranch": getattr(p, "targetBranch", None),
        "prUrl": getattr(p, "prUrl", None),
        "createdById": getattr(p, "createdById", None),
        "startedAt": p.startedAt.isoformat() if p.startedAt else None,
        "finishedAt": p.finishedAt.isoformat() if p.finishedAt else None,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }

    # Include builds if loaded
    if hasattr(p, "builds") and p.builds:
        data["builds"] = [
            {
                "id": b.id,
                "product": safe_product_str(getattr(b, "product", None), getattr(b, "target", None)) or getattr(b, "productId", None),
                "status": b.status,
                "target": b.target,
                "variant": b.variant,
                "board": b.board,
                "commitSha": b.commitSha,
                "buildNum": b.buildNum,
                "versionString": b.versionString,
                "durationSeconds": b.durationSeconds,
                "artifactCount": len(b.artifacts) if hasattr(b, "artifacts") and b.artifacts else 0,
                "reusedFromId": getattr(b, "reusedFromId", None),
                "matrixLabel": getattr(b, "matrixLabel", None),
                "matrixIndex": getattr(b, "matrixIndex", None),
                "versionBump": getattr(b, "versionBump", False),
                "baseJobId": getattr(b, "baseJobId", None),
            }
            for b in p.builds
        ]

    return data


def serialize_build_run_summary(p) -> Dict[str, Any]:
    """Serialize a BuildRun for list view."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
        "productId": getattr(p, "productId", None),
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "stage": getattr(p, "stage", None),
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "matrixMode": getattr(p, "matrixMode", None),
        "autoRunStage": p.autoRunStage,
        "recipeVersionId": getattr(p, "recipeVersionId", None),
        "validationRunId": getattr(p, "validationRunId", None),
        # PR context
        "prNumber": getattr(p, "prNumber", None),
        "prTitle": getattr(p, "prTitle", None),
        "prAuthor": getattr(p, "prAuthor", None),
        "sourceBranch": getattr(p, "sourceBranch", None),
        "targetBranch": getattr(p, "targetBranch", None),
        "prUrl": getattr(p, "prUrl", None),
        "createdById": getattr(p, "createdById", None),
        "startedAt": p.startedAt.isoformat() if p.startedAt else None,
        "finishedAt": p.finishedAt.isoformat() if p.finishedAt else None,
        "createdAt": p.createdAt.isoformat(),
    }

    # Include builds summary
    if hasattr(p, "builds") and p.builds:
        data["builds"] = [
            {
                "id": b.id,
                "product": safe_product_str(getattr(b, "product", None), getattr(b, "target", None)) or getattr(b, "productId", None),
                "status": b.status,
                "target": b.target,
                "variant": b.variant,
                "commitSha": b.commitSha,
                "versionString": b.versionString,
                "durationSeconds": b.durationSeconds,
                "reusedFromId": getattr(b, "reusedFromId", None),
                "matrixLabel": getattr(b, "matrixLabel", None),
                "matrixIndex": getattr(b, "matrixIndex", None),
                "versionBump": getattr(b, "versionBump", False),
            }
            for b in sorted(p.builds, key=lambda x: getattr(x, "matrixIndex", 0) or 0)
        ]

    return data


# ── Build spec generation ────────────────────────────────────────────────


def auto_increment_version(db, product_id: str, variant: str, target: str = "app") -> Optional[str]:
    """Auto-increment the build number from the latest successful build.

    Finds the most recent SUCCESS build for the product+variant+target, parses its
    version string (major.minor.build), and increments the build number.
    Returns None if no previous build exists.
    """
    latest = db.buildjob.find_first(
        where={"productId": product_id, "variant": variant, "target": target, "status": "SUCCESS"},
        order={"createdAt": "desc"},
    )
    if latest and latest.versionString:
        parts = latest.versionString.split(".")
        if len(parts) >= 3:
            try:
                next_build = int(parts[2]) + 1
                return f"{parts[0]}.{parts[1]}.{next_build}"
            except ValueError:
                pass
    return None


def get_max_build_number(db, product_id: str, target: str = "app") -> tuple[Optional[str], int]:
    """Get the highest build number across ALL variants for a product+target.

    Returns (version_prefix, max_build_num) e.g. ("0.8", 17).
    Used to allocate non-colliding version numbers for debug+release pairs.

    CoreCloud strips the D (debug) flag from CFW version strings, so
    debug v0.8.18-BD and release v0.8.18-B collide. By allocating
    sequential build numbers (debug=N, release=N+1), each variant
    gets a unique version on CoreCloud.
    """
    latest = db.buildjob.find_first(
        where={
            "productId": product_id,
            "target": target,
            "status": {"in": ["SUCCESS", "CACHED"]},
        },
        order={"buildNum": "desc"},
    )
    if latest and latest.versionString:
        parts = latest.versionString.split(".")
        if len(parts) >= 3:
            try:
                return f"{parts[0]}.{parts[1]}", int(parts[2])
            except ValueError:
                pass
    return None, 0


def resolve_build_run_context(db, data) -> Dict[str, Any]:
    """Resolve product, repo names, stage config, and build specs for a build run.

    Returns a context dict with all the resolved values needed to create
    the build run record and build jobs.
    """
    product_record = None
    if data.product_id:
        product_record = db.product.find_unique(where={"id": data.product_id})
    if not product_record:
        product_record = db.product.find_first(
            where={"slug": data.product}
        )

    if product_record:
        product_base = product_record.slug or product_record.name.lower().replace(" ", "_")
        repo_base = product_base
        for suffix in ["_b0", "_a0", "_b1", "_a1"]:
            repo_base = repo_base.replace(suffix, "")
        repo_base = repo_base.strip("_")
    else:
        repo_base = (data.repo_slug or data.product or "").lower().replace(" ", "_").replace("_fw", "").replace("_mfg", "")
        for suffix in ["_b0", "_a0", "_b1", "_a1"]:
            repo_base = repo_base.replace(suffix, "")
        repo_base = repo_base.strip("_")
        product_base = repo_base

    main_fw = data.repo_slug or f"{repo_base}_fw"
    mfg_fw = data.mfg_repo_slug or f"{repo_base}_mfg_fw"

    stage_map = {
        "smoke": Stage.SMOKE,
        "driver": Stage.DRIVER,
        "integration": Stage.INTEGRATION,
        "regression": Stage.REGRESSION,
        "fuota": Stage.FUOTA,
    }
    stage_number = data.validation_config.get("stage") if data.validation_config else None
    stage = stage_map.get(data.matrix_mode, Stage.FUOTA)

    stage_config = None
    stage_config_matrix = None
    if product_record:
        stage_num = stage_number or {"smoke": 1, "driver": 2, "integration": 3, "regression": 4, "fuota": 5}.get(data.matrix_mode, 5)
        stage_config = db.productstageconfig.find_first(
            where={"productId": product_record.id, "stage": stage_num},
        )
        if stage_config and stage_config.buildMatrix:
            stage_config_matrix = stage_config.buildMatrix if isinstance(stage_config.buildMatrix, list) else None

    if stage_config_matrix:
        build_specs = generate_matrix_build_specs(
            matrix=stage_config_matrix,
            product_record=product_record,
            repo_base=repo_base,
            board=data.board,
            branch=data.pr_branch or data.branch,
            commit_sha=data.commit_sha,
            db=db,
        )
    else:
        raise ValueError(
            f"Stage '{data.matrix_mode}' not configured for product '{product_record.name if product_record else 'unknown'}'. "
            "Populate ProductStageConfig.buildMatrix for this product and stage."
        )

    return {
        "product_record": product_record,
        "product_base": product_base,
        "repo_base": repo_base,
        "main_fw": main_fw,
        "mfg_fw": mfg_fw,
        "stage_config": stage_config,
        "stage_config_matrix": stage_config_matrix,
        "build_specs": build_specs,
    }


def create_build_run_record(db, data, ctx: Dict[str, Any]):
    """Create the BuildRun DB record and its build jobs.

    Returns (build_run, builds) tuple after creating and re-fetching with includes.
    """
    product_record = ctx["product_record"]
    product_base = ctx["product_base"]
    repo_base = ctx["repo_base"]
    main_fw = ctx["main_fw"]
    mfg_fw = ctx["mfg_fw"]
    stage_config = ctx["stage_config"]
    stage_config_matrix = ctx["stage_config_matrix"]
    build_specs = ctx["build_specs"]

    trigger_data = {
        "source": data.trigger_type,
        "repoSlug": data.repo_slug,  # Kept in trigger metadata for build context
        "mfgRepoSlug": data.mfg_repo_slug,  # Kept in trigger metadata for build context
        "modemFirmware": {
            "storageKey": f"firmware/modem/{repo_base}/mfw_nrf91x1_2.0.2.zip",
            "version": "2.0.2",
            "name": "mfw_nrf91x1_2.0.2.zip",
        },
    }
    if data.validation_config:
        trigger_data.update(data.validation_config)

    matrix_config = {
        "mode": data.matrix_mode,
        "product": repo_base,
        "productId": product_record.id if product_record else None,
        "mainFw": main_fw,
        "mfgFw": mfg_fw,
        "mainCommit": data.main_commit or data.commit_sha,
        "prBranch": data.pr_branch or data.branch,
        "prCommit": data.commit_sha,
    }
    if stage_config_matrix:
        matrix_config["buildMatrix"] = stage_config_matrix

    create_data = {
        "name": data.name or f"{product_base}-{data.branch[:8]}" + (f"-{data.commit_sha[:7]}" if data.commit_sha else ""),
        "board": data.board,
        "branch": data.branch,
        "commitSha": data.commit_sha,
        "status": "PENDING",
        "triggerTypes": data.trigger_type,
        "expectedBuilds": len(build_specs),
        "matrixMode": data.matrix_mode,
        "autoRunStage": data.auto_run_stage,
        "triggerData": Json(trigger_data),
        "startedAt": datetime.now(timezone.utc),
        "buildMatrix": Json(matrix_config),
    }
    if product_record:
        create_data["productId"] = product_record.id
    if stage_config:
        create_data["stageConfigId"] = stage_config.id
        create_data["stage"] = stage_config.stage

    # Traceability: record who created this build run
    try:
        user = getattr(g, "current_user", None)
        if user and isinstance(user, dict):
            create_data["createdById"] = user.get("sub")
    except RuntimeError:
        pass  # Outside Flask request context (e.g., git poller)

    build_run = db.buildrun.create(data=create_data)
    builds = create_build_jobs(db, build_run, build_specs, data, product_record)

    log_audit("ci.buildRun.create", "BuildRun", build_run.id, {
        "product": product_base,
        "branch": data.branch,
        "commitSha": data.commit_sha,
        "triggerTypes": data.trigger_type,
        "builds": [b.id for b in builds],
    })

    build_run = db.buildrun.find_unique(
        where={"id": build_run.id},
        include={"builds": {"include": {"product": True}}, "product": True},
    )

    return build_run, builds


def _generate_head_app_sub_builds(
    board: str, branch: str, commit_sha: Optional[str],
    firmware: str, prefix: str, max_build: int, start_idx: int,
) -> List[Dict[str, Any]]:
    """Generate 4 sub-builds (verbose/quiet x base/bump) for head app builds."""
    sub_defs = [
        ("prod_verbose",      max_build + 1, True),
        ("prod_verbose_bump", max_build + 2, True),
        ("prod_quiet",        max_build + 3, False),
        ("prod_quiet_bump",   max_build + 4, False),
    ]
    logger.info(
        "FUOTA version allocation: VERBOSE=v%s.%d/%d, QUIET=v%s.%d/%d (max=%s.%d)",
        prefix, max_build + 1, max_build + 2,
        prefix, max_build + 3, max_build + 4,
        prefix, max_build,
    )
    builds = []
    for i, (sub_label, ver_build, force_log) in enumerate(sub_defs):
        config = {"forceLog": True} if force_log else {}
        builds.append({
            "board": board, "target": "app", "variant": "release",
            "branch": branch, "commitSha": commit_sha, "status": "QUEUED",
            "matrixLabel": sub_label, "matrixIndex": start_idx + i,
            "versionBump": False, "source": "head", "firmware": firmware,
            "versionOverride": f"{prefix}.{ver_build}", "extraConfig": config,
        })
    return builds


def _make_build_spec(
    board: str, target: str, variant: str, branch: str,
    commit_sha: Optional[str], label: str, idx: int,
    source: str, firmware: str, version_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a single build spec dict."""
    spec: Dict[str, Any] = {
        "board": board, "target": target, "variant": variant,
        "mtibRev": "1.2", "branch": branch,
        "commitSha": commit_sha if source == "head" else None,
        "status": "QUEUED", "matrixLabel": label, "matrixIndex": idx,
        "versionBump": False, "source": source, "firmware": firmware,
    }
    if version_override:
        spec["versionOverride"] = version_override
    return spec


def generate_matrix_build_specs(
    matrix: List[Dict[str, Any]],
    product_record: Any,
    repo_base: str,
    board: str,
    branch: str,
    commit_sha: Optional[str],
    db: Any,
) -> List[Dict[str, Any]]:
    """Generate build specs from a ProductStageConfig buildMatrix.

    Returns a flat list of build spec dicts.
    """
    builds = []
    idx = 0
    product_id = product_record.id if product_record else None

    for entry in matrix:
        new_specs, count = _expand_matrix_entry(
            entry, repo_base, board, branch, commit_sha, product_id, db, idx,
        )
        builds.extend(new_specs)
        idx += count

    return builds


def _expand_matrix_entry(entry, repo_base, board, branch, commit_sha, product_id, db, idx):
    """Expand a single buildMatrix entry into build specs. Returns (specs, count)."""
    role = entry.get("role", "unknown")
    firmware = entry.get("firmware", f"{repo_base}_fw")
    source = entry.get("source", "head")
    target = "mfg" if "_mfg" in firmware else "app"

    # For "head" app builds, generate 4 sub-builds with sequential versions
    if source == "head" and target == "app" and product_id:
        prefix, max_build = get_max_build_number(db, product_id, target)
        if prefix:
            sub_builds = _generate_head_app_sub_builds(
                board, branch, commit_sha, firmware, prefix, max_build, idx,
            )
            return sub_builds, len(sub_builds)

    specs = []
    for variant in ("release",):
        label = f"{role.upper()}_{variant.upper()}" if target != "mfg" else role.upper()
        version_override = None
        if source == "head" and product_id:
            version_override = auto_increment_version(db, product_id, variant, target)

        if source in ("head", "latest", "latest_prev"):
            specs.append(_make_build_spec(
                board, target, variant, branch, commit_sha,
                label, idx, source, firmware, version_override,
            ))
        idx += 1

    return specs, len(specs) or 1


# ── Build run lifecycle ──────────────────────────────────────────────────


def create_build_jobs(
    db,
    build_run,
    build_specs: List[Dict[str, Any]],
    data,
    product_record,
) -> list:
    """Create BuildJob records for a build run from build specs.

    Handles cache lookups, fingerprinting, version overrides, and base-job linking.
    Returns the list of created build records.
    """
    builds = []
    label_to_id = {}
    specs_with_builds = []

    for spec in build_specs:
        cached_build = None
        fingerprint = None

        if spec.get("source") in ("latest", "latest_prev"):
            skip_count = 1 if spec.get("source") == "latest_prev" else 0
            cached_builds = db.buildjob.find_many(
                where={
                    "productId": product_record.id if product_record else None,
                    "variant": spec["variant"],
                    "target": spec.get("target", "app"),
                    "status": "SUCCESS",
                },
                include={"artifacts": True, "product": True},
                order={"buildNum": "desc"},
                take=skip_count + 1,
            )
            cached_build = cached_builds[skip_count] if len(cached_builds) > skip_count else (cached_builds[0] if cached_builds else None)
            if cached_build:
                logger.info("Cache %s: found %s v=%s (source=%s, skip=%d, total=%d)",
                           spec.get("matrixLabel"), cached_build.id[:8], cached_build.versionString,
                           spec.get("source"), skip_count, len(cached_builds))

        elif spec.get("source") == "head" and spec.get("commitSha"):
            repo_url = ""  # Fingerprint from commit SHA + board + variant
            fingerprint = compute_build_fingerprint(
                repo_url=repo_url, commit_sha=spec["commitSha"],
                board=spec["board"], variant=spec["variant"], config_flags=None,
            )
            cached_build = find_cached_build(db, fingerprint)
            if cached_build:
                logger.info("Cache hit for %s: reusing build %s", spec["matrixLabel"], cached_build.id[:8])

        if cached_build and spec.get("source") in ("latest", "latest_prev"):
            build_data = {
                "productId": product_record.id if product_record else None,
                "board": spec["board"],
                "target": spec["target"],
                "variant": spec["variant"],
                "branch": spec.get("branch", data.branch),
                "commitSha": getattr(cached_build, "commitSha", None),
                "status": "CACHED",
                "buildRunId": build_run.id,
                "matrixLabel": spec.get("matrixLabel"),
                "matrixIndex": spec.get("matrixIndex"),
                "versionBump": False,
                "buildFingerprint": fingerprint,
                "reusedFromId": cached_build.id,
                "versionString": cached_build.versionString,
                "webhookData": Json({
                    "buildRunId": build_run.id,
                    "source": data.trigger_type,
                    "matrixLabel": spec.get("matrixLabel"),
                    "cachedFrom": cached_build.id,
                }),
            }
        else:
            build_data = {
                "productId": product_record.id if product_record else None,
                "board": spec["board"],
                "target": spec["target"],
                "variant": spec["variant"],
                "branch": spec["branch"],
                "commitSha": spec["commitSha"],
                "status": spec["status"],
                "buildRunId": build_run.id,
                "matrixLabel": spec.get("matrixLabel"),
                "matrixIndex": spec.get("matrixIndex"),
                "versionBump": spec.get("versionBump", False),
                "webhookData": Json({
                    "buildRunId": build_run.id,
                    "source": data.trigger_type,
                    "matrixLabel": spec.get("matrixLabel"),
                }),
            }
            if fingerprint:
                build_data["buildFingerprint"] = fingerprint
            if spec.get("versionOverride"):
                override_flags = {
                    "buildRunId": build_run.id,
                    "source": data.trigger_type,
                    "matrixLabel": spec.get("matrixLabel"),
                    "versionOverride": spec["versionOverride"],
                }
                build_data["configFlags"] = Json(override_flags)
                build_data["webhookData"] = Json(override_flags)

        build = db.buildjob.create(data=build_data)
        builds.append(build)
        label_to_id[spec.get("matrixLabel")] = build.id
        specs_with_builds.append((spec, build))

    # Second pass: link version bump builds to their base builds
    for spec, build in specs_with_builds:
        base_label = spec.get("baseLabel")
        if base_label and base_label in label_to_id:
            db.buildjob.update(
                where={"id": build.id},
                data={"baseJobId": label_to_id[base_label]},
            )

    return builds


def check_build_run_completion(run_id: str) -> Optional[str]:
    """Check if all builds in a build run are complete and update status.

    Returns the new status if changed, None otherwise.
    Called by the build status update endpoint when a build finishes.
    """
    db = get_db_client()

    try:
        build_run = db.buildrun.find_unique(
            where={"id": run_id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not build_run:
            return None

        if build_run.status not in ("PENDING", "CLONING", "BUILDING"):
            return None

        builds = build_run.builds or []
        if not builds:
            return None

        completed = sum(1 for b in builds if b.status in ("SUCCESS", "CACHED", "FAILED", "CANCELLED"))
        succeeded = sum(1 for b in builds if b.status in ("SUCCESS", "CACHED"))
        failed = sum(1 for b in builds if b.status in ("FAILED", "CANCELLED"))

        # Fail-fast: if any build fails, cancel all pending/blocked/building siblings
        if failed > 0:
            pending_builds = [b for b in builds if b.status in ("QUEUED", "BLOCKED", "CLONING", "BUILDING")]
            if pending_builds:
                logger.info("Build failed in build run %s, cancelling %d pending/blocked builds",
                           run_id, len(pending_builds))
                for build in pending_builds:
                    db.buildjob.update(
                        where={"id": build.id},
                        data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
                    )
                completed = sum(1 for b in builds if b.status in ("SUCCESS", "FAILED", "CANCELLED"))
                completed += len(pending_builds)

        if completed != build_run.completedBuilds:
            db.buildrun.update(
                where={"id": run_id},
                data={"completedBuilds": completed},
            )

        if completed < len(builds):
            return None

        if failed > 0:
            new_status = "BUILD_FAILED"
            db.buildrun.update(
                where={"id": run_id},
                data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
            )
            logger.info("Build run %s failed: %d/%d builds failed", run_id, failed, len(builds))
            return new_status

        # All builds succeeded — validate artifacts before proceeding
        try:
            validation_result = validate_build_run_artifacts(db, run_id)
            if not validation_result["valid"]:
                new_status = "BUILD_FAILED"
                error_msg = format_missing_artifacts_message(validation_result["missing"])
                db.buildrun.update(
                    where={"id": run_id},
                    data={
                        "status": new_status,
                        "finishedAt": datetime.now(timezone.utc),
                    },
                )
                logger.warning("BuildRun %s artifact validation failed: %s", run_id, error_msg)
                return new_status
        except Exception as val_err:
            logger.exception("BuildRun %s artifact validation error (non-blocking): %s", run_id, val_err)

        # Promote artifacts to FirmwareSets
        try:
            promoted = promote_build_run_to_firmware(run_id)
            if promoted:
                logger.info("BuildRun %s promoted to %d FirmwareSet(s)", run_id, len(promoted))
            else:
                logger.warning("BuildRun %s promotion returned no results", run_id)
        except Exception as promo_err:
            logger.error("BuildRun %s promotion failed (non-blocking): %s", run_id, promo_err)

        # Create unified AssetSet from build artifacts
        try:
            asset_result = create_asset_set_from_build_run(run_id)
            if asset_result:
                logger.info("BuildRun %s → AssetSet %s (%d assets)",
                           run_id, asset_result["assetSetId"], asset_result["assetCount"])
        except Exception as asset_err:
            logger.error("BuildRun %s AssetSet creation failed (non-blocking): %s", run_id, asset_err)

        if build_run.autoRunStage:
            new_status = "VALIDATING"
            db.buildrun.update(
                where={"id": run_id},
                data={"status": new_status},
            )
            logger.info("Build run %s builds complete, auto-triggering validation", run_id)

            result = trigger_build_run_validation(run_id, build_run, builds)
            if result and result.get("started"):
                validation_run_id = result["sessionId"]
                db.buildrun.update(
                    where={"id": run_id},
                    data={"validationRunId": validation_run_id},
                )
                logger.info("Build run %s validation triggered: %s", run_id, validation_run_id)
            elif result and result.get("queued"):
                logger.info(
                    "Build run %s validation queued: entry=%s reason=%s",
                    run_id, result["entryId"][:8], result.get("reason"),
                )
            else:
                new_status = "SUCCESS"
                db.buildrun.update(
                    where={"id": run_id},
                    data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
                )
                logger.warning("Build run %s auto-run-stage failed (no bench?), set to SUCCESS", run_id)
        else:
            new_status = "SUCCESS"
            db.buildrun.update(
                where={"id": run_id},
                data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
            )
            logger.info("Build run %s builds complete (autoRunStage=false), set to SUCCESS", run_id)

        # Auto-progress: DISABLED — uncomment when cross-stage auto-trigger is ready
        # if new_status == "SUCCESS" and build_run.stage and build_run.productId:
        #     try:
        #         from src.services.webhook_trigger import handle_auto_progress
        #         auto_result = handle_auto_progress(build_run.productId, build_run.stage)
        #         if auto_result:
        #             logger.info("Auto-progress: stage %d → %d for product %s, buildRun=%s",
        #                         build_run.stage, build_run.stage + 1, build_run.productId,
        #                         auto_result.get("buildRunId", "?")[:8])
        #     except Exception as e:
        #         logger.warning("Auto-progress failed for build run %s: %s", run_id, e)

        return new_status

    except Exception as e:
        logger.error("Failed to check build run completion %s: %s", run_id, e)
        return None


def _find_available_fixture(db, product_id: str):
    """Find an available fixture with a ready, online slot for the given product.

    Returns (fixture, slot, mtib_address) if found, else (None, None, None).
    """
    fixtures = db.fixture.find_many(
        where={"productId": product_id, "active": True},
        include={"slots": {"include": {"node": True}}, "design": True},
    )

    fixture = None
    slot = None
    mtib_address = None

    for f in fixtures:
        if f.status != "AVAILABLE":
            logger.debug("Fixture %s skipped: status=%s", f.name, f.status)
            continue
        for s in (f.slots or []):
            if not (s.active and s.dutSnr and s.dutDeviceId):
                continue
            node = getattr(s, "node", None)
            if node and node.status == "ONLINE" and node.ipAddress:
                fixture = f
                slot = s
                mtib_address = node.ipAddress
                break
        if fixture:
            break

    return fixture, slot, mtib_address, fixtures


def _is_fixture_available(f) -> bool:
    """Check if a fixture has AVAILABLE status."""
    return f.status == "AVAILABLE"


def _has_configured_slot(f) -> bool:
    """Check if a fixture has at least one active slot with a DUT serial."""
    return any(s.active and s.dutSnr for s in (f.slots or []))


def _has_offline_slot(f) -> bool:
    """Check if any configured slot has a non-ONLINE node."""
    return any(
        s.active and s.dutSnr
        and getattr(getattr(s, "node", None), "status", None) != "ONLINE"
        for s in (f.slots or [])
    )


def _analyze_unavailability(db, fixtures) -> dict:
    """Categorize why no fixture is available.

    Returns dict with keys: locked, offline, unconfigured (each a list of names).
    """
    locked = [f.name for f in fixtures if not _is_fixture_available(f)]
    available = [f for f in fixtures if _is_fixture_available(f)]
    no_slot = [f.name for f in available if not _has_configured_slot(f)]
    offline = [f.name for f in available if _has_configured_slot(f) and _has_offline_slot(f)]
    return {"locked": locked, "offline": offline, "unconfigured": no_slot}


def _queue_validation(db, run_id: str, unavailability: dict) -> dict:
    """Create or return an existing validation queue entry.

    Resolves the AssetSet for the given BuildRun, then queues by assetSetId.
    Returns {"queued": True, "entryId": "...", "reason": "..."}.
    """
    # Resolve the AssetSet for this build run
    asset_set = db.assetset.find_first(where={"buildRunId": run_id})
    if not asset_set:
        logger.warning("No AssetSet for build run %s, cannot queue", run_id[:8])
        return {"queued": False, "reason": "No asset set found for build run"}

    locked = unavailability["locked"]
    offline = unavailability["offline"]
    no_slot = unavailability["unconfigured"]

    existing = db.validationqueueentry.find_first(
        where={"assetSetId": asset_set.id, "status": "QUEUED"},
    )
    if existing:
        logger.info("Queue entry already exists for build run %s (assetSet %s): %s",
                     run_id[:8], asset_set.id[:8], existing.id[:8])
        return {"queued": True, "entryId": existing.id, "reason": f"Fixture locked: {locked}"}

    reason_parts = []
    if locked:
        reason_parts.append(f"locked={locked}")
    if offline:
        reason_parts.append(f"offline={offline}")
    if no_slot:
        reason_parts.append(f"unconfigured={no_slot}")
    reason = f"No fixture available: {'; '.join(reason_parts)}"

    queue_entry = db.validationqueueentry.create(data={
        "assetSetId": asset_set.id,
        "stage": 4,
        "priority": 0,
        "status": "QUEUED",
        "reason": reason,
        "requestedAt": datetime.now(timezone.utc),
    })

    logger.info(
        "Queued validation for build run %s (assetSet %s): entry=%s reason=%s",
        run_id[:8], asset_set.id[:8], queue_entry.id[:8], reason,
    )
    return {"queued": True, "entryId": queue_entry.id, "reason": reason}


def _create_validation_session(db, fixture, slot, mtib_address: str, run_id: str, build_run, product, builds: list) -> dict:
    """Lock the fixture, create session + device + API key records.

    Returns a dict with keys: session, raw_key, api_url.
    """
    db.fixture.update(
        where={"id": fixture.id},
        data={
            "status": "LOCKED",
            "lockedBy": f"buildRun:{run_id}",
            "lockedAt": datetime.now(timezone.utc),
        },
    )
    logger.info("Locked fixture %s for build run %s", fixture.name, run_id[:8])

    build_summaries = [
        {"id": b.id, "product": derive_build_product_slug(b), "variant": b.variant, "version": b.versionString}
        for b in builds
    ]

    session = db.testrun.create(
        data={
            "name": f"FUOTA validation — {product.name} {build_run.branch}",
            "type": "VALIDATION",
            "productId": product.id,
            "fixtureId": fixture.id,
            "buildRunId": run_id,
            "status": "ACTIVE",
            "operatorId": get_system_user_id(db),
            "targetCount": 1,
            "config": Json({
                "buildRunId": run_id,
                "branch": build_run.branch,
                "builds": build_summaries,
                "fixture": {"id": fixture.id, "name": fixture.name, "stationId": fixture.stationId},
                "slot": {
                    "dutDeviceId": slot.dutDeviceId,
                    "dutSnr": slot.dutSnr,
                    "dutImei": slot.dutImei,
                    "dutIccids": slot.dutIccids,
                },
                "mtibAddress": mtib_address,
            }),
        },
    )

    db.runtarget.create(
        data={
            "runId": session.id,
            "slotIndex": 0,
            "slotId": slot.id,
            "serialNumber": slot.dutSnr,
            "deviceId": slot.dutDeviceId,
            "status": "RUNNING",
            "metadata": Json({
                "imei": slot.dutImei,
                "iccids": slot.dutIccids,
                "fixtureSlotId": slot.id,
            }),
        },
    )

    raw_key = f"ck_run_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db.apikey.create(
        data={
            "name": f"Build run validation {session.id}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:12],
            "userId": get_system_user_id(db),
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    api_url = os.environ.get("CONCORD_API_URL", "http://concord-http-api.staging.svc.cluster.local:9001")
    return {"session": session, "raw_key": raw_key, "api_url": api_url}


def trigger_build_run_validation(run_id: str, build_run, builds: list) -> Optional[dict]:
    """Trigger a validation job for a completed build run.

    Returns:
        ``{"started": True, "sessionId": "..."}`` — run started immediately
        ``{"queued": True, "entryId": "..."}`` — queued for later execution
        ``None`` — unrecoverable failure
    """
    db = get_db_client()

    try:
        product = db.product.find_unique(where={"id": build_run.productId}) if build_run.productId else None
        if not product:
            product = db.product.find_first(
                where={"name": {"contains": build_run.product, "mode": "insensitive"}} if hasattr(build_run, "product") and build_run.product else {},
            )
        if not product:
            logger.warning("Product not found for build run %s", run_id)
            return None

        fixture, slot, mtib_address, fixtures = _find_available_fixture(db, product.id)

        if not fixture:
            unavailability = _analyze_unavailability(db, fixtures)
            locked = unavailability["locked"]
            offline = unavailability["offline"]
            no_slot = unavailability["unconfigured"]
            logger.info(
                "No ready bench for %s: locked=%s offline=%s unconfigured=%s",
                product.name, locked, offline, no_slot,
            )
            if locked:
                return _queue_validation(db, run_id, unavailability)
            return None

        logger.info(
            "Selected: fixture=%s slot=%s (SNR=%s device=%s) MTIB=%s",
            fixture.name, slot.id[:8], slot.dutSnr, slot.dutDeviceId, mtib_address,
        )

        ctx = _create_validation_session(db, fixture, slot, mtib_address, run_id, build_run, product, builds)
        session = ctx["session"]
        raw_key = ctx["raw_key"]
        api_url = ctx["api_url"]

        firmware_version = None
        for build in builds:
            if build.versionString and build.variant == "release":
                firmware_version = build.versionString
                break
        if not firmware_version:
            for build in builds:
                if build.versionString:
                    firmware_version = build.versionString
                    break

        fixture_profile_path = ""
        if fixture.design and hasattr(fixture.design, "profileTemplate"):
            fixture_profile_path = f"fixtures/{product.slug}.json"

        image_tag = os.environ.get("ENVIRONMENT", "staging")
        git_commit = os.environ.get("GIT_COMMIT", "unknown")[:7]

        stage_config = None
        stage_name = getattr(build_run, "matrixMode", None) or "fuota"
        stage_map = {"smoke": 1, "driver": 2, "integration": 3, "regression": 4, "fuota": 5}
        stage_num = stage_map.get(stage_name)
        if stage_num and product:
            stage_config = db.productstageconfig.find_first(
                where={"productId": product.id, "stage": stage_num},
            )

        test_enable = {"electrical": False, "app_post": False, "comm_post": False}
        job_name = create_kubernetes_job(
            product=product.name,
            job_id=session.id,
            firmware_path="",
            test_type="validation",
            test_enable=test_enable,
            firmware_version=firmware_version or "unknown",
            run_id=session.id,
            api_key=raw_key,
            api_url=api_url,
            mtib_address=mtib_address or "",
            bench_id=fixture.id,
            device_id=slot.dutDeviceId or "",
            device_snr=slot.dutSnr or "",
            device_imei=slot.dutImei or "",
            device_iccids=",".join(slot.dutIccids) if slot.dutIccids else "",
            fixture_profile_path=fixture_profile_path,
            build_run_id=run_id,
            stage=stage_name,
            image_tag=image_tag,
            test_directory=getattr(stage_config, "testDirectory", None) if stage_config else None,
            test_marker=getattr(stage_config, "testMarker", None) if stage_config else None,
        )

        if not job_name:
            logger.error("Failed to create K8s job for build run %s", run_id)
            db.fixture.update(where={"id": fixture.id}, data={"status": "AVAILABLE", "lockedBy": None, "lockedAt": None})
            return None

        config = session.config if isinstance(session.config, dict) else {}
        config["trigger"] = {
            "jobName": job_name,
            "firmwareVersion": firmware_version,
            "imageTag": image_tag,
            "apiCommit": git_commit,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }
        config["apiUrl"] = api_url

        db.testrun.update(
            where={"id": session.id},
            data={"config": Json(config)},
        )

        log_audit("ci.buildRun.validation_trigger", "BuildRun", run_id, {
            "sessionId": session.id,
            "jobName": job_name,
            "fixtureId": fixture.id,
            "fixtureStationId": fixture.stationId,
        })

        logger.info("Validation triggered for build run %s: session=%s, job=%s", run_id[:8], session.id[:8], job_name)
        return {"started": True, "sessionId": session.id}

    except Exception as e:
        logger.error("Failed to trigger validation for build run %s: %s", run_id, e)
        return None
