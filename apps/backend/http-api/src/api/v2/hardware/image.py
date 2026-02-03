from datetime import timedelta

from flask import redirect

from src.lib.decorators import require_auth
from src.lib.errors import internal_error, not_found
from src.services.storage.client import get_hardware_bucket_name, get_storage_client


@require_auth
def get_hardware_image(key: str):
    """Redirect to a presigned MinIO URL for the given image key."""
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
