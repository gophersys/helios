from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

from minio import Minio

from config.env import env_config

# Global storage client instance
appStorageClient: Optional[Minio] = None


class StoragePrefixes:
    FIRMWARE_RAW = "firmware/raw"
    FIRMWARE_ENCRYPTED = "firmware/encrypted"
    INVENTORY = "inventory"
    CODEBASES = "codebases"
    TESTING_LOGS = "testing/logs"
    TESTING_REPORTS = "testing/reports"
    TESTING_EXPORTS = "testing/exports"
    DEVICES_CALIBRATION = "devices/calibration"
    DEVICES_CERTIFICATES = "devices/certificates"
    DEVICES_DIAGNOSTICS = "devices/diagnostics"
    FIRMWARE_BUILDS = "firmware/builds"
    VALIDATION_RUNS = "validation/runs"  # Structured: runs/{run_id}/{tests,manifest.json,run.zip}
    CI_BUILD_SCRIPTS = "ci/build-scripts"  # Build scripts per product: ci/build-scripts/{product}/build.sh


def storage_key(prefix: str, relative_path: str) -> str:
    return f"{prefix}/{relative_path}"


def init_storage_client() -> Minio:
    """Initialize the global storage client using environment configuration"""
    global appStorageClient

    if appStorageClient is None:
        # Parse URL to extract host and determine if secure
        parsed_url = urlparse(env_config.STORAGE_URL)
        host = parsed_url.netloc
        secure = parsed_url.scheme == "https"

        appStorageClient = Minio(
            endpoint=host,
            access_key=env_config.STORAGE_ACCESS_KEY,
            secret_key=env_config.STORAGE_SECRET_ACCESS_KEY,
            secure=secure,
        )

        # Ensure bucket exists
        _ensure_bucket_exists()

    return appStorageClient


def _ensure_bucket_exists() -> None:
    """Ensure the single concord bucket exists, create it if it doesn't"""
    bucket_name = env_config.STORAGE_BUCKET_NAME

    try:
        if not appStorageClient.bucket_exists(bucket_name):
            appStorageClient.make_bucket(bucket_name)
            print(f"Created storage bucket: {bucket_name}")
        else:
            print(f"Storage bucket already exists: {bucket_name}")
    except Exception as e:
        print(f"Warning: Could not ensure storage bucket exists: {e}")
        raise RuntimeError(f"Failed to ensure storage bucket '{bucket_name}' exists: {e}") from e


def get_storage_client() -> Minio:
    """Get the initialized storage client, initializing if necessary"""
    if appStorageClient is None:
        return init_storage_client()
    return appStorageClient


def close_storage_client() -> None:
    """Close the storage client connection"""
    global appStorageClient
    appStorageClient = None


def get_bucket_name() -> str:
    """Get the configured bucket name"""
    return env_config.STORAGE_BUCKET_NAME


def presigned_get_url(object_key: str, expires_hours: int = 1, download_filename: str | None = None) -> Optional[str]:
    """Generate a presigned GET URL for an object.

    Args:
        object_key:        The object key in the bucket.
        expires_hours:     URL validity period in hours.
        download_filename: When provided, the response forces a download with
                           Content-Disposition: attachment; filename="...".
    """
    if not object_key:
        return None
    client = get_storage_client()

    extra_query_params = None
    if download_filename:
        extra_query_params = {
            "response-content-disposition": f'attachment; filename="{download_filename}"',
        }

    return client.presigned_get_object(
        get_bucket_name(),
        object_key,
        expires=timedelta(hours=expires_hours),
        extra_query_params=extra_query_params,
    )
