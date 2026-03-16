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

from .build_cache import compute_build_fingerprint, find_cached_build
from .types import PipelineCreateRequest
from .stage_builds import (
    ValidationStage,
    StageBuildDef,
    get_stage_build_defs,
)

logger = logging.getLogger(__name__)


def _safe_product_str(obj) -> str | None:
    """Safely extract product slug string from a model field that could be a string or relation."""
    if isinstance(obj, str):
        return obj
    if obj and hasattr(obj, "repoSlug"):
        return obj.repoSlug or obj.slug or obj.name
    return None


def _generate_build_specs(
    stage: ValidationStage,
    product_base: str,
    board: str,
    branch: str,
    commit_sha: Optional[str],
    mtib_rev: str = "1.2",
) -> List[Dict[str, Any]]:
    """Generate build job specs from stage definitions.

    Converts StageBuildDef entries to the dict format expected by BuildJob creation.
    This is the single source of truth - all build requirements come from stage_builds.py.
    """
    defs = get_stage_build_defs(stage)
    builds = []

    for idx, d in enumerate(defs):
        # Determine firmware type from fw_type field
        if d.fw_type == "mfg":
            fw_product = f"{product_base}_mfg_fw"
        elif d.fw_type == "driver_test":
            fw_product = f"{product_base}_fw"  # Driver tests use same repo
        else:  # "app"
            fw_product = f"{product_base}_fw"

        # Resolve git ref based on git_ref field
        if d.git_ref == "main":
            # Use pipeline branch as baseline — "main" means the pipeline's
            # reference branch (e.g. concord-main), not literal git main.
            # Firmware repos may have validation-specific branches that differ
            # from upstream main (VAL server config, board fixes, etc.).
            git_branch = branch
            git_commit = None  # Use HEAD of the branch
        elif d.git_ref == "merge":
            # TODO: Support actual merge commits (git merge base into PR)
            # For now, same as "main" — builds from pipeline branch HEAD
            git_branch = branch
            git_commit = None
        else:  # "pr"
            git_branch = branch
            git_commit = commit_sha

        # Version bump builds start BLOCKED until base completes
        initial_status = "BLOCKED" if d.is_version_bump else "QUEUED"

        builds.append({
            "product": fw_product,
            "board": board,
            "target": "nrf52840",
            "variant": d.variant,
            "mtibRev": mtib_rev,
            "branch": git_branch,
            "commitSha": git_commit,
            "status": initial_status,
            "matrixLabel": d.label,
            "matrixIndex": idx,
            "versionBump": d.is_version_bump,
            "baseLabel": d.base_label,
        })

    return builds


def _auto_increment_version(db, product_id: str, variant: str, target: str = "app") -> Optional[str]:
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


def _generate_matrix_build_specs(
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

        # Each role produces both debug and release variants
        for variant in ("debug", "release"):
            label = f"{role.upper()}_{variant.upper()}"

            if source == "head":
                # New build from triggering commit — auto-version based on target type
                version_override = _auto_increment_version(db, product_id, variant, target) if product_id else None

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
            else:
                # "latest" — will be resolved to CACHED in pipeline creation
                builds.append({
                    "board": board,
                    "target": target,
                    "variant": variant,
                    "mtibRev": "1.2",
                    "branch": branch,
                    "commitSha": None,  # Will be filled from cached build
                    "status": "QUEUED",
                    "matrixLabel": label,
                    "matrixIndex": idx,
                    "versionBump": False,
                    "source": "latest",
                    "firmware": firmware,
                })
            idx += 1

    return builds


def _serialize_pipeline(p) -> Dict[str, Any]:
    """Serialize a PipelineRun for API response."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": _safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
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
                "product": _safe_product_str(getattr(b, "product", None)) or getattr(b, "productId", None),
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
        "product": _safe_product_str(getattr(p, "product", None)) or getattr(p, "productId", None),
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

    # Include builds summary for Stage 4 matrix display
    if hasattr(p, "builds") and p.builds:
        data["builds"] = [
            {
                "id": b.id,
                "product": _safe_product_str(getattr(b, "product", None)) or getattr(b, "productId", None),
                "status": b.status,
                "variant": b.variant,
                "versionString": b.versionString,
                "durationSeconds": b.durationSeconds,
                "matrixLabel": getattr(b, "matrixLabel", None),
                "matrixIndex": getattr(b, "matrixIndex", None),
                "versionBump": getattr(b, "versionBump", False),
            }
            for b in sorted(p.builds, key=lambda x: getattr(x, "matrixIndex", 0) or 0)
        ]

    return data


@require_permissions(Permissions.BUILDS_VIEW)
def list_pipelines():
    """GET /v2/builds/pipelines — List pipeline runs."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    # Filters
    product = request.args.get("product")
    branch = request.args.get("branch")
    status = request.args.get("status")
    matrix_mode = request.args.get("matrixMode")

    where: Dict[str, Any] = {}
    if product:
        where["product"] = product
    if branch:
        where["branch"] = branch
    if status:
        where["status"] = status
    if matrix_mode:
        where["matrixMode"] = matrix_mode

    try:
        total = db.pipelinerun.count(where=where)
        pipelines = db.pipelinerun.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"builds": {"include": {"product": True}}, "product": True},  # Include builds for Stage 4 matrix display
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


@require_permissions(Permissions.BUILDS_VIEW)
def get_pipeline(pipeline_id: str):
    """GET /v2/builds/pipelines/<id> — Get pipeline details with builds."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
        )
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        return jsonify(ApiResponse.ok(_serialize_pipeline(pipeline)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to get pipeline")


@require_permissions(Permissions.BUILDS_VIEW)
def download_pipeline_artifacts(pipeline_id: str):
    """GET /v2/builds/pipelines/<id>/artifacts/download — Download all artifacts as ZIP.

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
        include={"builds": {"include": {"artifacts": True, "product": True}}, "product": True},
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


@require_permissions(Permissions.BUILDS_TRIGGER)
def create_pipeline():
    """POST /v2/builds/pipelines — Create a new pipeline (triggers builds).

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
    # Prefer Product model fields when available
    if product_record:
        repo_slug = data.repo_slug or product_record.repoSlug or data.product
        # Derive repo_base from Product slug or name
        product_base = product_record.slug or product_record.name.lower().replace(" ", "_")
        # Strip board suffixes for base name (alpha_b0 -> alpha)
        repo_base = product_base
        for suffix in ["_b0", "_a0", "_b1", "_a1"]:
            repo_base = repo_base.replace(suffix, "")
        repo_base = repo_base.strip("_")
    else:
        repo_slug = data.repo_slug or data.product
        # Normalize: remove _fw/_mfg suffixes, spaces, board suffixes (b0/a0)
        repo_base = repo_slug.lower().replace(" ", "_").replace("_fw", "").replace("_mfg", "")
        for suffix in ["_b0", "_a0", "_b1", "_a1"]:
            repo_base = repo_base.replace(suffix, "")
        repo_base = repo_base.strip("_")
        product_base = repo_base

    # Determine which firmware builds are needed based on matrix mode
    # Use Product model fields when available
    if product_record and product_record.repoSlug:
        main_fw = product_record.repoSlug  # e.g. "alpha_fw"
    else:
        main_fw = f"{repo_base}_fw"

    if data.mfg_repo_slug:
        mfg_fw = data.mfg_repo_slug
    elif product_record and product_record.mfgRepoSlug:
        mfg_fw = product_record.mfgRepoSlug  # e.g. "alpha_mfg_fw"
    else:
        mfg_fw = f"{repo_base}_mfg_fw"

    # Map matrix mode to validation stage (all 5 stages supported)
    stage_map = {
        "smoke": ValidationStage.SMOKE,
        "silicon": ValidationStage.SILICON,
        "integration": ValidationStage.INTEGRATION,
        "nightly": ValidationStage.NIGHTLY,
        "fuota": ValidationStage.FUOTA,
    }
    # Use explicit stage parameter if provided, otherwise derive from matrixMode
    stage_number = data.validation_config.get("stage") if data.validation_config else None
    stage = stage_map.get(data.matrix_mode, ValidationStage.FUOTA)

    # Look up ProductStageConfig for the product to read buildMatrix
    stage_config = None
    stage_config_matrix = None
    if product_record:
        stage_num = stage_number or {"smoke": 1, "silicon": 2, "integration": 3, "nightly": 4, "fuota": 5}.get(data.matrix_mode, 5)
        stage_config = db.productstageconfig.find_first(
            where={"productId": product_record.id, "stage": stage_num},
        )
        if stage_config and stage_config.buildMatrix:
            stage_config_matrix = stage_config.buildMatrix if isinstance(stage_config.buildMatrix, list) else None

    # If stage config has a buildMatrix, use it for FUOTA-style matrix builds
    # Otherwise fall back to the stage_builds.py definitions
    if stage_config_matrix:
        build_specs = _generate_matrix_build_specs(
            matrix=stage_config_matrix,
            product_record=product_record,
            repo_base=repo_base,
            board=data.board,
            branch=data.pr_branch or data.branch,
            commit_sha=data.commit_sha,
            db=db,
        )
    else:
        build_specs = _generate_build_specs(
            stage=stage,
            product_base=repo_base,
            board=data.board,
            branch=data.pr_branch or data.branch,
            commit_sha=data.commit_sha,
            mtib_rev="1.2",
        )

    expected_builds = len(build_specs)

    # Use autoValidate from stage config if available
    auto_validate = data.auto_validate
    if stage_config and hasattr(stage_config, "blocksMerge"):
        # Stage configs with requiresFuota typically auto-validate
        pass  # Keep the user-provided value unless overridden

    try:
        # Create pipeline run
        trigger_data = {
            "source": data.trigger_type,
            "repoSlug": data.repo_slug,
            "mfgRepoSlug": data.mfg_repo_slug,
        }
        if data.validation_config:
            trigger_data.update(data.validation_config)

        # Store matrix config in pipeline (include Product model fields for traceability)
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

        # Build create data - conditionally include buildMatrix only when provided
        create_data = {
            "name": data.name or f"{product_base}-{data.branch[:8]}" + (f"-{data.commit_sha[:7]}" if data.commit_sha else ""),
            "board": data.board,
            "branch": data.branch,
            "commitSha": data.commit_sha,
            "status": "PENDING",
            "triggerType": data.trigger_type,
            "expectedBuilds": expected_builds,
            "matrixMode": data.matrix_mode,
            "autoValidate": auto_validate,
            "triggerData": Json(trigger_data),
            "startedAt": datetime.now(timezone.utc),
        }
        if product_record:
            create_data["productId"] = product_record.id
        if stage_config:
            create_data["stageConfigId"] = stage_config.id
            create_data["stage"] = stage_config.stage
        # Always include buildMatrix (fuota/nightly modes always have config)
        create_data["buildMatrix"] = Json(matrix_config)

        pipeline = db.pipelinerun.create(data=create_data)

        # Create build jobs based on mode
        # Create build jobs from matrix specs
        builds = []
        label_to_id = {}  # Track created jobs for baseJobId linking
        specs_with_builds = []  # Track specs with their created builds

        for spec in build_specs:
            # Check build cache for non-version-bump builds
            cached_build = None
            fingerprint = None
            if not spec.get("versionBump", False) and spec.get("commitSha"):
                repo_url = product_record.repoSshUrl if product_record else ""
                fingerprint = compute_build_fingerprint(
                    repo_url=repo_url,
                    commit_sha=spec.get("commitSha") or "",
                    board=spec["board"],
                    variant=spec["variant"],
                    config_flags=None,
                )
                if spec.get("source") == "latest":
                    # For "latest" source, find the most recent successful build
                    cached_build = db.buildjob.find_first(
                        where={
                            "productId": product_record.id if product_record else None,
                            "variant": spec["variant"],
                            "target": spec.get("target", "app"),
                            "status": "SUCCESS",
                        },
                        include={"artifacts": True, "product": True},
                        order={"finishedAt": "desc"},
                    )

            if cached_build and spec.get("source") == "latest":
                # Create a CACHED reference build
                build_data = {
                    "productId": product_record.id if product_record else None,
                    "board": spec["board"],
                    "target": spec["target"],
                    "variant": spec["variant"],
                    "mtibRev": spec["mtibRev"],
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
                if fingerprint:
                    build_data["buildFingerprint"] = fingerprint
                # Auto-version for "head" source builds — put in configFlags
                # so the build worker picks it up as VERSION_BUILD_OVERRIDE
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
            include={"builds": {"include": {"product": True}}, "product": True},
        )

        return jsonify(ApiResponse.created(_serialize_pipeline(pipeline)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create pipeline: %s", e)
        return internal_error("Failed to create pipeline")


@require_permissions(Permissions.BUILDS_MANAGE)
def cancel_pipeline(pipeline_id: str):
    """POST /v2/builds/pipelines/<id>/cancel — Cancel a pipeline."""
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
                "status": {"in": ["QUEUED", "CLONING", "BUILDING"]},
            },
            data={"status": "CANCELLED"},
        )

        # Update pipeline
        pipeline = db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": "CANCELLED", "finishedAt": datetime.now(timezone.utc)},
            include={"builds": {"include": {"product": True}}, "product": True},
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
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not pipeline:
            return None

        if pipeline.status not in ("PENDING", "CLONING", "BUILDING"):
            return None  # Already in terminal state

        builds = pipeline.builds or []
        if not builds:
            return None

        # Count build statuses (CACHED counts as completed/succeeded)
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

        # All builds succeeded
        if getattr(pipeline, "autoValidate", False):
            # Auto-trigger validation
            new_status = "VALIDATING"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={"status": new_status},
            )
            logger.info("Pipeline %s builds complete, auto-triggering validation", pipeline_id)

            validation_run_id = trigger_pipeline_validation(pipeline_id, pipeline, builds)
            if validation_run_id:
                db.pipelinerun.update(
                    where={"id": pipeline_id},
                    data={"validationRunId": validation_run_id},
                )
                logger.info("Pipeline %s validation triggered: %s", pipeline_id, validation_run_id)
            else:
                # Validation trigger failed (no bench, etc.) — mark SUCCESS, user can trigger manually
                new_status = "SUCCESS"
                db.pipelinerun.update(
                    where={"id": pipeline_id},
                    data={"status": new_status, "finishedAt": datetime.now(timezone.utc)},
                )
                logger.warning("Pipeline %s auto-validate failed (no bench?), set to SUCCESS", pipeline_id)
        else:
            # No auto-validate — builds are done
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


def trigger_pipeline_validation(pipeline_id: str, pipeline, builds: list) -> Optional[str]:
    """
    Trigger a validation job for a completed pipeline.
    Creates a validation session and K8s job with the build artifacts.
    Uses the Fixture model (not legacy TestBench).
    Returns the validation run ID if successful.
    """
    import hashlib
    import os
    import secrets
    from datetime import timedelta

    from src.api.v2.sessions.manual import create_kubernetes_job

    db = get_db_client()

    try:
        # Look up the product
        product = db.product.find_unique(where={"id": pipeline.productId}) if pipeline.productId else None
        if not product:
            product = db.product.find_first(
                where={"name": {"contains": pipeline.product, "mode": "insensitive"}} if hasattr(pipeline, "product") and pipeline.product else {},
            )
        if not product:
            logger.warning("Product not found for pipeline %s", pipeline_id)
            return None

        # Find an available fixture for this product
        fixture = db.fixture.find_first(
            where={
                "productId": product.id,
                "status": "AVAILABLE",
                "active": True,
            },
            include={
                "slots": True,
                "design": True,
            },
        )
        if not fixture:
            logger.warning("No available fixture for product %s", product.name)
            return None

        # Get the first active slot with DUT identity
        slot = None
        for s in (fixture.slots or []):
            if s.active and s.dutSnr:
                slot = s
                break

        if not slot:
            logger.warning("Fixture %s has no active slot with DUT identity", fixture.name)
            return None

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

        # Get MTIB address from the node linked to the slot
        mtib_address = None
        if slot.nodeId:
            node = db.node.find_unique(where={"id": slot.nodeId})
            if node:
                mtib_address = node.address
        if not mtib_address:
            # Fallback: check fixture metadata
            meta = fixture.metadata if isinstance(fixture.metadata, dict) else {}
            mtib_address = meta.get("mtibAddress", "")

        # Create a validation session
        build_summaries = []
        for b in builds:
            slug = _derive_build_product_slug(b)
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
                "createdById": _get_system_user_id(db),
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
                "userId": _get_system_user_id(db),
                "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
            },
        )

        # Get API URL for reporter
        api_url = os.environ.get("CONCORD_API_URL", "https://10.4.45.11:443")

        # Get firmware version from the FUOTA target build (release variant)
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

        # Determine fixture profile path
        fixture_profile_path = ""
        if fixture.design and hasattr(fixture.design, "profileTemplate"):
            fixture_profile_path = f"fixtures/{product.slug}.json"

        # Create K8s Job
        test_enable = {"electrical": False, "app_post": False, "comm_post": False}

        job_name = create_kubernetes_job(
            product=product.name,
            job_id=session.id,
            firmware_path="",  # Validation runner fetches from MinIO by build ID
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
            fixture_profile_path=fixture_profile_path,
            stage="fuota",
        )

        if not job_name:
            logger.error("Failed to create K8s job for pipeline %s", pipeline_id)
            # Unlock fixture
            db.fixture.update(where={"id": fixture.id}, data={"status": "AVAILABLE", "lockedBy": None, "lockedAt": None})
            return None

        # Update session with job info
        config = session.config if isinstance(session.config, dict) else {}
        config["trigger"] = {
            "jobName": job_name,
            "firmwareVersion": firmware_version,
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
        return session.id

    except Exception as e:
        logger.error("Failed to trigger validation for pipeline %s: %s", pipeline_id, e)
        return None


def _derive_build_product_slug(b) -> str:
    """Get product slug from build for session metadata."""
    product = getattr(b, "product", None)
    if isinstance(product, str):
        return product
    if product and hasattr(product, "repoSlug"):
        if getattr(b, "target", "") == "mfg" and getattr(product, "mfgRepoSlug", None):
            return product.mfgRepoSlug
        return product.repoSlug or product.slug
    return getattr(b, "productId", "unknown")


def _get_system_user_id(db) -> str:
    """Get or create system user for automated actions."""
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.create(data={"name": "System", "email": "system@concord.local"})
    return system_user.id


@require_permissions(Permissions.BUILDS_VIEW)
def list_pipeline_sessions(pipeline_id: str):
    """GET /v2/builds/pipelines/<id>/sessions — List sessions triggered by this pipeline."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    try:
        # Verify pipeline exists
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        where = {"pipelineRunId": pipeline_id}
        total = db.session.count(where=where)
        sessions = db.session.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"product": True},
        )

        pages = (total + limit - 1) // limit if limit > 0 else 0

        data = []
        for s in sessions:
            entry = {
                "id": s.id,
                "name": s.name,
                "type": s.type if hasattr(s, "type") else "VALIDATION",
                "productId": s.productId,
                "status": s.status,
                "targetCount": s.targetCount,
                "completedCount": s.completedCount,
                "passedCount": s.passedCount,
                "failedCount": s.failedCount,
                "startedAt": s.startedAt.isoformat() if s.startedAt else None,
                "finishedAt": s.finishedAt.isoformat() if s.finishedAt else None,
                "createdAt": s.createdAt.isoformat(),
            }
            if hasattr(s, "product") and s.product is not None:
                entry["product"] = {"id": s.product.id, "name": s.product.name}
            data.append(entry)

        return jsonify(ApiResponse.paginated(
            data=data,
            page=page,
            total_pages=pages,
            total_results=total,
            results_per_page=limit,
        ).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list pipeline sessions %s: %s", pipeline_id, e)
        return internal_error("Failed to list pipeline sessions")


@require_permissions(Permissions.BUILDS_MANAGE)
def validate_pipeline(pipeline_id: str):
    """POST /v2/builds/pipelines/<id>/validate — Manually trigger validation for a completed pipeline."""
    db = get_db_client()

    try:
        pipeline = db.pipelinerun.find_unique(
            where={"id": pipeline_id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_id}")

        # Allow from SUCCESS (never auto-validated) or FAILED (re-trigger after fix)
        if pipeline.status not in ("SUCCESS", "FAILED", "BUILD_FAILED"):
            if pipeline.status == "VALIDATING":
                return bad_request("Pipeline is already validating")
            return bad_request(f"Cannot trigger validation for pipeline in {pipeline.status} state")

        builds = pipeline.builds or []
        succeeded = [b for b in builds if b.status == "SUCCESS"]
        if not succeeded:
            return bad_request("No successful builds — cannot trigger validation")

        # Trigger validation
        validation_run_id = trigger_pipeline_validation(pipeline_id, pipeline, builds)
        if not validation_run_id:
            return internal_error("Failed to create validation run (no bench available?)")

        db.pipelinerun.update(
            where={"id": pipeline_id},
            data={"status": "VALIDATING", "validationRunId": validation_run_id},
        )

        log_audit("ci.pipeline.validate_manual", "PipelineRun", pipeline_id, {
            "validationRunId": validation_run_id,
        })

        return jsonify(ApiResponse.ok({
            "pipelineId": pipeline_id,
            "validationRunId": validation_run_id,
            "status": "VALIDATING",
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to trigger validation for pipeline %s: %s", pipeline_id, e)
        return internal_error("Failed to trigger validation")
