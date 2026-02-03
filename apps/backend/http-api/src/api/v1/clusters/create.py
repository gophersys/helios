# standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify, request

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_create_bp = Blueprint("clusters_create", __name__)


@clusters_create_bp.route("/v1/clusters", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Create"])
def clusters_create_handler():
    try:
        # Access JSON data from the request
        data = request.get_json()

        # Validate request fields
        name = data.get("name")
        if not name:
            return jsonify({"error": "Bad request, 'name' field is required."}), 400

        type = data.get("type")
        if not type:
            return jsonify({"error": "Bad request, 'type' field is required."}), 400

        # Call app
        error, cluster_uuid = appProxyServer.clusters_create(name, type)
        if error:
            logging.error(error)
            return jsonify({"error": error}), 400

        return jsonify({"uuid": cluster_uuid}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
