#!/usr/bin/env python3
"""CI Pipeline Orchestrator — End-to-end firmware build → upload → validate.

Simulates the full CI pipeline flow that would normally be handled by the
build service + webhook chain. Designed to run from the devbox.

Usage:
    python3 scripts/ci_pipeline.py \
        --artifacts-dir /path/to/artifacts/alpha_fw/alpha_b0 \
        --product alpha \
        --firmware-type alpha_fw \
        --variant debug \
        --branch concord-main \
        --commit-sha abc123 \
        --minio-endpoint localhost:9000 \
        --api-url http://localhost:9001
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ci-pipeline")


# ─── MinIO Upload ───────────────────────────────────────────────────────

def upload_to_minio(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    artifacts_dir: Path,
    storage_prefix: str,
) -> list[dict]:
    """Upload build artifacts to MinIO and return artifact metadata."""
    from minio import Minio

    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

    # Ensure bucket exists
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info("Created bucket: %s", bucket)

    artifacts = []
    for fpath in sorted(artifacts_dir.iterdir()):
        if not fpath.is_file():
            continue

        storage_key = f"{storage_prefix}/{fpath.name}"
        size = fpath.stat().st_size

        # Compute SHA-256
        sha256 = hashlib.sha256(fpath.read_bytes()).hexdigest()

        # Upload
        client.fput_object(bucket, storage_key, str(fpath))
        log.info("  Uploaded: %s (%d bytes, sha256=%s)", storage_key, size, sha256[:12])

        artifacts.append({
            "name": fpath.name,
            "storageKey": storage_key,
            "sizeBytes": size,
            "checksum": sha256,
        })

    return artifacts


# ─── API Calls (via curl to staging) ────────────────────────────────────

def create_build_job_via_api(api_url: str, api_key: str, build_data: dict) -> dict:
    """Create a BuildJob via the Concord HTTP API."""
    import urllib.request
    import urllib.error

    url = f"{api_url}/v2/builds"
    payload = json.dumps(build_data).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            return body.get("data", body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log.error("API error %d: %s", e.code, body)
        raise


def create_build_job_via_db(build_data: dict, artifacts: list[dict]) -> str:
    """Create a BuildJob directly in the staging database via kubectl exec."""
    # Use kubectl to run a prisma query against the staging DB
    build_id = build_data.get("buildId", "")
    product = build_data["product"]
    board = build_data["board"]
    target = build_data["target"]
    variant = build_data["variant"]
    branch = build_data["branch"]
    commit_sha = build_data.get("commitSha", "")

    # Build the SQL for inserting the build job
    sql = f"""
    INSERT INTO "BuildJob" (
        "id", "product", "board", "target", "variant", "mtibRev",
        "branch", "commitSha", "status", "buildNum",
        "versionString", "createdAt", "updatedAt"
    ) VALUES (
        gen_random_uuid(), '{product}', '{board}', '{target}', '{variant}', '1.2',
        '{branch}', '{commit_sha}', 'SUCCESS', 1,
        '0.8.1-ED', NOW(), NOW()
    ) RETURNING "id";
    """

    result = subprocess.run(
        [
            "kubectl", "exec", "-n", "staging",
            "deploy/concord-postgres", "--",
            "psql", "-U", "concord", "-d", "concord",
            "-t", "-A", "-c", sql,
        ],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        log.error("DB insert failed: %s", result.stderr)
        raise RuntimeError(f"DB insert failed: {result.stderr}")

    build_id = result.stdout.strip()
    log.info("Created BuildJob: %s", build_id)

    # Insert artifacts
    for art in artifacts:
        art_sql = f"""
        INSERT INTO "BuildJobArtifact" (
            "id", "buildJobId", "name", "storageKey",
            "sizeBytes", "checksum", "createdAt"
        ) VALUES (
            gen_random_uuid(), '{build_id}', '{art["name"]}', '{art["storageKey"]}',
            {art["sizeBytes"]}, '{art["checksum"]}', NOW()
        );
        """
        subprocess.run(
            [
                "kubectl", "exec", "-n", "staging",
                "deploy/concord-postgres", "--",
                "psql", "-U", "concord", "-d", "concord",
                "-c", art_sql,
            ],
            capture_output=True, text=True, timeout=30,
        )

    log.info("Inserted %d artifacts for build %s", len(artifacts), build_id)
    return build_id


# ─── Main Pipeline ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CI Pipeline Orchestrator")
    parser.add_argument("--artifacts-dir", required=True, help="Path to build artifacts directory")
    parser.add_argument("--product", default="alpha", help="Product name")
    parser.add_argument("--firmware-type", default="alpha_fw", help="Firmware type")
    parser.add_argument("--variant", default="debug", help="Build variant")
    parser.add_argument("--branch", default="concord-main", help="Git branch")
    parser.add_argument("--commit-sha", default="", help="Git commit SHA")
    parser.add_argument("--board", default="alpha_b0", help="Board name")

    # MinIO config
    parser.add_argument("--minio-endpoint", default="localhost:9000")
    parser.add_argument("--minio-access-key", default="minioadmin")
    parser.add_argument("--minio-secret-key", default="minioadmin-staging")
    parser.add_argument("--minio-bucket", default="firmware-builds")

    # API config
    parser.add_argument("--api-url", default="")
    parser.add_argument("--api-key", default="")

    # Options
    parser.add_argument("--skip-upload", action="store_true", help="Skip MinIO upload")
    parser.add_argument("--skip-db", action="store_true", help="Skip DB record creation")

    args = parser.parse_args()
    artifacts_dir = Path(args.artifacts_dir)

    if not artifacts_dir.exists():
        log.error("Artifacts directory not found: %s", artifacts_dir)
        sys.exit(1)

    artifact_files = [f for f in artifacts_dir.iterdir() if f.is_file()]
    log.info("Found %d artifacts in %s", len(artifact_files), artifacts_dir)
    for f in artifact_files:
        log.info("  %s (%d bytes)", f.name, f.stat().st_size)

    # Step 1: Upload to MinIO
    storage_prefix = f"{args.product}/{args.firmware_type}/{args.variant}/0.8.1"
    artifacts_meta = []

    if not args.skip_upload:
        log.info("=== Step 1: Uploading artifacts to MinIO ===")
        artifacts_meta = upload_to_minio(
            endpoint=args.minio_endpoint,
            access_key=args.minio_access_key,
            secret_key=args.minio_secret_key,
            bucket=args.minio_bucket,
            artifacts_dir=artifacts_dir,
            storage_prefix=storage_prefix,
        )
        log.info("Uploaded %d artifacts to MinIO", len(artifacts_meta))
    else:
        log.info("Skipping MinIO upload")

    # Step 2: Create DB record
    if not args.skip_db:
        log.info("=== Step 2: Creating BuildJob in database ===")
        build_data = {
            "product": args.product,
            "board": args.board,
            "target": "app",
            "variant": args.variant,
            "branch": args.branch,
            "commitSha": args.commit_sha,
        }
        build_id = create_build_job_via_db(build_data, artifacts_meta)
        log.info("BuildJob ID: %s", build_id)
    else:
        log.info("Skipping DB record creation")

    log.info("")
    log.info("=== Pipeline Complete ===")
    log.info("  Product: %s", args.product)
    log.info("  Branch: %s", args.branch)
    log.info("  Variant: %s", args.variant)
    log.info("  Artifacts: %d files in MinIO/%s/%s", len(artifacts_meta), args.minio_bucket, storage_prefix)
    if not args.skip_db:
        log.info("  BuildJob: %s", build_id)
    log.info("  Next: trigger validation run from Concord UI or API")


if __name__ == "__main__":
    main()
