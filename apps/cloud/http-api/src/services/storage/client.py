from minio import Minio
from typing import Optional
from urllib.parse import urlparse

from config.env import env_config

# Global storage client instance
appStorageClient: Optional[Minio] = None


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

        # Ensure firmware bucket exists
        _ensure_firmware_bucket_exists()

    return appStorageClient


def _ensure_firmware_bucket_exists() -> None:
    """Ensure the firmware bucket exists, create it if it doesn't"""
    bucket_name = env_config.STORAGE_FIRMWARE_BUCKET_NAME

    try:
        if not appStorageClient.bucket_exists(bucket_name):
            appStorageClient.make_bucket(bucket_name)
            print(f"✓ Created firmware bucket: {bucket_name}")
        else:
            print(f"✓ Firmware bucket already exists: {bucket_name}")
    except Exception as e:
        print(f"⚠ Warning: Could not ensure firmware bucket exists: {e}")
        # Re-raise the exception to prevent silent failures during initialization
        raise RuntimeError(f"Failed to ensure firmware bucket '{bucket_name}' exists: {e}") from e


def get_storage_client() -> Minio:
    """Get the initialized storage client, initializing if necessary"""
    if appStorageClient is None:
        return init_storage_client()
    return appStorageClient


def close_storage_client() -> None:
    """Close the storage client connection"""
    global appStorageClient
    appStorageClient = None


def get_firmware_bucket_name() -> str:
    """Get the configured firmware bucket name"""
    return env_config.STORAGE_FIRMWARE_BUCKET_NAME
