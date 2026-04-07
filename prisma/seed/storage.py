"""MinIO storage seeding — writes recipe files to object storage.

Uses the same env vars as the http-api: STORAGE_URL, STORAGE_ACCESS_KEY,
STORAGE_SECRET_ACCESS_KEY, STORAGE_BUCKET_NAME.
"""

import io
import os

from minio import Minio
from urllib.parse import urlparse


def get_seed_storage() -> tuple:
    """Get MinIO client + bucket for seeding. Returns (client, bucket) or (None, None)."""
    storage_url = os.environ.get("STORAGE_URL", "http://localhost:8675")
    access_key = os.environ.get("STORAGE_ACCESS_KEY", "concord")
    secret_key = os.environ.get("STORAGE_SECRET_ACCESS_KEY", "concordstorage!")
    bucket = os.environ.get("STORAGE_BUCKET_NAME", "concord")

    parsed = urlparse(storage_url)
    host = parsed.netloc or parsed.path
    secure = parsed.scheme == "https"

    try:
        client = Minio(endpoint=host, access_key=access_key, secret_key=secret_key, secure=secure)
        # Ensure bucket exists
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        return client, bucket
    except Exception as e:
        print(f"  ⚠ MinIO not available ({e}), skipping storage seeding")
        return None, None


def seed_recipe_to_minio(client: Minio, bucket: str, key: str, content: str) -> bool:
    """Write a recipe file to MinIO. Returns True on success."""
    try:
        content_bytes = content.encode("utf-8")
        client.put_object(
            bucket, key,
            io.BytesIO(content_bytes),
            length=len(content_bytes),
            content_type="text/x-shellscript",
        )
        return True
    except Exception as e:
        print(f"  ⚠ Failed to write {key}: {e}")
        return False
