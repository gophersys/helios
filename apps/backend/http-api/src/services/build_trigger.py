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

    # Create BuildRun
    build_run = db.buildrun.create(
        data={
            "productId": product_id,
            "board": board,
            "branch": branch,
            "status": "BUILDING",
            "triggerType": "stage",
            "stage": stage_config.stage,
            "stageConfigId": stage_config_id,
            "expectedBuilds": len(build_defs),
            "completedBuilds": 0,
            "startedAt": datetime.now(timezone.utc),
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

    # Create BuildJobs
    jobs_created = []
    for i, build_def in enumerate(build_defs):
        # Determine which repo to clone
        if build_def.fw_type == "mfg":
            repo_url = mfg_repo or fw_repo
        else:
            repo_url = fw_repo

        # Determine initial status (version-bumped builds start BLOCKED)
        initial_status = "BLOCKED" if build_def.is_version_bump else "QUEUED"

        # Find base job ID for version-bumped builds
        base_job_id = None
        if build_def.base_label:
            base_job = next((j for j in jobs_created if j["matrixLabel"] == build_def.base_label), None)
            if base_job:
                base_job_id = base_job["id"]

        # Determine git ref
        git_ref = branch
        if build_def.git_ref == "main":
            git_ref = "main"
        elif build_def.git_ref == "merge":
            git_ref = branch  # In a PR context, this would be the merge commit

        job = db.buildjob.create(
            data={
                "productId": product_id,
                "board": board,
                "target": build_def.fw_type,  # "app" or "mfg"
                "variant": build_def.variant,  # "debug", "release", "mfg"
                "branch": git_ref,
                "status": initial_status,
                "matrixLabel": build_def.label,
                "matrixIndex": i,
                "versionBump": build_def.is_version_bump,
                "baseJobId": base_job_id,
                "buildRunId": build_run.id,
                "webhookData": Json({
                    "repoUrl": repo_url,
                    "builderImage": builder_image,
                    "signingKeyId": stage_config.signingKeyId,
                    "boardRevisionId": revision.id,
                    "ckBoardsName": board,
                }),
            },
        )
        jobs_created.append({"id": job.id, "matrixLabel": build_def.label})

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
