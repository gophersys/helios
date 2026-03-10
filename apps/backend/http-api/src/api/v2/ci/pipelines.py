"""CI Pipeline coordination — groups builds and triggers validation."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import PipelineCreateRequest
from .stage4_matrix import (
    Stage4MatrixConfig,
    generate_stage4_builds,
    generate_quick_builds,
    calculate_expected_builds,
)

logger = logging.getLogger(__name__)


def _serialize_pipeline(p) -> Dict[str, Any]:
    """Serialize a PipelineRun for API response."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": p.product,
        "board": p.board,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "validationRunId": p.validationRunId,
        "matrixMode": getattr(p, "matrixMode", None),
        "buildMatrix": p.buildMatrix if hasattr(p, "buildMatrix") else None,
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
                "product": b.product,
                "status": b.status,
                "variant": b.variant,
                "buildNum": b.buildNum,
                "versionString": b.versionString,
                "durationSeconds": b.durationSeconds,
                "artifactCount": len(b.artifacts) if hasattr(b, "artifacts") and b.artifacts else 0,
                # Stage 4 matrix fields
                "matrixLabel": getattr(b, "matrixLabel", None),
                "matrixIndex": getattr(b, "matrixIndex", None),
                "versionBump": getattr(b, "versionBump", False),
                "baseJobId": getattr(b, "baseJobId", None),
            }
            for b in p.builds
        ]

    return data


def _serialize_pipeline_summary(p) -> Dict[str, Any]:
    """Serialize a PipelineRun for list view."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": p.product,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "matrixMode": getattr(p, "matrixMode", None),
        "startedAt": p.startedAt.isoformat() if p.startedAt else None,
        "finishedAt": p.finishedAt.isoformat() if p.finishedAt else None,
        "createdAt": p.createdAt.isoformat(),
    }

    # Include builds summary for Stage 4 matrix display
    if hasattr(p, "builds") and p.builds:
        data["builds"] = [
            {
                "id": b.id,
                "product": b.product,
                "status": b.status,
                "variant": b.variant,
                "matrixLabel": getattr(b, "matrixLabel", None),
                "matrixIndex": getattr(b, "matrixIndex", None),
                "versionBump": getattr(b, "versionBump", False),
            }
            for b in sorted(p.builds, key=lambda x: getattr(x, "matrixIndex", 0) or 0)
        ]

    return data


@require_permissions(Permissions.ADMIN_CI_VIEW)
def list_pipelines():
    """GET /v2/ci/pipelines — List pipeline runs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    # Filters
    product = request.args.get("product")
    branch = request.args.get("branch")
    status = request.args.get("status")

    where: Dict[str, Any] = {}
    if product:
        where["product"] = product
    if branch:
        where["branch"] = branch
    if status:
        where["status"] = status

    try:
        total = db.pipelinerun.count(where=where)
        pipelines = db.pipelinerun.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"builds": True},  # Include builds for Stage 4 matrix display
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        return jsonify(ApiResponse.paginated(
            data=[_serialize_pipeline_summary(p) for p in pipelines],
            page=page,
            total_pages=pages,
            total_results=total,
            results_per_page=limit,
        ).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list pipelines: %s", e)
        return internal_error("Failed to list pipelines")


@require_permissions(Permissions.ADMIN_CI_VIEW)
def get_pipeline(pipeline_id: str):
    """GET /v2/ci/pipelines/<id> — Get pipeline details with builds."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"artifacts": True}}},
        )
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        return jsonify(ApiResponse.ok(_serialize_pipeline(pipeline)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to get pipeline")


@require_permissions(Permissions.ADMIN_CI_VIEW)
def download_pipeline_artifacts(pipeline_id: str):
    """GET /v2/ci/pipelines/<id>/artifacts/download — Download all artifacts as ZIP.

    Creates a structured ZIP containing all builds:
      <product>_<branch>_<sha>/
        alpha_fw/
          debug/
            firmware/
              app_nrf52840.hex
              comms_nrf9151.hex
            cfw/
              108.x.x.x.cfw
              109.x.x.x.cfw
            build.json
          release/
            firmware/...
            cfw/...
        alpha_mfg_fw/
          debug/...
          release/...
    """
    import io
    import re
    import zipfile
    from flask import Response
    from src.services.storage.client import get_storage_client

    db = get_db_client()

    pipeline = db.pipelinerun.find_unique(
        where={"id": pipeline_id},
        include={"builds": {"include": {"artifacts": True}}},
    )
    if not pipeline:
        return not_found(f"Pipeline not found: {pipeline_id}")

    if not pipeline.builds:
        return not_found("No builds found for this pipeline")

    def get_clean_name(name: str) -> str:
        """Strip version/variant prefix from artifact name."""
        match = re.match(r'^\d+\.\d+\.\d+_(debug|no_debug|release)_(.+)$', name)
        return match.group(2) if match else name

    def get_folder(name: str) -> str:
        """Determine subfolder for artifact."""
        if name.endswith('.hex') or name.endswith('.bin'):
            return "firmware"
        elif name.endswith('.cfw'):
            return "cfw"
        return ""

    try:
        storage = get_storage_client()

        # Root folder name
        commit_short = pipeline.commitSha[:7] if pipeline.commitSha else "build"
        branch_safe = re.sub(r'[^\w\-]', '_', pipeline.branch or "main")
        root_folder = f"{pipeline.product}_{branch_safe}_{commit_short}"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for build in pipeline.builds:
                if not build.artifacts:
                    continue

                variant = build.variant or "release"
                # Map no_debug -> release for folder naming
                variant_folder = "release" if variant == "no_debug" else variant

                for artifact in build.artifacts:
                    try:
                        response = storage.get_object("concord", artifact.storageKey)
                        content = response.read()
                        response.close()
                        response.release_conn()

                        clean_name = get_clean_name(artifact.name)
                        subfolder = get_folder(clean_name)

                        if subfolder:
                            zip_path = f"{root_folder}/{build.product}/{variant_folder}/{subfolder}/{clean_name}"
                        else:
                            zip_path = f"{root_folder}/{build.product}/{variant_folder}/{clean_name}"

                        zf.writestr(zip_path, content)
                    except Exception as e:
                        logger.warning("Failed to add %s to ZIP: %s", artifact.name, e)
                        continue

        zip_buffer.seek(0)
        zip_filename = f"{root_folder}.zip"

        return Response(
            zip_buffer.getvalue(),
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Length": str(len(zip_buffer.getvalue())),
            },
        )

    except Exception as e:
        logger.error("Failed to create ZIP for pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to create artifact ZIP")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def create_pipeline():
    """POST /v2/ci/pipelines — Create a new pipeline (triggers builds).

    Can be triggered manually (UI) or by git poller. Git poller provides:
    - productId: DB product ID for linking
    - repoSlug: Git repo slug (e.g. "alpha_fw")
    - commitSha: Commit to build
    - triggerType: "poller"
    - mfgRepoSlug: Manufacturing firmware repo (optional)
    """
    data, error = PipelineCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Get product info - either by ID (poller) or lookup by name/slug
    product_record = None
    if data.product_id:
        product_record = db.product.find_unique(where={"id": data.product_id})
    if not product_record:
        # Try by slug or name
        product_record = db.product.find_first(
            where={"OR": [{"slug": data.product}, {"repoSlug": data.product}]}
        )

    # Determine product/repo base name for builds
    # Build jobs use repo slugs (alpha_fw, alpha_mfg_fw), not product slugs (alpha_b0)
    repo_slug = data.repo_slug or data.product
    # Normalize: remove _fw/_mfg suffixes, spaces, board suffixes (b0/a0)
    # "Alpha B0" -> "alpha", "alpha_fw" -> "alpha", "alpha b0_mfg_fw" -> "alpha"
    repo_base = repo_slug.lower().replace(" ", "_").replace("_fw", "").replace("_mfg", "")
    # Remove board suffixes like _b0, _a0
    for suffix in ["_b0", "_a0", "_b1", "_a1"]:
        repo_base = repo_base.replace(suffix, "")
    repo_base = repo_base.strip("_")  # "alpha"

    # Product base for pipeline naming (use product name if found)
    product_base = repo_base
    if product_record:
        product_base = product_record.name.lower().replace(" ", "_")  # "alpha"

    # Determine which firmware builds are needed based on matrix mode
    main_fw = f"{repo_base}_fw"  # alpha_fw
    mfg_fw = data.mfg_repo_slug or f"{repo_base}_mfg_fw"  # alpha_mfg_fw

    # Build matrix configuration (stage4 or quick mode only)
    stage4_config = Stage4MatrixConfig(
        product=repo_base,
        board=data.board,
        main_branch="main",
        main_commit=data.main_commit or data.commit_sha or "HEAD",
        pr_branch=data.pr_branch or data.branch,
        pr_commit=data.commit_sha or "HEAD",
        merge_commit=None,  # TODO: Support simulated merge
        mtib_rev="1.2",
    )

    if data.matrix_mode == "stage4":
        build_specs = generate_stage4_builds(stage4_config)
    else:  # quick
        build_specs = generate_quick_builds(stage4_config)

    expected_builds = len(build_specs)

    try:
        # Create pipeline run
        trigger_data = {
            "source": data.trigger_type,
            "repoSlug": data.repo_slug,
            "mfgRepoSlug": data.mfg_repo_slug,
        }
        if data.validation_config:
            trigger_data.update(data.validation_config)

        # Store matrix config in pipeline
        matrix_config = {
            "mode": data.matrix_mode,
            "product": repo_base,
            "mainCommit": data.main_commit or data.commit_sha,
            "prBranch": data.pr_branch or data.branch,
            "prCommit": data.commit_sha,
        }

        # Build create data - conditionally include buildMatrix only when provided
        create_data = {
            "name": data.name or f"{product_base}-{data.branch[:8]}" + (f"-{data.commit_sha[:7]}" if data.commit_sha else ""),
            "product": product_base,
            "board": data.board,
            "branch": data.branch,
            "commitSha": data.commit_sha,
            "status": "PENDING",
            "triggerType": data.trigger_type,
            "expectedBuilds": expected_builds,
            "matrixMode": data.matrix_mode,
            "triggerData": Json(trigger_data),
            "startedAt": datetime.now(timezone.utc),
        }
        # Always include buildMatrix (stage4/quick modes always have config)
        create_data["buildMatrix"] = Json(matrix_config)

        pipeline = db.pipelinerun.create(data=create_data)

        # Create build jobs based on mode
        # Create build jobs from matrix specs
        builds = []
        label_to_id = {}  # Track created jobs for baseJobId linking
        specs_with_builds = []  # Track specs with their created builds

        for spec in build_specs:
            build_data = {
                "product": spec["product"],
                "productId": product_record.id if product_record else None,
                "board": spec["board"],
                "target": spec["target"],
                "variant": spec["variant"],
                "mtibRev": spec["mtibRev"],
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

        # Keep pipeline PENDING - status changes to BUILDING when a worker starts a job
        # This is handled by the build status update endpoint

        log_audit("ci.pipeline.create", "PipelineRun", pipeline.id, {
            "product": product_base,
            "branch": data.branch,
            "commitSha": data.commit_sha,
            "triggerType": data.trigger_type,
            "builds": [b.id for b in builds],
        })

        # Refetch with builds
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline.id},
            include={"builds": True},
        )

        return jsonify(ApiResponse.created(_serialize_pipeline(pipeline)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create pipeline: %s", e)
        return internal_error("Failed to create pipeline")


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def cancel_pipeline(pipeline_id: str):
    """POST /v2/ci/pipelines/<id>/cancel — Cancel a pipeline."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        if pipeline.status in ("SUCCESS", "FAILED", "CANCELLED"):
            return bad_request(f"Pipeline already in terminal state: {pipeline.status}")

        # Cancel all pending/building jobs
        db.buildjob.update_many(
            where={
                "pipelineRunId": pipeline_id,
                "status": {"in": ["QUEUED", "BUILDING"]},
            },
            data={"status": "CANCELLED"},
        )

        # Update pipeline
        pipeline = db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
            include={"builds": True},
        )

        log_audit("ci.pipeline.cancel", "PipelineRun", pipeline_id, {})

        return jsonify(ApiResponse.ok(_serialize_pipeline(pipeline)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to cancel pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to cancel pipeline")


def check_pipeline_completion(pipeline_id: str) -> Optional[str]:
    """
    Check if all builds in a pipeline are complete and update status.
    Returns the new status if changed, None otherwise.

    Called by the build status update endpoint when a build finishes.
    """
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": True},
        )
        if not pipeline:
            return None

        if pipeline.status not in ("PENDING", "BUILDING"):
            return None  # Already in terminal state

        builds = pipeline.builds or []
        if not builds:
            return None

        # Count build statuses
        completed = sum(1 for b in builds if b.status in ("SUCCESS", "FAILED", "CANCELLED"))
        succeeded = sum(1 for b in builds if b.status == "SUCCESS")
        failed = sum(1 for b in builds if b.status in ("FAILED", "CANCELLED"))

        # Fail-fast: if any build fails, cancel all pending/blocked/building siblings
        if failed > 0:
            pending_builds = [b for b in builds if b.status in ("QUEUED", "BLOCKED", "BUILDING")]
            if pending_builds:
                logger.info("Build failed in pipeline %s, cancelling %d pending/blocked builds",
                           pipeline_id, len(pending_builds))
                for build in pending_builds:
                    db.buildjob.update(
                        where={"id": build.id},
                        data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
                    )
                # Refresh completed count after cancellation
                completed = sum(1 for b in builds if b.status in ("SUCCESS", "FAILED", "CANCELLED"))
                completed += len(pending_builds)  # Add the just-cancelled builds

        # Update completed count
        if completed != pipeline.completedBuilds:
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"completedBuilds": completed},
            )

        # Check if all builds are done
        if completed < len(builds):
            return None  # Still waiting

        # All builds complete - determine final status
        if failed > 0:
            new_status = "BUILD_FAILED"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
            )
            logger.info("Pipeline %s failed: %d/%d builds failed", pipeline_id, failed, len(builds))
            return new_status

        # All builds succeeded - trigger validation
        new_status = "VALIDATING"
        db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": new_status},
        )
        logger.info("Pipeline %s builds complete, triggering validation", pipeline_id)

        # Trigger validation job
        validation_run_id = trigger_pipeline_validation(pipeline_id, pipeline, builds)
        if validation_run_id:
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"validationRunId": validation_run_id},
            )
            logger.info("Pipeline %s validation triggered: %s", pipeline_id, validation_run_id)

        return new_status

    except Exception as e:
        logger.error("Failed to check pipeline completion %s: %s", pipeline_id, e)
        return None


def trigger_pipeline_validation(pipeline_id: str, pipeline, builds: list) -> Optional[str]:
    """
    Trigger a validation job for a completed pipeline.
    Creates a validation session and K8s job with the build artifacts.
    Returns the validation run ID if successful.
    """
    import hashlib
    import os
    import secrets
    from datetime import timedelta

    from src.api.v2.validation.tests.run import create_kubernetes_job

    db = get_db_client()

    try:
        # Look up the product by name
        product = db.product.find_first(
            where={"name": {"contains": pipeline.product, "mode": "insensitive"}},
        )
        if not product:
            logger.warning("Product not found for pipeline %s: %s", pipeline_id, pipeline.product)
            return None

        # Find an available test bench for this product
        bench = db.testbench.find_first(
            where={
                "dutProduct": pipeline.product.lower(),
                "status": "AVAILABLE",
            },
        )
        if not bench:
            logger.warning("No available test bench for product %s", pipeline.product)
            return None

        # Lock the bench for this pipeline
        db.testbench.update(
            where={"id": bench.id},
            data={
                "status": "LOCKED",
                "lockedBy": pipeline_id,
                "lockedAt": datetime.now(timezone.utc),
            },
        )
        logger.info("Locked bench %s (%s) for pipeline %s", bench.stationId, bench.id, pipeline_id)

        # Create a validation session
        session = db.session.create(
            data={
                "name": f"Pipeline {pipeline.name} - {pipeline.branch}",
                "productId": product.id,
                "status": "ACTIVE",
                "config": Json({
                    "pipelineId": pipeline_id,
                    "branch": pipeline.branch,
                    "builds": [{"id": b.id, "product": b.product, "buildNum": b.buildNum} for b in builds],
                    "bench": {
                        "id": bench.id,
                        "stationId": bench.stationId,
                        "mtibAddress": bench.mtibAddress,
                        "dutDeviceId": bench.dutDeviceId,
                        "dutSnr": bench.dutSnr,
                    },
                }),
            },
        )

        # Create API key for the K8s job
        raw_key = f"ck_run_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Use a system user for pipeline-triggered runs
        system_user = db.user.find_first(where={"email": "system@concord.local"})
        if not system_user:
            # Create system user if it doesn't exist
            system_user = db.user.create(
                data={
                    "name": "System",
                    "email": "system@concord.local",
                },
            )

        db.apikey.create(
            data={
                "name": f"Pipeline validation {session.id}",
                "keyHash": key_hash,
                "keyPrefix": raw_key[:12],
                "userId": system_user.id,
                "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
            },
        )

        # Get API URL for reporter
        api_url = os.environ.get("CONCORD_API_URL", "https://10.4.45.11:443")

        # Get firmware artifacts from builds
        # Look for the mfg hex files (used for J-Link flash)
        firmware_path = ""
        for build in builds:
            if "_mfg_" in build.product:
                # Use mfg firmware for initial flash
                artifacts = db.buildjobartifact.find_many(
                    where={"buildJobId": build.id, "name": {"contains": "merged.hex"}},
                )
                if artifacts:
                    firmware_path = artifacts[0].storageKey
                    break

        # Determine test configuration
        test_enable = {
            "electrical": True,
            "app_post": True,
            "comm_post": True,
        }

        # Get firmware version from one of the builds
        firmware_version = None
        for build in builds:
            if build.versionString:
                firmware_version = build.versionString
                break

        # Create K8s Job
        job_name = create_kubernetes_job(
            product=product.name,
            job_id=session.id,
            firmware_path=firmware_path,
            test_type="validation",
            test_enable=test_enable,
            firmware_version=firmware_version,
            run_id=session.id,
            api_key=raw_key,
            api_url=api_url,
            # Bench params from scheduler
            mtib_address=bench.mtibAddress,
            bench_id=bench.id,
            device_id=bench.dutDeviceId,
            device_snr=bench.dutSnr,
            fixture_profile_path=bench.profilePath,
        )

        if not job_name:
            logger.error("Failed to create K8s job for pipeline %s", pipeline_id)
            return None

        # Update session with job info
        config = session.config if isinstance(session.config, dict) else {}
        config["trigger"] = {
            "jobName": job_name,
            "firmwareVersion": firmware_version,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }
        config["apiUrl"] = api_url
        config["concordRunId"] = session.id
        # Store bench info for unlock on finish
        config["benchId"] = bench.id
        config["benchStationId"] = bench.stationId
        config["mtibAddress"] = bench.mtibAddress

        db.session.update(
            where={"id": session.id},
            data={"config": Json(config)},
        )

        log_audit("ci.pipeline.validation_trigger", "PipelineRun", pipeline_id, {
            "sessionId": session.id,
            "jobName": job_name,
            "benchId": bench.id,
            "stationId": bench.stationId,
        })

        return session.id

    except Exception as e:
        logger.error("Failed to trigger validation for pipeline %s: %s", pipeline_id, e)
        return None
