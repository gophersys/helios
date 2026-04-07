"""Build Job K8s Runner — creates K8s Jobs to execute firmware builds.

Each BuildJob gets its own K8s Job using the product's builder image.
The job clones the firmware repo, runs build.sh, and uploads artifacts
back to Concord via the HTTP API. Fully decoupled — same endpoints
that TeamCity or any external CI would use.
"""

import hashlib
import logging
import os
import re
import secrets as secrets_module
from datetime import datetime, timedelta, timezone
from typing import Optional

import yaml  # type: ignore[import-untyped]

from config import env_config
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def create_build_k8s_job(build_job_id: str) -> Optional[str]:
    """Create a K8s Job for a BuildJob.

    Returns the K8s job name on success, None on failure.
    """
    db = get_db_client()

    job = db.buildjob.find_unique(
        where={"id": build_job_id},
        include={
            "product": True,
        },
    )
    if not job:
        logger.error("BuildJob %s not found", build_job_id)
        return None

    product = job.product
    webhook_data = job.webhookData or {}

    # Extract build config from webhook data
    repo_url = webhook_data.get("repoUrl", "")
    builder_image = webhook_data.get("builderImage", "")
    signing_key_id = webhook_data.get("signingKeyId")
    board_revision_id = webhook_data.get("boardRevisionId")

    if not repo_url:
        logger.error("BuildJob %s has no repoUrl", build_job_id)
        return None

    if not builder_image:
        # Fallback: derive from product
        if product and product.builderImage:
            builder_image = product.builderImage
        elif product and product.fwRepoSlug:
            builder_image = f"containers.ad.corekinect.com/{product.fwRepoSlug}-builder:latest"
        else:
            logger.error("BuildJob %s has no builder image", build_job_id)
            return None

    # Get signing key value if referenced
    signing_key_b64 = ""
    if signing_key_id:
        secret = db.secret.find_unique(where={"id": signing_key_id})
        if secret:
            signing_key_b64 = secret.value

    # Get Bitbucket SSH key for cloning
    bitbucket_ssh_key = env_config.BITBUCKET_SSH_KEY

    # Create a scoped API key for the build job to upload artifacts
    raw_key = f"ck_build_{secrets_module.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Find or create system user for API key
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.create(data={
            "email": "system@concord.local",
            "name": "System",
            "active": True,
        })

    db.apikey.create(
        data={
            "name": f"Build job {build_job_id[:8]}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:12],
            "userId": system_user.id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    api_url = os.environ.get("CONCORD_API_URL",
                              "http://concord-http-api.staging.svc.cluster.local:9001")

    # Sanitize names for K8s
    product_k8s = re.sub(r"[^a-z0-9-]", "-", (product.name or "build").lower()).strip("-")
    label = (job.matrixLabel or "build").lower().replace("_", "-")
    job_name = f"build-{product_k8s}-{label}-{build_job_id[:8]}"
    job_name = re.sub(r"-+", "-", job_name)[:63]  # K8s name limit

    namespace = os.environ.get("BUILD_NAMESPACE", env_config.VALIDATION_NAMESPACE)

    # Build the K8s Job spec
    k8s_job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {
                "app": "concord-build",
                "product": product_k8s[:63],
                "build-job-id": build_job_id[:63],
                "matrix-label": label[:63],
            },
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "metadata": {
                    "labels": {
                        "app": "concord-build",
                        "product": product_k8s[:63],
                    },
                },
                "spec": {
                    "restartPolicy": "Never",
                    "nodeSelector": {
                        "concord.corekinect.com/workload-build": "true",
                    },
                    "containers": [{
                        "name": "builder",
                        "image": builder_image,
                        "command": ["/bin/bash", "-c"],
                        "args": [_build_entrypoint_script()],
                        "env": [
                            {"name": "BUILD_JOB_ID", "value": build_job_id},
                            {"name": "CONCORD_API_URL", "value": api_url},
                            {"name": "CONCORD_API_KEY", "value": raw_key},
                            {"name": "CONCORD_API_HOST", "value": env_config.CONCORD_API_HOST},
                            {"name": "REPO_URL", "value": repo_url},
                            {"name": "REPO_BRANCH", "value": job.branch or "main"},
                            {"name": "BOARD", "value": job.board or ""},
                            {"name": "VARIANT", "value": job.variant or "debug"},
                            {"name": "FIRMWARE_TYPE", "value": job.target or "app"},
                            {"name": "MATRIX_LABEL", "value": job.matrixLabel or ""},
                            {"name": "VERSION_BUMP", "value": "true" if job.versionBump else "false"},
                            {"name": "BUILD_NUM", "value": str(job.buildNum or 0)},
                            {"name": "CONFIG_LOG", "value": "y" if (job.configFlags or {}).get("config_log", True) else "n"},
                            {"name": "BITBUCKET_SSH_KEY", "value": bitbucket_ssh_key},
                            {"name": "SIGNING_KEY", "value": signing_key_b64},
                        ],
                        "resources": {
                            "requests": {"memory": "2Gi", "cpu": "1"},
                            "limits": {"memory": "4Gi", "cpu": "2"},
                        },
                    }],
                },
            },
        },
    }

    try:
        from src.services.kubernetes.client import get_k8s_client
        k8s_client = get_k8s_client()
        if not k8s_client:
            logger.warning("K8s client not available — build job %s created in DB but not scheduled", build_job_id)
            return None

        from kubernetes import client as k8s_api
        batch_v1 = k8s_api.BatchV1Api(k8s_client)
        batch_v1.create_namespaced_job(namespace=namespace, body=k8s_job)

        # Update job status to BUILDING
        db.buildjob.update(
            where={"id": build_job_id},
            data={
                "status": "BUILDING",
                "workerId": job_name,
                "startedAt": datetime.now(timezone.utc),
            },
        )

        logger.info("Created K8s build job: %s (image: %s)", job_name, builder_image)
        return job_name

    except Exception as e:
        logger.error("Failed to create K8s build job %s: %s", build_job_id, e)
        return None


def _build_entrypoint_script() -> str:
    """Generate the bash entrypoint script for the build container.

    This script:
    1. Sets up SSH for git clone
    2. Clones the firmware repo
    3. Sets up signing keys
    4. Runs build.sh
    5. Uploads artifacts to Concord via HTTP API
    6. Reports build status
    """
    return '''
set -eo pipefail

echo "=== Concord Build Job ==="
echo "Job ID: $BUILD_JOB_ID"
echo "Board: $BOARD"
echo "Variant: $VARIANT"
echo "Type: $FIRMWARE_TYPE"
echo "Label: $MATRIX_LABEL"

# Report BUILDING status
curl -s -X PATCH "$CONCORD_API_URL/v2/builds/$BUILD_JOB_ID" \\
  -H "Authorization: ApiKey $CONCORD_API_KEY" \\
  -H "Host: $CONCORD_API_HOST" \\
  -H "Content-Type: application/json" \\
  -d '{"status": "BUILDING"}' || true

# Setup SSH for git clone
mkdir -p /root/.ssh
if [ -n "$BITBUCKET_SSH_KEY" ]; then
  echo "$BITBUCKET_SSH_KEY" | base64 -d > /root/.ssh/id_rsa
  chmod 600 /root/.ssh/id_rsa
  ssh-keyscan -t rsa bitbucket.org >> /root/.ssh/known_hosts 2>/dev/null
fi

# Setup signing key
if [ -n "$SIGNING_KEY" ]; then
  mkdir -p /keys
  echo "$SIGNING_KEY" | base64 -d > /keys/signing_key.pem
  chmod 600 /keys/signing_key.pem
  export SIGNING_KEY_PATH=/keys/signing_key.pem
fi

# Clone repo
REPO_DIR=/workspace/repo
git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR"

# Version bump if needed
if [ "$VERSION_BUMP" = "true" ] && [ -n "$BUILD_NUM" ]; then
  find "$REPO_DIR" -name "VersionDevice.h" -type f | while read f; do
    sed -i "s/^#define BUILD_NUM.*/#define BUILD_NUM         $BUILD_NUM/" "$f"
    echo "Patched BUILD_NUM=$BUILD_NUM in $f"
  done
fi

# Run build script
export REPO_DIR
export OUTPUT_DIR=/workspace/artifacts
export CI_MODE=true
mkdir -p "$OUTPUT_DIR"

cd "$REPO_DIR"
if [ -f scripts/build.sh ]; then
  bash scripts/build.sh "$FIRMWARE_TYPE" --board "$BOARD" --variant "$VARIANT"
elif [ -f build.sh ]; then
  bash build.sh "$FIRMWARE_TYPE" --board "$BOARD" --variant "$VARIANT"
else
  echo "ERROR: No build script found (scripts/build.sh or build.sh)"
  curl -s -X PATCH "$CONCORD_API_URL/v2/builds/$BUILD_JOB_ID" \\
    -H "Authorization: ApiKey $CONCORD_API_KEY" \\
    -H "Host: $CONCORD_API_HOST" \\
    -H "Content-Type: application/json" \\
    -d '{"status": "FAILED", "errorMessage": "No build script found"}' || true
  exit 1
fi

# Upload artifacts
ARTIFACT_COUNT=0
for artifact in "$OUTPUT_DIR"/*; do
  [ -f "$artifact" ] || continue
  FILENAME=$(basename "$artifact")

  # Determine artifact type from extension
  ARTIFACT_TYPE="plaintextHex"
  case "$FILENAME" in
    *.cfw) ARTIFACT_TYPE="encryptedCfw" ;;
    *_encrypted*.hex) ARTIFACT_TYPE="encryptedHex" ;;
    *.json) ARTIFACT_TYPE="manifest" ;;
    *.log) ARTIFACT_TYPE="log" ;;
  esac

  # Determine role from filename
  ROLE=""
  case "$FILENAME" in
    *comms*|*nrf91*) ROLE="comms" ;;
    *app*|*nrf52*|*nrf54*) ROLE="app" ;;
  esac

  # Determine processor from filename
  PROCESSOR=""
  case "$FILENAME" in
    *nrf52840*) PROCESSOR="nrf52840" ;;
    *nrf9151*) PROCESSOR="nrf9151" ;;
    *nrf9160*) PROCESSOR="nrf9160" ;;
    *nrf54l15*) PROCESSOR="nrf54l15" ;;
  esac

  echo "Uploading: $FILENAME (type=$ARTIFACT_TYPE, role=$ROLE, processor=$PROCESSOR)"

  curl -s -X POST "$CONCORD_API_URL/v2/builds/$BUILD_JOB_ID/artifacts" \\
    -H "Authorization: ApiKey $CONCORD_API_KEY" \\
    -H "Host: $CONCORD_API_HOST" \\
    -F "file=@$artifact" \\
    -F "artifactType=$ARTIFACT_TYPE" \\
    -F "role=$ROLE" \\
    -F "processor=$PROCESSOR" || echo "WARN: Failed to upload $FILENAME"

  ARTIFACT_COUNT=$((ARTIFACT_COUNT + 1))
done

echo "Uploaded $ARTIFACT_COUNT artifacts"

# Report SUCCESS
curl -s -X PATCH "$CONCORD_API_URL/v2/builds/$BUILD_JOB_ID" \\
  -H "Authorization: ApiKey $CONCORD_API_KEY" \\
  -H "Host: $CONCORD_API_HOST" \\
  -H "Content-Type: application/json" \\
  -d "{\\"status\\": \\"SUCCESS\\", \\"versionString\\": \\"$(cat $OUTPUT_DIR/version.txt 2>/dev/null || echo unknown)\\"}" || true

echo "=== Build Complete ==="
'''
