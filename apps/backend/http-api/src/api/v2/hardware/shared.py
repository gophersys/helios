from datetime import timedelta

from src.services.storage.client import get_hardware_bucket_name, get_storage_client

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def presigned_url(image_key: str | None) -> str | None:
    if not image_key:
        return None
    client = get_storage_client()
    return client.presigned_get_object(
        get_hardware_bucket_name(),
        image_key,
        expires=timedelta(hours=1),
    )
