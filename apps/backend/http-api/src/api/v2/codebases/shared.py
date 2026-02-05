from src.services.storage.client import presigned_get_url

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

ALLOWED_ARTIFACT_EXTENSIONS = {
    "zip", "hex", "bin", "ckbin", "elf", "img",
    "tar", "gz", "tgz",
    "json", "xml", "csv", "txt", "pdf",
    "png", "jpg", "jpeg", "webp",
}

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def presigned_url(key: str | None, download_filename: str | None = None) -> str | None:
    return presigned_get_url(key, download_filename=download_filename)
