"""Build promotion — converts BuildRun artifacts into FirmwareSets and AssetSets.

When all BuildJobs in a BuildRun succeed, this service:
1. Groups BuildArtifacts by variant (debug, release, mfg)
2. Creates FirmwareSet records for each group
3. Creates FirmwareBuild records linked to ProductTargets
4. Creates a unified AssetSet with Asset records for downstream consumption
5. The firmware then appears in the product's Firmware tab
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.database.prisma import get_db_client
from src.services.storage.client import canonical_asset_filename

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
        """Map a build variant to a release track name."""
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


def create_asset_set_from_build_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Create an AssetSet from a completed BuildRun.

    Groups all BuildJob artifacts into a single AssetSet for downstream
    consumption by validation sessions and manufacturing.

    Returns {"assetSetId": "...", "assetCount": N} on success, None on failure.
    """
    db = get_db_client()

    build_run = db.buildrun.find_unique(
        where={"id": run_id},
        include={
            "builds": {"include": {"artifacts": True}},
            "product": True,
        },
    )
    if not build_run:
        logger.error("BuildRun %s not found for AssetSet creation", run_id)
        return None

    if not build_run.builds:
        logger.warning("BuildRun %s has no builds for AssetSet creation", run_id)
        return None

    # Check if an AssetSet already exists for this run (idempotency)
    existing = db.assetset.find_first(where={"buildRunId": run_id})
    if existing:
        logger.info("AssetSet %s already exists for BuildRun %s", existing.id, run_id)
        return {"assetSetId": existing.id, "assetCount": 0, "deduplicated": True}

    # Resolve board revision
    board_revision_id = None
    if build_run.stageConfigId:
        stage_config = db.productstageconfig.find_unique(
            where={"id": build_run.stageConfigId}
        )
        if stage_config:
            board_revision_id = stage_config.boardRevisionId

    if not board_revision_id and build_run.board:
        revision = db.boardrevision.find_first(
            where={"ckBoardsName": build_run.board}
        )
        if revision:
            board_revision_id = revision.id

    # Extract version from the first build with a version string
    version = "0.0.0"
    for build in build_run.builds:
        if build.versionString:
            parts = build.versionString.split(".")
            if len(parts) >= 4:
                version = f"{parts[1]}.{parts[2]}.{parts[3].split('-')[0]}"
                break

    # Determine primary variant (prefer "debug" or first non-mfg variant)
    variants = set(b.variant or "debug" for b in build_run.builds)
    if "debug" in variants:
        primary_variant = "debug"
    elif "release" in variants:
        primary_variant = "release"
    else:
        primary_variant = next(iter(variants), "debug")

    # Resolve stageType from the build run's stage config
    stage_type = None
    if getattr(build_run, "stageConfigId", None):
        sc = db.productstageconfig.find_unique(where={"id": build_run.stageConfigId})
        if sc:
            stage_type = sc.type

    # Create the AssetSet
    asset_set = db.assetset.create(data={
        "productId": build_run.productId,
        "boardRevisionId": board_revision_id,
        "version": version,
        "variant": primary_variant,
        "stage": getattr(build_run, "stage", None),
        "stageType": stage_type,
        "source": "BUILD_SERVICE",
        "buildRunId": build_run.id,
        "commitSha": build_run.commitSha,
        "branch": build_run.branch,
        "recipeVersionId": getattr(build_run, "recipeVersionId", None),
        "status": "COMPLETE",
    })

    # Build a label→processor lookup and label→matrix entry from the build matrix
    matrix_processor_map: Dict[str, str] = {}
    matrix_entry_map: Dict[str, Any] = {}
    if build_run.stageConfigId:
        matrix_entries = db.stagebuildmatrix.find_many(
            where={"stageConfigId": build_run.stageConfigId},
        )
        for entry in matrix_entries:
            processor = getattr(entry, "processor", None)
            if processor:
                matrix_processor_map[entry.label] = processor
            matrix_entry_map[entry.label] = entry

    # Look up product slug and revision version for canonical filenames
    product_slug = getattr(build_run.product, "slug", None) if build_run.product else None
    rev_version = None
    if board_revision_id:
        board_rev_rec = db.boardrevision.find_unique(where={"id": board_revision_id})
        if board_rev_rec:
            rev_version = board_rev_rec.version

    # Create Asset records from each job's artifacts
    asset_count = 0
    for job in build_run.builds:
        if not job.artifacts:
            continue

        job_label = getattr(job, "matrixLabel", None) or "UNKNOWN"

        for artifact in job.artifacts:
            # Parse appId from filename pattern: {appId}.{version}[-{track}].{ext}
            app_id = None
            if artifact.name:
                parts = artifact.name.split(".")
                if parts[0].isdigit():
                    app_id = int(parts[0])

            # Resolve processor: prefer artifact metadata, then matrix entry
            processor = artifact.processor
            if not processor and job_label in matrix_processor_map:
                processor = matrix_processor_map[job_label]

            # Compute canonical filename from matrix entry metadata
            asset_filename = artifact.name
            matrix_entry = matrix_entry_map.get(job_label)
            if matrix_entry and product_slug and rev_version and artifact.name:
                ext = artifact.name.rsplit(".", 1)[-1].lower() if "." in artifact.name else "hex"
                asset_filename = canonical_asset_filename(
                    product_slug=product_slug,
                    role=getattr(matrix_entry, "fwType", None) or artifact.role or "unknown",
                    processor=processor or "unknown",
                    revision=rev_version,
                    variant=getattr(matrix_entry, "variant", None) or (job.variant or "debug"),
                    ext=ext,
                )

            db.asset.create(data={
                "assetSetId": asset_set.id,
                "label": job_label,
                "role": artifact.role or "unknown",
                "processor": processor,
                "artifactType": artifact.artifactType or "unknown",
                "storageKey": artifact.storageKey,
                "filename": asset_filename,
                "sizeBytes": artifact.sizeBytes,
                "checksum": artifact.checksum or "",
                "contentType": getattr(artifact, "contentType", None),
                "appId": app_id,
                "versionString": getattr(job, "versionString", None),
            })
            asset_count += 1

    # Auto-link modem firmware
    # Check board revision for inline modem firmware first
    if board_revision_id:
        board_rev = db.boardrevision.find_unique(where={"id": board_revision_id})
        if board_rev and getattr(board_rev, "modemStorageKey", None) and getattr(board_rev, "modemVersion", None):
            db.asset.create(data={
                "assetSetId": asset_set.id,
                "label": "modem_fw",
                "role": "modem",
                "processor": "nrf9151",
                "artifactType": "modemFirmware",
                "storageKey": board_rev.modemStorageKey,
                "filename": f"modem_{board_rev.modemVersion}.zip",
                "sizeBytes": 0,
                "checksum": "",
                "versionString": board_rev.modemVersion,
            })
            asset_count += 1
            logger.info("Included modem firmware v%s in AssetSet %s",
                        board_rev.modemVersion, asset_set.id)

        # Auto-link ModemFirmware record if available
        modem_fw = db.modemfirmware.find_first(
            where={"boardRevisionId": board_revision_id},
            order={"createdAt": "desc"},
        ) if hasattr(db, "modemfirmware") else None
        if modem_fw:
            try:
                db.assetset.update(
                    where={"id": asset_set.id},
                    data={"modemFirmwareId": modem_fw.id},
                )
                logger.info("Auto-linked ModemFirmware %s to AssetSet %s",
                            modem_fw.id, asset_set.id)
            except Exception:
                logger.debug("modemFirmwareId field not available on AssetSet, skipping auto-link")

    logger.info("Created AssetSet %s from BuildRun %s (%d assets)",
                asset_set.id, run_id, asset_count)

    return {"assetSetId": asset_set.id, "assetCount": asset_count}
