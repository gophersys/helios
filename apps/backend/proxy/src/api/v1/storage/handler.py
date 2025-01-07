from flask import Blueprint, jsonify
from src.services.proxy import appProxyServer

storage_bp = Blueprint("storage", __name__)


@storage_bp.route("/v1/storage", methods=["GET"])
def storage_handler():
    """
    This route returns the storage usage information in a more human-readable format.
    """
    used_bytes, total_bytes = appProxyServer.get_database_usage()
    used_MB = used_bytes / (2**20)  # Convert bytes to megabytes
    total_MB = total_bytes / (2**20)  # Convert bytes to megabytes

    # Calculate percent used, round to 2 decimal places, and handle very small values
    if total_MB > 0:
        percent_used = (used_MB / total_MB) * 100
        # If the calculated percentage is very small, consider it as zero
        percent_used = round(percent_used, 2) if percent_used > 0.01 else 0
    else:
        percent_used = 0  # Avoid division by zero

    response = {
        "usedMB": round(used_MB, 2),  # Round to 2 decimal places for consistency
        "totalMB": round(total_MB, 2),
        "percentUsed": percent_used,
    }

    return jsonify(response), 200
