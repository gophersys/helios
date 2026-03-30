"""Pipeline business logic — matrix expansion, build creation, completion, validation trigger.

Extracted from api/v2/builds/pipelines.py to keep handlers thin.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import Json

from src.lib.audit import log_audit
from src.services.database.prisma import get_db_client

from src.api.v2.builds.build_cache import compute_build_fingerprint, find_cached_build
from src.api.v2.builds.stage_builds import ValidationStage

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


def serialize_pipeline(p) -> Dict[str, Any]:
    """Serialize a PipelineRun for API response."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
        "board": p.board,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "validationRunId": p.validationRunId,
        "matrixMode": getattr(p, "matrixMode", None),
        "autoValidate": getattr(p, "autoValidate", False),
        "buildMatrix": p.buildMatrix if hasattr(p, "buildMatrix") else None,
        "triggerData": p.triggerData if hasattr(p, "triggerData") else None,
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


def serialize_pipeline_summary(p) -> Dict[str, Any]:
    """Serialize a PipelineRun for list view."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "matrixMode": getattr(p, "matrixMode", None),
        "autoValidate": getattr(p, "autoValidate", False),
        "validationRunId": getattr(p, "validationRunId", None),
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


def resolve_pipeline_context(db, data) -> Dict[str, Any]:
    """Resolve product, repo names, stage config, and build specs for a pipeline.

    Returns a context dict with all the resolved values needed to create
    the pipeline record and build jobs.
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
        "smoke": ValidationStage.SMOKE,
        "silicon": ValidationStage.SILICON,
        "integration": ValidationStage.INTEGRATION,
        "nightly": ValidationStage.NIGHTLY,
        "fuota": ValidationStage.FUOTA,
    }
    stage_number = data.validation_config.get("stage") if data.validation_config else None
    stage = stage_map.get(data.matrix_mode, ValidationStage.FUOTA)

    stage_config = None
    stage_config_matrix = None
    if product_record:
        stage_num = stage_number or {"smoke": 1, "silicon": 2, "integration": 3, "nightly": 4, "fuota": 5}.get(data.matrix_mode, 5)
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


def create_pipeline_record(db, data, ctx: Dict[str, Any]):
    """Create the PipelineRun DB record and its build jobs.

    Returns (pipeline, builds) tuple after creating and re-fetching with includes.
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
        "triggerType": data.trigger_type,
        "expectedBuilds": len(build_specs),
        "matrixMode": data.matrix_mode,
        "autoValidate": data.auto_validate,
        "triggerData": Json(trigger_data),
        "startedAt": datetime.now(timezone.utc),
        "buildMatrix": Json(matrix_config),
    }
    if product_record:
        create_data["productId"] = product_record.id
    if stage_config:
        create_data["stageConfigId"] = stage_config.id
        create_data["stage"] = stage_config.stage

    pipeline = db.pipelinerun.create(data=create_data)
    builds = create_build_jobs(db, pipeline, build_specs, data, product_record)

    log_audit("ci.pipeline.create", "PipelineRun", pipeline.id, {
        "product": product_base,
        "branch": data.branch,
        "commitSha": data.commit_sha,
        "triggerType": data.trigger_type,
        "builds": [b.id for b in builds],
    })

    pipeline = db.pipelinerun.find_unique(
        where={"id": pipeline.id},
        include={"builds": {"include": {"product": True}}, "product": True},
    )

    return pipeline, builds


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

    Each matrix entry produces TWO builds (debug + release).
    - source == "head": new build from the triggering commit, auto-versioned.
    - source == "latest": reference to the latest successful build (CACHED).

    The firmware field determines the target type:
    - Contains "_mfg" -> target="mfg" (manufacturing firmware)
    - Otherwise -> target="app" (production firmware)

    Returns a flat list of build spec dicts.
    """
    builds = []
    idx = 0
    product_id = product_record.id if product_record else None

    for entry in matrix:
        role = entry.get("role", "unknown")
        firmware = entry.get("firmware", f"{repo_base}_fw")
        source = entry.get("source", "head")

        # Derive target from firmware name
        target = "mfg" if "_mfg" in firmware else "app"

        # All builds are release variant — no debug flag in CFW
        variants = ("release",)

        # For "head" app builds, generate 4 sub-builds with sequential versions
        if source == "head" and target == "app":
            prefix, max_build = get_max_build_number(db, product_id, target) if product_id else (None, 0)
            if prefix:
                sub_builds = [
                    ("PROD_VERBOSE",      prefix, max_build + 1, True),
                    ("PROD_VERBOSE_BUMP", prefix, max_build + 2, True),
                    ("PROD_QUIET",        prefix, max_build + 3, False),
                    ("PROD_QUIET_BUMP",   prefix, max_build + 4, False),
                ]
                logger.info(
                    "FUOTA version allocation: VERBOSE=v%s.%d/%d, QUIET=v%s.%d/%d (max=%s.%d)",
                    prefix, max_build + 1, max_build + 2,
                    prefix, max_build + 3, max_build + 4,
                    prefix, max_build,
                )
                for sub_label, ver_prefix, ver_build, force_log in sub_builds:
                    config = {"forceLog": True} if force_log else {}
                    builds.append({
                        "board": board,
                        "target": target,
                        "variant": "release",
                        "branch": branch,
                        "commitSha": commit_sha,
                        "status": "QUEUED",
                        "matrixLabel": sub_label,
                        "matrixIndex": idx,
                        "versionBump": False,
                        "source": "head",
                        "firmware": firmware,
                        "versionOverride": f"{ver_prefix}.{ver_build}",
                        "extraConfig": config,
                    })
                    idx += 1
                continue

        for variant in variants:
            label = f"{role.upper()}_{variant.upper()}" if target != "mfg" else role.upper()

            if source == "head":
                version_override = auto_increment_version(db, product_id, variant, target) if product_id else None

                builds.append({
                    "board": board,
                    "target": target,
                    "variant": variant,
                    "mtibRev": "1.2",
                    "branch": branch,
                    "commitSha": commit_sha,
                    "status": "QUEUED",
                    "matrixLabel": label,
                    "matrixIndex": idx,
                    "versionBump": False,
                    "source": "head",
                    "firmware": firmware,
                    "versionOverride": version_override,
                })
            elif source in ("latest", "latest_prev"):
                builds.append({
                    "board": board,
                    "target": target,
                    "variant": variant,
                    "mtibRev": "1.2",
                    "branch": branch,
                    "commitSha": None,
                    "status": "QUEUED",
                    "matrixLabel": label,
                    "matrixIndex": idx,
                    "versionBump": False,
                    "source": source,
                    "firmware": firmware,
                })
            idx += 1

    return builds


# ── Pipeline lifecycle ───────────────────────────────────────────────────


def create_build_jobs(
    db,
    pipeline,
    build_specs: List[Dict[str, Any]],
    data,
    product_record,
) -> list:
    """Create BuildJob records for a pipeline from build specs.

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
                "pipelineRunId": pipeline.id,
                "matrixLabel": spec.get("matrixLabel"),
                "matrixIndex": spec.get("matrixIndex"),
                "versionBump": False,
                "buildFingerprint": fingerprint,
                "reusedFromId": cached_build.id,
                "versionString": cached_build.versionString,
                "webhookData": Json({
                    "pipelineId": pipeline.id,
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
                "pipelineRunId": pipeline.id,
                "matrixLabel": spec.get("matrixLabel"),
                "matrixIndex": spec.get("matrixIndex"),
                "versionBump": spec.get("versionBump", False),
                "webhookData": Json({
                    "pipelineId": pipeline.id,
                    "source": data.trigger_type,
                    "matrixLabel": spec.get("matrixLabel"),
                }),
            }
            if fingerprint:
                build_data["buildFingerprint"] = fingerprint
            if spec.get("versionOverride"):
                override_flags = {
                    "pipelineId": pipeline.id,
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


def check_pipeline_completion(pipeline_id: str) -> Optional[str]:
    """Check if all builds in a pipeline are complete and update status.

    Returns the new status if changed, None otherwise.
    Called by the build status update endpoint when a build finishes.
    """
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not pipeline:
            return None

        if pipeline.status not in ("PENDING", "CLONING", "BUILDING"):
            return None

        builds = pipeline.builds or []
        if not builds:
            return None

        completed = sum(1 for b in builds if b.status in ("SUCCESS", "CACHED", "FAILED", "CANCELLED"))
        succeeded = sum(1 for b in builds if b.status in ("SUCCESS", "CACHED"))
        failed = sum(1 for b in builds if b.status in ("FAILED", "CANCELLED"))

        # Fail-fast: if any build fails, cancel all pending/blocked/building siblings
        if failed > 0:
            pending_builds = [b for b in builds if b.status in ("QUEUED", "BLOCKED", "CLONING", "BUILDING")]
            if pending_builds:
                logger.info("Build failed in pipeline %s, cancelling %d pending/blocked builds",
                           pipeline_id, len(pending_builds))
                for build in pending_builds:
                    db.buildjob.update(
                        where={"id": build.id},
                        data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
                    )
                completed = sum(1 for b in builds if b.status in ("SUCCESS", "FAILED", "CANCELLED"))
                completed += len(pending_builds)

        if completed != pipeline.completedBuilds:
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"completedBuilds": completed},
            )

        if completed < len(builds):
            return None

        if failed > 0:
            new_status = "BUILD_FAILED"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
            )
            logger.info("Pipeline %s failed: %d/%d builds failed", pipeline_id, failed, len(builds))
            return new_status

        # All builds succeeded — validate artifacts before proceeding
        from src.services.artifact_validator import (
            validate_pipeline_artifacts,
            format_missing_artifacts_message,
        )
        validation_result = validate_pipeline_artifacts(db, pipeline_id)
        if not validation_result["valid"]:
            new_status = "BUILD_FAILED"
            error_msg = format_missing_artifacts_message(validation_result["missing"])
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={
                    "status": new_status,
                    "finishedAt": datetime.now(timezone.utc),
                },
            )
            logger.warning("Pipeline %s artifact validation failed: %s", pipeline_id, error_msg)
            return new_status

        if getattr(pipeline, "autoValidate", False):
            new_status = "VALIDATING"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"status": new_status},
            )
            logger.info("Pipeline %s builds complete, auto-triggering validation", pipeline_id)

            result = trigger_pipeline_validation(pipeline_id, pipeline, builds)
            if result and result.get("started"):
                validation_run_id = result["sessionId"]
                db.pipelinerun.update(
                    where={"id": pipeline_id},
                    data={"validationRunId": validation_run_id},
                )
                logger.info("Pipeline %s validation triggered: %s", pipeline_id, validation_run_id)
            elif result and result.get("queued"):
                logger.info(
                    "Pipeline %s validation queued: entry=%s reason=%s",
                    pipeline_id, result["entryId"][:8], result.get("reason"),
                )
            else:
                new_status = "SUCCESS"
                db.pipelinerun.update(
                    where={"id": pipeline_id},
                    data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
                )
                logger.warning("Pipeline %s auto-validate failed (no bench?), set to SUCCESS", pipeline_id)
        else:
            new_status = "SUCCESS"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
            )
            logger.info("Pipeline %s builds complete (autoValidate=false), set to SUCCESS", pipeline_id)

        return new_status

    except Exception as e:
        logger.error("Failed to check pipeline completion %s: %s", pipeline_id, e)
        return None


def trigger_pipeline_validation(pipeline_id: str, pipeline, builds: list) -> Optional[dict]:
    """Trigger a validation job for a completed pipeline.

    Returns:
        ``{"started": True, "sessionId": "..."}`` — run started immediately
        ``{"queued": True, "entryId": "..."}`` — queued for later execution
        ``None`` — unrecoverable failure
    """
    from src.api.v2.sessions.manual import create_kubernetes_job

    db = get_db_client()

    try:
        product = db.product.find_unique(where={"id": pipeline.productId}) if pipeline.productId else None
        if not product:
            product = db.product.find_first(
                where={"name": {"contains": pipeline.product, "mode": "insensitive"}} if hasattr(pipeline, "product") and pipeline.product else {},
            )
        if not product:
            logger.warning("Product not found for pipeline %s", pipeline_id)
            return None

        # Find an available fixture with a ready slot
        fixtures = db.fixture.find_many(
            where={
                "productId": product.id,
                "active": True,
            },
            include={
                "slots": {"include": {"node": True}},
                "design": True,
            },
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

        if not fixture:
            locked = [f.name for f in fixtures if f.status != "AVAILABLE"]
            no_slot = [f.name for f in fixtures if f.status == "AVAILABLE"
                       and not any(s.active and s.dutSnr for s in (f.slots or []))]
            offline = [f.name for f in fixtures if f.status == "AVAILABLE"
                       and any(s.active and s.dutSnr and getattr(getattr(s, "node", None), "status", None) != "ONLINE"
                               for s in (f.slots or []))]
            logger.info(
                "No ready bench for %s: locked=%s offline=%s unconfigured=%s",
                product.name, locked, offline, no_slot,
            )

            if locked:
                existing = db.validationqueueentry.find_first(
                    where={"pipelineRunId": pipeline_id, "status": "QUEUED"},
                )
                if existing:
                    logger.info("Queue entry already exists for pipeline %s: %s", pipeline_id[:8], existing.id[:8])
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
                    "pipelineRunId": pipeline_id,
                    "stage": 4,
                    "priority": 0,
                    "status": "QUEUED",
                    "reason": reason,
                    "requestedAt": datetime.now(timezone.utc),
                })

                logger.info(
                    "Queued validation for pipeline %s: entry=%s reason=%s",
                    pipeline_id[:8], queue_entry.id[:8], reason,
                )
                return {"queued": True, "entryId": queue_entry.id, "reason": reason}

            return None

        logger.info(
            "Selected: fixture=%s slot=%s (SNR=%s device=%s) MTIB=%s",
            fixture.name, slot.id[:8], slot.dutSnr, slot.dutDeviceId, mtib_address,
        )

        # Lock the fixture
        db.fixture.update(
            where={"id": fixture.id},
            data={
                "status": "LOCKED",
                "lockedBy": f"pipeline:{pipeline_id}",
                "lockedAt": datetime.now(timezone.utc),
            },
        )
        logger.info("Locked fixture %s for pipeline %s", fixture.name, pipeline_id[:8])

        # Create a validation session
        build_summaries = []
        for b in builds:
            slug = derive_build_product_slug(b)
            build_summaries.append({"id": b.id, "product": slug, "variant": b.variant, "version": b.versionString})

        session = db.session.create(
            data={
                "name": f"FUOTA validation — {product.name} {pipeline.branch}",
                "type": "VALIDATION",
                "productId": product.id,
                "fixtureId": fixture.id,
                "pipelineRunId": pipeline_id,
                "status": "ACTIVE",
                "config": Json({
                    "pipelineId": pipeline_id,
                    "branch": pipeline.branch,
                    "builds": build_summaries,
                    "fixture": {
                        "id": fixture.id,
                        "name": fixture.name,
                        "stationId": fixture.stationId,
                    },
                    "slot": {
                        "dutDeviceId": slot.dutDeviceId,
                        "dutSnr": slot.dutSnr,
                        "dutImei": slot.dutImei,
                        "dutIccids": slot.dutIccids,
                    },
                    "mtibAddress": mtib_address,
                }),
                "createdById": get_system_user_id(db),
            },
        )

        # Create device record
        db.device.create(
            data={
                "serialNumber": slot.dutSnr,
                "sessionId": session.id,
                "status": "IN_PROGRESS",
                "metadata": Json({
                    "deviceId": slot.dutDeviceId,
                    "imei": slot.dutImei,
                    "iccids": slot.dutIccids,
                    "fixtureSlotId": slot.id,
                }),
            },
        )

        # Create API key for the K8s job
        raw_key = f"ck_run_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        db.apikey.create(
            data={
                "name": f"Pipeline validation {session.id}",
                "keyHash": key_hash,
                "keyPrefix": raw_key[:12],
                "userId": get_system_user_id(db),
                "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
            },
        )

        api_url = os.environ.get("CONCORD_API_URL", "http://concord-http-api.staging.svc.cluster.local:9001")

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

        # Load stage config for test routing
        stage_config = None
        stage_name = getattr(pipeline, "matrixMode", None) or "fuota"
        stage_map = {"smoke": 1, "silicon": 2, "integration": 3, "nightly": 4, "fuota": 5}
        stage_num = stage_map.get(stage_name)
        if stage_num and product:
            stage_config = db.productstageconfig.find_first(
                where={"productId": product.id, "stage": stage_num},
            )

        # Create K8s Job
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
            pipeline_id=pipeline_id,
            stage=stage_name,
            image_tag=image_tag,
            test_directory=getattr(stage_config, "testDirectory", None) if stage_config else None,
            test_marker=getattr(stage_config, "testMarker", None) if stage_config else None,
        )

        if not job_name:
            logger.error("Failed to create K8s job for pipeline %s", pipeline_id)
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

        db.session.update(
            where={"id": session.id},
            data={"config": Json(config)},
        )

        log_audit("ci.pipeline.validation_trigger", "PipelineRun", pipeline_id, {
            "sessionId": session.id,
            "jobName": job_name,
            "fixtureId": fixture.id,
            "fixtureStationId": fixture.stationId,
        })

        logger.info("Validation triggered for pipeline %s: session=%s, job=%s", pipeline_id[:8], session.id[:8], job_name)
        return {"started": True, "sessionId": session.id}

    except Exception as e:
        logger.error("Failed to trigger validation for pipeline %s: %s", pipeline_id, e)
        return None
