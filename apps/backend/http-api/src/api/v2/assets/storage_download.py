"""Generic MinIO storage download endpoint."""

import logging
from flask import request, Response
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.services.storage.client import get_storage_client, sanitize_filename

logger = logging.getLogger(__name__)

ALLOWED_PREFIXES = ("products/", "firmware/", "asset-sets/", "test-packages/")


@require_permissions(Permissions.BUILDS_VIEW)
def download_storage_file():
    """GET /v2/storage/download?key=<storage_key> — Download a file from MinIO."""
    key = request.args.get("key", "").strip()
    if not key:
        return bad_request("key parameter is required")

    if not any(key.startswith(p) for p in ALLOWED_PREFIXES):
        return bad_request("Access denied: path not in allowed prefixes")

    if ".." in key:
        return bad_request("Invalid key")

    try:
        storage = get_storage_client()
        response = storage.get_object("concord", key)
        data = response.read()
        response.close()
        response.release_conn()

        raw_filename = key.split("/")[-1]
        filename = sanitize_filename(raw_filename)
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(data)),
            },
        )
    except Exception as e:
        logger.error("Failed to download %s: %s", key, e)
        return not_found("File not found")
