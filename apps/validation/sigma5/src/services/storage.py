from typing import Optional
from urllib.parse import urlparse

from config.env import env_config
from minio import Minio

# Global storage client instance
appStorageClient: Optional[Minio] = None


def init_storage_client() -> Optional[str]:
    """Initialize the global storage client using environment configuration"""
    global appStorageClient

    try:
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

            # Ensure storage bucket exists
            error = _ensure_bucket_exists()
            if error:
                return f"Failed to ensure storage bucket exists: {error}"
    except Exception as e:
        return f"Failed to initialize storage client: {e}"

    return None


def _ensure_bucket_exists() -> Optional[str]:
    """Ensure the storage bucket exists"""
    bucket_name = env_config.STORAGE_BUCKET_NAME

    try:
        if not appStorageClient.bucket_exists(bucket_name):
            return f"Storage bucket does not exist: {bucket_name}"
        return None
    except Exception as e:
        return f"Failed to ensure storage bucket '{bucket_name}' exists: {e}"


def get_storage_client() -> Minio:
    """Get the initialized storage client, initializing if necessary"""
    return appStorageClient


def close_storage_client() -> None:
    """Close the storage client connection"""
    global appStorageClient
    appStorageClient = None
