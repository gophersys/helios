"""Upload test artifacts (UART logs, power traces) to MinIO."""

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

try:
    from minio import Minio
    _HAS_MINIO = True
except ImportError:
    _HAS_MINIO = False


class ArtifactUploader:
    """Uploads test artifacts to MinIO. Opt-in via STORAGE_URL env var."""

    def __init__(self):
        self.storage_url = os.environ.get("STORAGE_URL", "")
        self.access_key = os.environ.get("STORAGE_ACCESS_KEY", "")
        self.secret_key = os.environ.get("STORAGE_SECRET_ACCESS_KEY", "")
        self.run_id = os.environ.get("CONCORD_RUN_ID", "")
        self.bucket = os.environ.get("STORAGE_BUCKET", "concord")
        self.enabled = bool(self.storage_url and self.run_id and _HAS_MINIO)
        self._client: Optional[Minio] = None

    def _get_client(self) -> "Minio":
        if self._client is None:
            # Strip http:// prefix for Minio client
            endpoint = self.storage_url.replace("http://", "").replace("https://", "")
            self._client = Minio(
                endpoint, access_key=self.access_key,
                secret_key=self.secret_key, secure=False,
            )
        return self._client

    def upload(self, local_path: str, remote_name: str) -> bool:
        """Upload a local file to MinIO under validation/artifacts/{run_id}/."""
        if not self.enabled:
            return False
        try:
            object_name = f"validation/artifacts/{self.run_id}/{remote_name}"
            self._get_client().fput_object(self.bucket, object_name, local_path)
            log.info("Uploaded artifact: %s → %s", local_path, object_name)
            return True
        except Exception as e:
            log.warning("Artifact upload failed for %s: %s", local_path, e)
            return False
