"""Build trigger service — creates BuildRun + BuildJobs from stage configuration.

When a user enables a stage and clicks "Build Now", this service:
1. Reads the product's repos and target revision
2. Gets the StageBuildDef recipe for the stage
3. Creates a BuildRun with BuildJobs for each recipe entry
4. Creates a K8s Job for each BuildJob (using the product's builder image)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import Json

from src.lib.audit import log_audit
from src.services.database.prisma import get_db_client
from src.api.v2.builds.stage_builds import ValidationStage, get_stage_build_defs

logger = logging.getLogger(__name__)

# Map stage numbers to ValidationStage enum
_STAGE_MAP = {
    1: ValidationStage.SMOKE,
    2: ValidationStage.SILICON,
    3: ValidationStage.INTEGRATION,
    4: ValidationStage.NIGHTLY,
    5: ValidationStage.FUOTA,
}


def trigger_stage_build(
    product_id: str,
    stage_config_id: str,
    event_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Create a BuildRun with BuildJobs for a stage.

    Returns {"buildRunId": "...", "jobCount": N} on success, None on failure.
    """
    db = get_db_client()

    # Load product with repos
    product = db.product.find_unique(
        where={"id": product_id},
        include={
            "boards": {
                "include": {
                    "revisions": {
                        "include": {"targets": True},
                    },
                },
            },
        },
    )
    if not product:
        logger.error("Product %s not found", product_id)
        return None

    # Load stage config with revision and signing key
    stage_config = db.productstageconfig.find_unique(
        where={"id": stage_config_id},
        include={
            "boardRevision": True,
            "signingKey": True,
        },
    )
    if not stage_config:
        logger.error("Stage config %s not found", stage_config_id)
        return None

    if not stage_config.boardRevisionId or not stage_config.boardRevision:
        logger.error("Stage config %s has no board revision", stage_config_id)
        return None

    revision = stage_config.boardRevision
    stage_enum = _STAGE_MAP.get(stage_config.stage)
    if not stage_enum:
        logger.error("Unknown stage number: %s", stage_config.stage)
        return None

    # Get build recipe for this stage
    build_defs = get_stage_build_defs(stage_enum)
    if not build_defs:
        logger.error("No build definitions for stage %s", stage_enum)
        return None

    # Determine repos
    fw_repo = f"git@bitbucket.org:corekinect/{product.fwRepoSlug}.git" if product.fwRepoSlug else None
    mfg_repo = f"git@bitbucket.org:corekinect/{product.mfgFwRepoSlug}.git" if product.mfgFwRepoSlug else None
    branch = stage_config.watchBranch or "main"
    board = revision.ckBoardsName  # e.g., "alpha_b0"

    if not fw_repo:
        logger.error("Product %s has no fwRepoSlug", product.name)
        return None

    # Builder image — from product or convention
    builder_image = product.builderImage
    if not builder_image and product.fwRepoSlug:
        builder_image = f"containers.ad.corekinect.com/{product.fwRepoSlug}-builder:latest"

    # Extract trigger context from event metadata
    trigger_type = "manual"
    commit_sha = None
    trigger_data = None
    pr_number = None
    pr_title = None
    pr_author = None
    source_branch = None
    target_branch = None
    pr_url = None

    if event_metadata:
        commit_sha = event_metadata.get("source_commit") or event_metadata.get("commit_sha")
        trigger_data = Json(event_metadata)

        # Normalize trigger type to match ProductStageConfig.triggerTypes vocabulary
        source = event_metadata.get("source", "")
        if event_metadata.get("pr_id"):
            trigger_type = "pr_push"
            branch = event_metadata.get("source_branch", branch)
            # Promote PR fields to first-class columns
            pr_number = event_metadata.get("pr_id")
            pr_title = event_metadata.get("pr_title")
            pr_author = event_metadata.get("pr_author")
            source_branch = event_metadata.get("source_branch")
            target_branch = event_metadata.get("target_branch")
            pr_url = event_metadata.get("pr_url")
        elif source == "auto_progress":
            trigger_type = "auto"
        elif source == "schedule":
            trigger_type = "schedule"
        elif source in ("webhook", "poller"):
            trigger_type = "pr_push"
        else:
            trigger_type = "manual"

    now = datetime.now(timezone.utc)

    # Auto-cancel: cancel in-progress runs for the same PR+stage with older commits
    if pr_number and commit_sha:
        _cancel_stale_runs(db, product_id, pr_number, stage_config.stage, commit_sha)

    # Dedup: skip if an active BuildRun already exists for this exact commit+stage
    if commit_sha:
        existing = db.buildrun.find_first(
            where={
                "productId": product_id,
                "stageConfigId": stage_config_id,
                "commitSha": commit_sha,
                "status": {"in": ["PENDING", "BUILDING"]},
            },
        )
        if existing:
            logger.info("Dedup: BuildRun %s already active for %s stage %d commit %s",
                        existing.id[:8], product.name, stage_config.stage, commit_sha[:7])
            return {"buildRunId": existing.id, "deduplicated": True}

    # Create BuildRun
    build_run = db.buildrun.create(
        data={
            "productId": product_id,
            "board": board,
            "branch": branch,
            "commitSha": commit_sha,
            "status": "BUILDING",
            "triggerType": trigger_type,
            "triggerData": trigger_data,
            "stage": stage_config.stage,
            "stageConfigId": stage_config_id,
            "expectedBuilds": len(build_defs),
            "completedBuilds": 0,
            "startedAt": now,
            # PR context — first-class fields for efficient querying
            "prNumber": pr_number,
            "prTitle": pr_title,
            "prAuthor": pr_author,
            "sourceBranch": source_branch,
            "targetBranch": target_branch,
            "prUrl": pr_url,
            "buildMatrix": Json({
                "mode": stage_enum.value,
                "labels": [d.label for d in build_defs],
                "branch": branch,
                "board": board,
                "builderImage": builder_image,
            }),
            "matrixMode": stage_enum.value,
        },
    )

    logger.info("Created BuildRun %s for %s stage %s (%d jobs)",
                build_run.id, product.name, stage_config.name, len(build_defs))

    # Create BuildJobs — with build cache check
    from src.api.v2.builds.build_cache import compute_build_fingerprint, find_cached_build

    jobs_created = []
    cached_count = 0

    for i, build_def in enumerate(build_defs):
        try:
            # Determine which repo to clone
            if build_def.fw_type == "mfg":
                repo_url = mfg_repo or fw_repo
            else:
                repo_url = fw_repo

            # Determine git ref
            git_ref = branch
            if build_def.git_ref == "main":
                git_ref = "main"
            elif build_def.git_ref == "merge":
                git_ref = branch

            # Determine initial status (version-bumped builds start BLOCKED)
            initial_status = "BLOCKED" if build_def.is_version_bump else "QUEUED"

            # Find base job ID for version-bumped builds
            base_job_id = None
            if build_def.base_label:
                base_job = next((j for j in jobs_created if j["matrixLabel"] == build_def.base_label), None)
                if base_job:
                    base_job_id = base_job["id"]

            config_flags_dict = {
                "config_log": getattr(build_def, "config_log", True),
                "produces_hex": getattr(build_def, "produces_hex", True),
                "produces_cfw": getattr(build_def, "produces_cfw", False),
                "label": build_def.label,
            }

            # Build cache key logic:
            #   fw_type="mfg" → "main" (mfg repo always at main)
            #   git_ref="main" or "merge" → "main" (stable across PR commits)
            #   git_ref="pr" + fw_type="app" → PR commit SHA (changes per push)
            if build_def.fw_type == "mfg" or build_def.git_ref in ("main", "merge"):
                cache_commit = "main"
            else:
                cache_commit = commit_sha
            fingerprint = compute_build_fingerprint(
                repo_url=repo_url,
                commit_sha=cache_commit or "",
                board=board,
                variant=build_def.variant,
                config_flags=config_flags_dict,
            )

            cached_build = find_cached_build(db, fingerprint)

            if cached_build:
                # Cache hit — create job as CACHED, reuse artifacts
                job = db.buildjob.create(
                    data={
                        "productId": product_id,
                        "board": board,
                        "target": build_def.fw_type,
                        "variant": build_def.variant,
                        "branch": git_ref,
                        "status": "CACHED",
                        "matrixLabel": build_def.label,
                        "matrixIndex": i,
                        "configFlags": Json(config_flags_dict),
                        "buildFingerprint": fingerprint,
                        "reusedFromId": cached_build.id,
                        "versionString": cached_build.versionString,
                        "versionBump": False,
                        "buildRunId": build_run.id,
                        "webhookData": Json({"cached": True, "reusedFrom": cached_build.id}),
                    },
                )

                # Copy artifacts from cached build
                if cached_build.artifacts:
                    for art in cached_build.artifacts:
                        db.buildartifact.create(
                            data={
                                "buildJobId": job.id,
                                "name": art.name,
                                "storageKey": art.storageKey,
                                "sizeBytes": art.sizeBytes,
                                "checksum": art.checksum,
                                "role": art.role,
                                "processor": art.processor,
                                "artifactType": art.artifactType,
                            },
                        )

                cached_count += 1
                logger.info("Build cache HIT: %s (%s) → reused from %s",
                            build_def.label, fingerprint[:12], cached_build.id[:8])
            else:
                # Cache miss — create as normal QUEUED/BLOCKED job
                job = db.buildjob.create(
                    data={
                        "productId": product_id,
                        "board": board,
                        "target": build_def.fw_type,
                        "variant": build_def.variant,
                        "branch": git_ref,
                        "status": initial_status,
                        "matrixLabel": build_def.label,
                        "matrixIndex": i,
                        "configFlags": Json(config_flags_dict),
                        "buildFingerprint": fingerprint,
                        "versionBump": build_def.is_version_bump,
                        "baseJobId": base_job_id,
                        "buildRunId": build_run.id,
                        "webhookData": Json({
                            "repoUrl": repo_url,
                            "fwRepoUrl": fw_repo,
                            "mfgRepoUrl": mfg_repo,
                            "fwRepoSlug": product.fwRepoSlug,
                            "mfgRepoSlug": product.mfgFwRepoSlug,
                            "builderImage": builder_image,
                            "signingKeyId": stage_config.signingKeyId,
                            "signingKeyValue": stage_config.signingKey.value if stage_config.signingKey else None,
                            "boardRevisionId": revision.id,
                            "ckBoardsName": board,
                        }),
                    },
                )

            jobs_created.append({"id": job.id, "matrixLabel": build_def.label})
        except Exception:
            logger.exception("Failed to create BuildJob for %s (index %d)", build_def.label, i)

    if cached_count > 0:
        # Update completed count for cached builds
        db.buildrun.update(
            where={"id": build_run.id},
            data={"completedBuilds": cached_count},
        )
        logger.info("Build cache: %d/%d jobs cached (instant)", cached_count, len(build_defs))

    log_audit("buildRun.trigger", "BuildRun", build_run.id, {
        "product": product.name,
        "stage": stage_config.name,
        "board": board,
        "branch": branch,
        "jobCount": len(jobs_created),
    })

    logger.info("Created %d BuildJobs for BuildRun %s", len(jobs_created), build_run.id)

    # Spawn K8s Jobs for QUEUED builds (not BLOCKED ones — they'll spawn when unblocked)
    from src.services.build_job_runner import create_build_k8s_job
    k8s_launched = 0
    for job_info in jobs_created:
        job_record = db.buildjob.find_unique(where={"id": job_info["id"]})
        if job_record and job_record.status == "QUEUED":
            k8s_name = create_build_k8s_job(job_info["id"])
            if k8s_name:
                k8s_launched += 1
                logger.info("Launched K8s build job: %s (%s)", k8s_name, job_info["matrixLabel"])

    logger.info("Launched %d/%d K8s build jobs for BuildRun %s",
                k8s_launched, len(jobs_created), build_run.id)

    return {
        "buildRunId": build_run.id,
        "jobCount": len(jobs_created),
        "k8sLaunched": k8s_launched,
        "jobs": jobs_created,
    }


def _cancel_stale_runs(db, product_id: str, pr_number: int, stage: int, new_commit_sha: str):
    """Cancel in-progress BuildRuns for the same PR+stage with older commits.

    When a developer pushes a new commit, builds for the old commit are wasted compute.
    This mirrors GitHub Actions' auto-cancel behavior.
    """
    stale_runs = db.buildrun.find_many(
        where={
            "productId": product_id,
            "prNumber": pr_number,
            "stage": stage,
            "status": {"in": ["PENDING", "BUILDING"]},
            "commitSha": {"not": new_commit_sha},
        },
    )
    now = datetime.now(timezone.utc)
    for run in stale_runs:
        db.buildjob.update_many(
            where={
                "buildRunId": run.id,
                "status": {"in": ["QUEUED", "BLOCKED", "CLONING", "BUILDING"]},
            },
            data={"status": "CANCELLED", "finishedAt": now},
        )
        db.buildrun.update(
            where={"id": run.id},
            data={"status": "CANCELLED", "finishedAt": now},
        )
        logger.info("Auto-cancelled stale BuildRun %s (PR #%d, stage %d, commit %s superseded by %s)",
                     run.id[:8], pr_number, stage,
                     (run.commitSha or "?")[:7], new_commit_sha[:7])
