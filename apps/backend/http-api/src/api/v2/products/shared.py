from src.services.storage.client import presigned_get_url

ALLOWED_FIRMWARE_EXTENSIONS = {"zip", "hex", "ckbin", "bin"}

MIME_TYPES = {
    "zip": "application/zip",
    "hex": "application/octet-stream",
    "ckbin": "application/octet-stream",
    "bin": "application/octet-stream",
}


def presigned_url(key: str | None, download_filename: str | None = None) -> str | None:
    return presigned_get_url(key, download_filename=download_filename)
