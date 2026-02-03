import re
from datetime import timedelta

from flask import redirect

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.services.storage.client import get_hardware_bucket_name, get_storage_client

_VALID_KEY_PATTERN = re.compile(r"^(components|assemblies)/[a-zA-Z0-9_-]+/hero\.\w+$")


@require_permissions(Permissions.ADMIN_HARDWARE_VIEW)
def get_hardware_image(key: str):
    """Redirect to a presigned MinIO URL for the given image key."""
    # Prevent path traversal
    if ".." in key or not _VALID_KEY_PATTERN.match(key):
        return bad_request("Invalid image key")

    try:
        client = get_storage_client()
        bucket = get_hardware_bucket_name()

        # Verify object exists
        try:
            client.stat_object(bucket, key)
        except Exception:
            return not_found("Image not found")

        url = client.presigned_get_object(bucket, key, expires=timedelta(hours=1))
        return redirect(url, code=302)
    except Exception as e:
        return internal_error(f"Failed to generate image URL: {str(e)}")
