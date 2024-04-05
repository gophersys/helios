# Standard includes
import logging

# 3rd party includes
from flask import Blueprint, jsonify, request 

# Application server
from src.server.proxy import ProxyServer

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
        "runners": [
            {
                "id": runner.id,
                "name": runner.name,
                "hostname": runner.hostname,
                "serverPort": runner.serverPort,
                "ipAddr": runner.ipAddr,
                "isInPanel": runner.isInPanel,
                "panelId": runner.panelId,
                "supportedSoftware": [
                    {
                        "softwareType": software.softwareType,
                        "executableName": software.executableName,
                        "version": software.version,
                    }
                    for software in runner.supportedSoftware  # Iterating over repeated SoftwareInfo
                ],
            }
            for runner in cluster_info.runners  # Iterating over repeated RunnerInfo
        ],
        "supportedHardware": {
            "model": cluster_info.supportedHardware.model,
            "version": cluster_info.supportedHardware.version,
        }
    }

    # Return success status with the cluster's info
    return jsonify(cluster_response), 200