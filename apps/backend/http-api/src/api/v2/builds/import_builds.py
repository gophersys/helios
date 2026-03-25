"""Build import and cache endpoints — register external artifacts, check fingerprints."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BuildImportRequest

logger = logging.getLogger(__name__)


def _serialize_import_result(pipeline, builds) -> Dict[str, Any]:
    """Serialize the import result for API response."""
    return {
        "pipelineId": pipeline.id,
        "status": pipeline.status,
        "builds": [
            {
                "id": b.id,
                "product": b.product,
                "variant": b.variant,
                "status": b.status,
                "reusedFromId": getattr(b, "reusedFromId", None),
            }
            for b in builds
        ],
    }


@require_permissions(Permissions.BUILDS_TRIGGER)
def import_builds():
    """POST /v2/builds/import — Register externally-built firmware artifacts.

    Creates a PipelineRun(triggerType='external', status=SUCCESS) and associated
    BuildJob records. For each build entry:
      - If reuseFromPipeline is specified, creates a CACHED BuildJob with reusedFromId
      - Otherwise creates a SUCCESS BuildJob
    """
    data, error = BuildImportRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Validate product exists
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return not_found(f"Product not found: {data.product_id}")

    try:
        now = datetime.now(timezone.utc)

        # Create PipelineRun with triggerType="external"
        pipeline = db.pipelinerun.create(
            data={
                "name": f"import-{product.slug or product.name}-{data.branch[:12]}",
                "productId": data.product_id,
                "board": data.board,
                "branch": data.branch,
                "commitSha": data.commit_sha,
                "status": "SUCCESS",
                "triggerType": "external",
                "expectedBuilds": len(data.builds) if data.builds else 0,
                "completedBuilds": len(data.builds) if data.builds else 0,
                "triggerData": Json({"source": data.source}),
                "startedAt": now,
                "finishedAt": now,
            },
        )

        builds = []
        for build_entry in (data.builds or []):
            build_product = build_entry.get("product", "").strip()
            build_variant = build_entry.get("variant", "release").strip()
            build_target = build_entry.get("target", "nrf52840").strip()
            version_string = build_entry.get("versionString")
            reuse_from = build_entry.get("reuseFromPipeline")

            build_data = {
                "productId": data.product_id,
                "product": build_product,
                "board": data.board,
                "target": build_target,
                "variant": build_variant,
                "branch": data.branch,
                "commitSha": data.commit_sha,
                "pipelineRunId": pipeline.id,
                "versionString": version_string,
                "startedAt": now,
                "finishedAt": now,
            }

            if reuse_from:
                # Look up the source build to reuse
                source_build = db.buildjob.find_first(
                    where={
                        "pipelineRunId": reuse_from,
                        "product": build_product,
                        "variant": build_variant,
                        "status": "SUCCESS",
                    },
                )
                if source_build:
                    build_data["status"] = "CACHED"
                    build_data["reusedFromId"] = source_build.id
                    build_data["buildFingerprint"] = getattr(source_build, "buildFingerprint", None)
                else:
                    build_data["status"] = "SUCCESS"
            else:
                build_data["status"] = "SUCCESS"

            build = db.buildjob.create(data=build_data)
            builds.append(build)

        log_audit("builds.import", "PipelineRun", pipeline.id, {
            "productId": data.product_id,
            "board": data.board,
            "branch": data.branch,
            "source": data.source,
            "buildCount": len(builds),
        })

        return jsonify(ApiResponse.created(
            _serialize_import_result(pipeline, builds)
        ).to_dict()), 201

    except Exception as e:
        logger.error("Failed to import builds: %s", e)
        return internal_error("Failed to import builds")


@require_permissions(Permissions.BUILDS_VIEW)
def check_build_cache():
    """GET /v2/builds/cache?fingerprint=X&productId=Y — Check if a cached build exists."""
    fingerprint = request.args.get("fingerprint", "").strip()
    if not fingerprint:
        return bad_request("fingerprint query parameter is required")

    product_id = request.args.get("productId", "").strip()

    db = get_db_client()

    try:
        where: Dict[str, Any] = {
            "buildFingerprint": fingerprint,
            "status": "SUCCESS",
        }
        if product_id:
            where["productId"] = product_id

        build = db.buildjob.find_first(
            where=where,
            order={"createdAt": "desc"},
            include={"artifacts": True},
        )

        if not build:
            return not_found("No cached build found for this fingerprint")

        result = {
            "id": build.id,
            "product": build.product,
            "board": build.board,
            "variant": build.variant,
            "branch": build.branch,
            "commitSha": build.commitSha,
            "status": build.status,
            "versionString": build.versionString,
            "buildFingerprint": build.buildFingerprint,
            "pipelineRunId": build.pipelineRunId,
            "createdAt": build.createdAt.isoformat(),
        }

        if hasattr(build, "artifacts") and build.artifacts:
            result["artifacts"] = [
                {
                    "id": a.id,
                    "name": a.name,
                    "storageKey": a.storageKey,
                    "sizeBytes": str(a.sizeBytes),
                }
                for a in build.artifacts
            ]

        return jsonify(ApiResponse.ok(result).to_dict()), 200

    except Exception as e:
        logger.error("Failed to check build cache: %s", e)
        return internal_error("Failed to check build cache")
