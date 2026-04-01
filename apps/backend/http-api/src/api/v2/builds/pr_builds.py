"""PR Pipeline endpoints — PR-centric view of build status across validation stages.

The killer feature: engineers land here and instantly see every PR's validation
health across all 5 stages, per product.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

STAGE_NAMES = {1: "Smoke", 2: "Silicon", 3: "Integration", 4: "Nightly", 5: "FUOTA"}


@require_permissions(Permissions.BUILDS_VIEW)
def list_pr_pipelines():
    """GET /v2/builds/prs — List PRs with build status across all stages.

    Returns PRs grouped by product, showing the latest BuildRun per stage.
    Query params: productId, status (active/completed/failed), page, limit.
    """
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    product_id = request.args.get("productId")
    status_filter = request.args.get("status")  # active, completed, failed

    # Build query — only BuildRuns with PR context
    where: Dict[str, Any] = {"prNumber": {"not": None}}
    if product_id:
        where["productId"] = product_id

    # Get all PR-linked BuildRuns ordered by creation time
    build_runs = db.buildrun.find_many(
        where=where,
        order={"createdAt": "desc"},
        include={"product": True},
    )

    # Group by (productId, prNumber) and pick latest per stage
    pr_groups: Dict[str, Dict[str, Any]] = {}
    for run in build_runs:
        key = f"{run.productId}:{run.prNumber}"
        if key not in pr_groups:
            pr_groups[key] = {
                "prNumber": run.prNumber,
                "prTitle": run.prTitle,
                "prAuthor": run.prAuthor,
                "prUrl": run.prUrl,
                "product": run.product.name if run.product else run.productId,
                "productId": run.productId,
                "sourceBranch": run.sourceBranch or run.branch,
                "targetBranch": run.targetBranch,
                "latestCommit": run.commitSha,
                "updatedAt": run.createdAt.isoformat(),
                "stages": {},
            }

        # Only keep the latest run per stage
        stage = run.stage
        if stage and stage not in pr_groups[key]["stages"]:
            duration = None
            if run.startedAt and run.finishedAt:
                duration = int((run.finishedAt - run.startedAt).total_seconds())
            pr_groups[key]["stages"][stage] = {
                "status": run.status,
                "buildRunId": run.id,
                "commitSha": run.commitSha,
                "completedBuilds": run.completedBuilds,
                "expectedBuilds": run.expectedBuilds,
                "duration": duration,
                "createdAt": run.createdAt.isoformat(),
            }

        # Update latest commit if this run is newer
        if run.commitSha and run.createdAt.isoformat() > pr_groups[key]["updatedAt"]:
            pr_groups[key]["latestCommit"] = run.commitSha
            pr_groups[key]["updatedAt"] = run.createdAt.isoformat()

    # Apply status filter
    pr_list = list(pr_groups.values())
    if status_filter == "active":
        pr_list = [pr for pr in pr_list if any(
            s["status"] in ("PENDING", "BUILDING", "VALIDATING")
            for s in pr["stages"].values()
        )]
    elif status_filter == "failed":
        pr_list = [pr for pr in pr_list if any(
            s["status"] in ("FAILED", "BUILD_FAILED")
            for s in pr["stages"].values()
        )]
    elif status_filter == "completed":
        pr_list = [pr for pr in pr_list if all(
            s["status"] in ("SUCCESS", "CANCELLED")
            for s in pr["stages"].values()
        )]

    # Sort by most recently updated
    pr_list.sort(key=lambda x: x["updatedAt"], reverse=True)

    # Paginate
    total = len(pr_list)
    pages = (total + limit - 1) // limit if limit > 0 else 0
    paginated = pr_list[(page - 1) * limit: page * limit]

    # Fill in missing stages as null
    for pr in paginated:
        for s in range(1, 6):
            if s not in pr["stages"]:
                pr["stages"][s] = None

    return jsonify(ApiResponse.ok({
        "data": paginated,
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_build_summary():
    """GET /v2/builds/summary — Dashboard statistics for the builds system."""
    db = get_db_client()

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    active_runs = db.buildrun.count(where={"status": {"in": ["PENDING", "BUILDING", "VALIDATING"]}})
    queued_jobs = db.buildjob.count(where={"status": "QUEUED"})
    building_jobs = db.buildjob.count(where={"status": {"in": ["BUILDING", "CLONING"]}})

    # 24h success rate
    completed_24h = db.buildrun.count(where={
        "status": {"in": ["SUCCESS", "FAILED", "BUILD_FAILED"]},
        "finishedAt": {"gte": day_ago},
    })
    success_24h = db.buildrun.count(where={
        "status": "SUCCESS",
        "finishedAt": {"gte": day_ago},
    })
    success_rate = round(success_24h / completed_24h, 2) if completed_24h > 0 else None

    # Average build duration (last 24h successful runs)
    recent_success = db.buildrun.find_many(
        where={"status": "SUCCESS", "finishedAt": {"gte": day_ago}},
        order={"finishedAt": "desc"},
        take=50,
    )
    durations = []
    for run in recent_success:
        if run.startedAt and run.finishedAt:
            durations.append(int((run.finishedAt - run.startedAt).total_seconds()))
    avg_duration = round(sum(durations) / len(durations)) if durations else None

    # Per-stage breakdown
    by_stage = []
    for stage_num in range(1, 6):
        active = db.buildrun.count(where={
            "stage": stage_num,
            "status": {"in": ["PENDING", "BUILDING", "VALIDATING"]},
        })
        success = db.buildrun.count(where={
            "stage": stage_num,
            "status": "SUCCESS",
            "finishedAt": {"gte": day_ago},
        })
        failed = db.buildrun.count(where={
            "stage": stage_num,
            "status": {"in": ["FAILED", "BUILD_FAILED"]},
            "finishedAt": {"gte": day_ago},
        })
        by_stage.append({
            "stage": stage_num,
            "name": STAGE_NAMES[stage_num],
            "active": active,
            "success24h": success,
            "failed24h": failed,
        })

    return jsonify(ApiResponse.ok({
        "activeRuns": active_runs,
        "queuedJobs": queued_jobs,
        "buildingJobs": building_jobs,
        "successRate24h": success_rate,
        "avgDurationSeconds": avg_duration,
        "byStage": by_stage,
    }).to_dict()), 200
