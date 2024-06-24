# Standard includes
import logging
import os

# 3rd party includes
from flask import Blueprint, jsonify, send_file

# App includes
from src.middleware.permissions import authMiddleware
from src.services.proxy import appProxyServer

# Flask Route
clusters_deployments_status_uuid_bp = Blueprint("clusters_deployments_status_uuid", __name__)


@clusters_deployments_status_uuid_bp.route(
    "/v1/clusters/<cluster_uuid>/deployments/<deployment_uuid>/status", methods=["GET"]
)
@authMiddleware.check_permissions(["Concord.Cluster.Deployment.Read"])
def clusters_deployments_status_uuid_handler(cluster_uuid, deployment_uuid):
    try:
        # Validate url fields
        if not cluster_uuid or not deployment_uuid:
            return jsonify({"error": "Bad request, malformed url."}), 400

        # Call app
        error, deployments_info = appProxyServer.cluster_deployments_get_status(cluster_uuid)
        if error:
            logging.error(error)
            return jsonify({"error": f"{error}"}), 400

        # Marshaling the deployment information into JSON for all deployments
        deployments_info_json = [
            {
                "name": deployment.name,
                "uuid": deployment.uuid,
                "podsInfo": [
                    {
                        "name": pod.name,
                        "image": pod.image,
                        "node": pod.node,
                        "status": pod.status,
                        "restarts": pod.restarts,
                        "ready": pod.ready,
                    }
                    for pod in deployment.pods_info
                ],
            }
            for deployment in deployments_info
        ]

        # Send the file as the response
        return jsonify(deployments_info_json), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
