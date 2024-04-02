import subprocess
import json
import logging
from flask import Blueprint, jsonify, make_response
import concurrent.futures

healthcheck_bp = Blueprint('healthcheck', __name__)

def ping_host(hostname):
    """Ping a hostname to check network connectivity."""
    response = subprocess.run(["ping", "-c", "1", hostname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {"hostname": hostname, "reachable": response.returncode == 0}

def get_kubectl_nodes():
    """Fetch Kubernetes nodes information using kubectl."""
    try:
        kubectl_response = subprocess.run(["kubectl", "get", "nodes", "-o", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return json.loads(kubectl_response.stdout)
    except subprocess.CalledProcessError as e:
        logging.error("Failed to fetch node details from kubectl.")
        raise e
    except json.JSONDecodeError as e:
        logging.error("Invalid JSON from kubectl.")
        raise e

def update_node_status(nodes, kubectl_data):
    """Update nodes information based on kubectl data."""
    for k8s_node in kubectl_data.get("items", []):
        hostname = k8s_node["metadata"]["name"]
        for node in nodes:
            if node["hostname"] == hostname and node["status"] != "NotFound":
                node["ipAddr"] = next((addr["address"] for addr in k8s_node["status"]["addresses"] if addr["type"] == "InternalIP"), "0")
                ready_condition = next((condition for condition in k8s_node["status"]["conditions"] if condition["type"] == "Ready"), None)
                node["status"] = "Ready" if ready_condition and ready_condition["status"] == "True" else "NotReady"
                break
    return nodes

def get_deployment_status():
    """Fetch the status of the deployment and its pods in the default namespace."""
    try:
        deployment_response = subprocess.run(
            ["kubectl", "get", "deployment", "-o", "json", "--namespace=default"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        deployment_data = json.loads(deployment_response.stdout)

        # Check if there are any deployments
        if not deployment_data["items"]:
            # No deployments found
            logging.debug("No deployments found in the default namespace.")
            return None, None  # Indicate that no deployments are present

        deployment_name = deployment_data["items"][0]["metadata"]["name"]

        pod_response = subprocess.run(
            ["kubectl", "get", "pods", "-l", f"app={deployment_name}", "-o", "json", "--namespace=default"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        pod_data = json.loads(pod_response.stdout)

        logging.debug("Successfully fetched deployment and pod details from kubectl.")
        return deployment_data, pod_data
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to fetch deployment or pod details from kubectl: {e.stderr.decode().strip()}")
        raise
    except json.JSONDecodeError as e:
        logging.error("Invalid JSON from kubectl in deployment or pod details.")
        raise

@healthcheck_bp.route('/v1/HealthCheck', methods=['GET'])
def health_check():
    logging.info("Starting HealthCheck")
    hostnames = ["control-plane", "slot-1", "slot-2", "slot-3", "slot-4", "slot-5"]
    nodes = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(hostnames)) as executor:
        ping_results = list(executor.map(ping_host, hostnames))
    
    for result in ping_results:
        nodes.append({"hostname": result["hostname"], "status": "NotFound" if not result["reachable"] else "Unknown", "ipAddr": "0" if not result["reachable"] else "Unknown"})

    try:
        kubectl_data = get_kubectl_nodes()
        nodes = update_node_status(nodes, kubectl_data)
        deployment_data = get_deployment_status()

        # Parse the deployment info
        deployment_data, pod_data = get_deployment_status()

        if deployment_data is None or pod_data is None:
            deployment_status = {"status": "NoDeployments", "message": "No deployments found in the default namespace."}
        else:
            deployment = deployment_data["items"][0]
            replicas = deployment["status"].get("replicas", 0)
            available_replicas = deployment["status"].get("availableReplicas", 0)

            # Prepare detailed pod status info
            pod_details = []
            for pod in pod_data["items"]:
                pod_status = {"name": pod["metadata"]["name"], "phase": pod["status"]["phase"]}
                if pod_status["phase"] != "Running":
                    pod_status["reason"] = pod["status"].get("conditions", [{}])[0].get("reason", "Unknown reason")
                pod_details.append(pod_status)

            # Assess deployment readiness
            deployment_status = {
                "status": "Ready" if replicas > 0 and replicas == available_replicas else "NotReady",
                "replicas": replicas,
                "availableReplicas": available_replicas,
                "pods": pod_details
            }

    except Exception as e:
        error_message = str(e) if not hasattr(e, 'stderr') else e.stderr.decode().strip()
        return make_response(jsonify(error="Failed to communicate with Kubernetes cluster or parse deployment status", status=503, details=error_message), 503)

    service_status = "Ready" if all(node["status"] == "Ready" for node in nodes) and deployment_status["status"] == "Ready" else "NotReady"
    
    return jsonify(status=service_status, nodes=nodes, deploymentStatus=deployment_status), 200 if service_status == "Ready" else 503
