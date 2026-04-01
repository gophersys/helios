"""Build promotion — converts BuildRun artifacts into FirmwareSets.

When all BuildJobs in a BuildRun succeed, this service:
1. Groups BuildArtifacts by variant (debug, release, mfg)
2. Creates FirmwareSet records for each group
3. Creates FirmwareBuild records linked to ProductTargets
4. The firmware then appears in the product's Firmware tab
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def promote_build_run_to_firmware(run_id: str) -> Optional[List[Dict[str, Any]]]:
    """Promote a completed BuildRun's artifacts to FirmwareSets.

    Returns list of created FirmwareSet IDs, or None on failure.
    """
    db = get_db_client()

    build_run = db.buildrun.find_unique(
        where={"id": run_id},
        include={
            "builds": {
                "include": {
                    "artifacts": True,
                },
            },
            "product": True,
        },
    )
    if not build_run:
        logger.error("BuildRun %s not found for promotion", run_id)
        return None

    if not build_run.builds:
        logger.warning("BuildRun %s has no builds to promote", run_id)
        return None

    # Find the board revision from the stage config or build matrix
    board_revision_id = None
    if build_run.stageConfigId:
        stage_config = db.productstageconfig.find_unique(
            where={"id": build_run.stageConfigId}
        )
        if stage_config:
            board_revision_id = stage_config.boardRevisionId

    # If no stage config, try to find revision by board name
    if not board_revision_id and build_run.board:
        revision = db.boardrevision.find_first(
            where={"ckBoardsName": build_run.board}
        )
        if revision:
            board_revision_id = revision.id

    # Group builds by variant
    variant_groups: Dict[str, List] = {}
    for build in build_run.builds:
        variant = build.variant or "debug"
        if variant not in variant_groups:
            variant_groups[variant] = []
        variant_groups[variant].append(build)

    # Determine version from builds
    version = "0.0.0"
    for build in build_run.builds:
        if build.versionString:
            # Extract version from "109.0.5.2-BM" → "0.5.2"
            parts = build.versionString.split(".")
            if len(parts) >= 4:
                version = f"{parts[1]}.{parts[2]}.{parts[3].split('-')[0]}"
                break

    # Determine release track from variant
    def variant_to_track(variant: str) -> str:
        return "bench"  # Default for now — would come from signing key

    created_sets = []

    for variant, builds in variant_groups.items():
        is_mfg = variant == "mfg"

        fw_set = db.firmwareset.create(
            data={
                "productId": build_run.productId,
                "boardRevisionId": board_revision_id,
                "version": version,
                "variant": variant,
                "releaseTrack": variant_to_track(variant),
                "isManufacturing": is_mfg,
                "isDebug": variant == "debug",
                "source": "build-service",
                "buildJobId": build_run.id,
            },
        )

        # Create FirmwareBuild records from each build's artifacts
        for build in builds:
            if not build.artifacts:
                continue

            # Find matching ProductTarget by looking at artifact metadata
            target_id = None
            if board_revision_id:
                # Try to match by processor/role in artifacts
                for artifact in build.artifacts:
                    if artifact.processor and artifact.role:
                        target = db.producttarget.find_first(
                            where={
                                "boardRevisionId": board_revision_id,
                                "role": artifact.role,
                            },
                        )
                        if target:
                            target_id = target.id
                            break

            # Group artifacts by type for this build
            hex_key = None
            hex_enc_key = None
            cfw_key = None
            manifest_key = None
            primary_artifact = build.artifacts[0] if build.artifacts else None

            for artifact in build.artifacts:
                atype = artifact.artifactType or ""
                if atype == "plaintextHex" or (not atype and artifact.name.endswith(".hex")):
                    hex_key = artifact.storageKey
                elif atype == "encryptedCfw" or artifact.name.endswith(".cfw"):
                    cfw_key = artifact.storageKey
                elif atype == "encryptedHex":
                    hex_enc_key = artifact.storageKey
                elif atype == "manifest" or artifact.name.endswith(".json"):
                    manifest_key = artifact.storageKey

            if primary_artifact:
                db.firmwarebuild.create(
                    data={
                        "firmwareSetId": fw_set.id,
                        "targetId": target_id,
                        "versionString": build.versionString,
                        "hexStorageKey": hex_key,
                        "hexEncStorageKey": hex_enc_key,
                        "cfwStorageKey": cfw_key,
                        "manifestKey": manifest_key,
                        "filename": primary_artifact.name,
                        "sizeBytes": primary_artifact.sizeBytes,
                        "checksum": primary_artifact.checksum,
                        "contentType": "application/octet-stream",
                    },
                )

        created_sets.append({
            "firmwareSetId": fw_set.id,
            "variant": variant,
            "buildCount": len(builds),
        })
        logger.info("Promoted BuildRun %s variant=%s → FirmwareSet %s",
                     run_id, variant, fw_set.id)

    return created_sets
