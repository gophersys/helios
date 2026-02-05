from src.services.storage.client import presigned_get_url

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def presigned_url(image_key: str | None) -> str | None:
    return presigned_get_url(image_key)
