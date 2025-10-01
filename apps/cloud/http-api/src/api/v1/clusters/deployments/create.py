# standard includes
import logging
import os

# 3rd party includes
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request

# App includes
from api.v1.clusters.deployments import apply_uuid
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_create_bp = Blueprint("clusters_deployments_create", __name__)


@clusters_deployments_create_bp.route("/v1/clusters/<uuid>/deployments", methods=["POST"])
@authMiddleware.check_permissions(["Concord.Cluster.Deployment.Create"])
def clusters_deployments_create_handler(uuid):
    try:
        # Validate url fields
        if not uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Access the cluster name from the request
        name = request.form.get("name")  # For form data
        if not name:
            name = request.json.get("name")  # For JSON data
            if not name:
                return jsonify({"error": "Bad request, 'name' field is required."}), 400

        # Access JSON data from the request
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "Bad request, 'file' field is required."}), 400

        # Apply is an optional field
        apply = request.form.get("apply")

        # Generate a unique filename and save it to a temporary folder for post-processing
        unique_filename = secure_filename(f"{uuid4()}-{file.filename}")
        temp_file_path = os.path.join("/tmp", unique_filename)
        file.save(temp_file_path)

        # Call App
        error, deployment_uuid = appProxyServer.cluster_deployments_create(uuid, name, temp_file_path)

        os.remove(temp_file_path)  # Delete the temporary file created regardless of request success

        if apply is not None and apply == "true":
            error = appProxyServer.clusters_deployments_apply(uuid, deployment_uuid)
            if error:
                logging.error(error)
                return jsonify({"error": error}), 400

        if error:
            logging.error(error)
            return jsonify({"error": error}), 400

        return jsonify({"uuid": deployment_uuid}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
