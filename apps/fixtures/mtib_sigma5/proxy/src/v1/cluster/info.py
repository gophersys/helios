# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Application server
from src.proxy import ProxyServer

# Route blueprint
cluster_info_bp = Blueprint('cluster_info', __name__)

@cluster_info_bp.route('/v1/cluster/<cluster_uuid>/info', methods=['GET'])
def cluster_info(cluster_uuid):
    # Input validation
    if not cluster_uuid:
        return jsonify({"error": "Bad request, 'cluster_uuid' parameter is required."}), 400

    # Get the cluster's information by its UUID
    found, cluster_info = ProxyServer().get_cluster_info(cluster_uuid)

    # Handle case where cluster information is not found
    if not found:
        return jsonify({"error": f"Cluster with UUID {cluster_uuid} not found."}), 404

    # Convert ClusterInfo into a JSON-serializable dict
    cluster_response = {
        "name": cluster_info.name,
        # Convert RunnerInfo into a JSON-serializable dict
        "runners": [
            {
                "id": runner.id,
                "name": runner.name,
                "hostname": runner.hostname,
                "serverPort": runner.serverPort,
                "isInPanel": runner.isInPanel,
                "panelId": runner.panelId,
                "supportedFirmware": [
                    {
                        "fileName": software.name,
                        "fileSizeKb": software.sizeKb,
                        "sha256Digest": software.sha256Digest,
                    }
                    for software in runner.supportedFirmware  # Iterating over repeated FwFileInfo
                ],
            }
            for runner in cluster_info.runners  # Iterating over repeated RunnerInfo
        ],
        "supportedHardware": [
            {
                "model": hardware.model,
                "version": hardware.version,
            }
            for hardware in cluster_info.supportedHardware
        ]
    }

    # Return success status with the cluster's info
    return jsonify(cluster_response), 200