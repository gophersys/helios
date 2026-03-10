"""Upload test artifacts (UART logs, power traces) to MinIO."""

from typing import Optional

from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="artifact_uploader")

try:
    from minio import Minio
    _HAS_MINIO = True
except ImportError:
    _HAS_MINIO = False


class _StorageConfig(EnvConfig):
    """MinIO storage config — loaded from env vars."""
    ENV_PREFIX = ""

    STORAGE_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    CONCORD_RUN_ID: Optional[str] = None
    STORAGE_BUCKET: str = "concord"


class ArtifactUploader:
    """Uploads test artifacts to MinIO. Opt-in via STORAGE_URL env var."""

    def __init__(self):
        cfg = _StorageConfig()
        self.storage_url = cfg.STORAGE_URL or ""
        self.access_key = cfg.STORAGE_ACCESS_KEY or ""
        self.secret_key = cfg.STORAGE_SECRET_ACCESS_KEY or ""
        self.run_id = cfg.CONCORD_RUN_ID or ""
        self.bucket = cfg.STORAGE_BUCKET
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
        """Upload a local file to MinIO under validation/runs/{run_id}/."""
        if not self.enabled:
            return False
        try:
            object_name = f"validation/runs/{self.run_id}/{remote_name}"
            self._get_client().fput_object(self.bucket, object_name, local_path)
            log.info("Uploaded artifact: %s -> %s", local_path, object_name)
            return True
        except Exception as e:
            log.warning("Artifact upload failed for %s: %s", local_path, e)
            return False
