import re
from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

from minio import Minio

from config.env import env_config


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for Content-Disposition headers and storage paths.

    Strips anything outside ASCII alphanumerics, dots, hyphens, and underscores.
    This is the single canonical sanitizer — import from here everywhere.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return sanitized if sanitized else "download"

# Global storage client instance
appStorageClient: Optional[Minio] = None


class StoragePrefixes:
    """MinIO object key prefixes for each storage domain."""

    PRODUCTS = "products"                   # Product-scoped assets and modem firmware
    FIRMWARE_BUILDS = "firmware/builds"     # CI build artifacts: {product}/{build_id}/{filename}
    FIRMWARE_UPLOADS = "firmware/uploads"   # Manual firmware uploads: {product}/{filename}
    BUILD_SCRIPTS = "builds/scripts"       # Build automation: {product}/build.sh
    SESSIONS = "sessions"                  # Test session data
    ICLE_LOGS = "icle"                     # ICLE power logs


def storage_key(prefix: str, relative_path: str) -> str:
    """Build a full MinIO object key from a prefix and relative path."""
    return f"{prefix}/{relative_path}"


STAGE_NAMES = {
    "VALIDATION": {1: "smoke", 2: "driver", 3: "integration", 4: "regression", 5: "fuota"},
    "MANUFACTURING": {1: "manufacturing"},
}


def _resolve_stage_name(stage_type: str | None, stage: int | None, stage_name: str | None) -> str:
    """Resolve a human-readable stage name for storage paths."""
    if stage_name:
        return sanitize_filename(stage_name.lower())
    if stage_type and stage is not None:
        return STAGE_NAMES.get(stage_type, {}).get(stage, str(stage))
    return "general"


def product_asset_key(
    product_slug: str | None,
    revision_version: str | None,
    stage_type: str | None,
    stage: int | None,
    asset_version: str,
    variant: str,
    label: str,
    filename: str,
    stage_name: str | None = None,
) -> str:
    """Build a product-scoped MinIO key for an asset file.

    Path: products/{slug}/{revision}/{stage_type}/{stage_name}/{version}-{variant}/{label}/{filename}
    Example: products/alpha/b0/validation/smoke/1.2.0-debug/mfg_app_debug/app_nrf52840.hex
    """
    slug = sanitize_filename(product_slug) if product_slug else "unknown"
    rev = sanitize_filename(revision_version) if revision_version else "unscoped"
    st = (stage_type or "general").lower()
    sn = _resolve_stage_name(stage_type, stage, stage_name)
    ver = sanitize_filename(asset_version or "0.0.0")
    var = sanitize_filename(variant or "default")
    lbl = sanitize_filename(label)
    fn = sanitize_filename(filename)

    return f"{StoragePrefixes.PRODUCTS}/{slug}/{rev}/{st}/{sn}/{ver}-{var}/{lbl}/{fn}"


def canonical_asset_filename(
    product_slug: str,
    role: str,
    processor: str,
    revision: str,
    variant: str,
    ext: str,
) -> str:
    """Generate canonical asset filename: alpha_app_nrf52840_b0_debug.hex"""
    parts = [
        sanitize_filename(product_slug or "unknown"),
        sanitize_filename(role or "unknown"),
        sanitize_filename(processor or "unknown"),
        sanitize_filename(revision.lower() if revision else "unknown"),
        sanitize_filename(variant or "unknown"),
    ]
    return "_".join(parts) + f".{ext}"


def modem_firmware_key(
    product_slug: str | None,
    revision_version: str | None,
    modem_version: str,
    filename: str,
) -> str:
    """Build a product-scoped MinIO key for modem firmware.

    Path: products/{slug}/{revision}/modem/{version}/{filename}
    """
    slug = sanitize_filename(product_slug) if product_slug else "unknown"
    rev = sanitize_filename(revision_version) if revision_version else "unscoped"
    ver = sanitize_filename(modem_version)
    fn = sanitize_filename(filename)

    return f"{StoragePrefixes.PRODUCTS}/{slug}/{rev}/modem/{ver}/{fn}"


def asset_set_zip_filename(
    product_slug: str | None,
    revision_version: str | None,
    stage_type: str | None,
    stage: int | None,
    asset_version: str,
    variant: str,
    stage_name: str | None = None,
) -> str:
    """Build a descriptive zip filename for asset set download.

    Example: alpha-b0-validation-smoke-v1.2.0-debug.zip
    """
    slug = sanitize_filename(product_slug) if product_slug else "unknown"
    rev = sanitize_filename(revision_version) if revision_version else "unscoped"
    st = (stage_type or "general").lower()
    sn = _resolve_stage_name(stage_type, stage, stage_name)
    ver = sanitize_filename(asset_version or "0.0.0")
    var = sanitize_filename(variant or "default")

    return f"{slug}-{rev}-{st}-{sn}-v{ver}-{var}.zip"


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
        assert appStorageClient is not None
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
    """Close the storage client connection and release pooled HTTP connections."""
    global appStorageClient
    if appStorageClient is not None:
        # Clear the urllib3 PoolManager to close all pooled connections
        try:
            appStorageClient._http.clear()
        except Exception:
            pass
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
        safe_filename = sanitize_filename(download_filename)
        extra_query_params = {
            "response-content-disposition": f'attachment; filename="{safe_filename}"',
        }

    return client.presigned_get_object(
        get_bucket_name(),
        object_key,
        expires=timedelta(hours=expires_hours),
        extra_query_params=extra_query_params,
    )
