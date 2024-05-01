# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_delete_uuid_bp = Blueprint('clusters_uuid_delete', __name__)
@clusters_delete_uuid_bp.route('/v1/clusters/<uuid>', methods=['DELETE'])
def clusters_delete_uuid_handler(uuid):
    try:
        # Validate url fields
        if not uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Call app
        error = appProxyServer.clusters_delete_one(uuid)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500