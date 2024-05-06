# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, request, jsonify

# App includes
from src.services.proxy import appProxyServer

# Flask Route
clusters_register_uuid_bp = Blueprint('clusters_register_uuid', __name__)
@clusters_register_uuid_bp.route('/v1/clusters/<uuid>/register', methods=['POST'])
def clusters_register_uuid_cluster(uuid):
    try:
        # Validate url fields
        if not uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400
        
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        cluster_url = data.get('url')
        if not cluster_url:
            return jsonify({"error": "Bad request, 'url' field is required."}), 400

        # Tell the proxy a new cluster is trying to register itself
        error = appProxyServer.clusters_register(uuid, cluster_url)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400
        else:
            return "", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500