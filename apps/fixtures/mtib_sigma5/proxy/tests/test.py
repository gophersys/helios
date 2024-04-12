import requests
import json  # Import the json module
import sys
import logging

# API client
from src.api.v1.client import APIClient

from tests.api.v1.cluster.create_test import ClusterCreateTest

CLUSTER_NAME="Test Cluster 4"
SERVER_URL="http://localhost:6969"
OLD_DEPLOYMENT_PATH="/workspaces/concord/apps/fixtures/mtib_sigma5/runner/deploy/deployment_old.yaml"
NEW_DEPLOYMENT_PATH="/workspaces/concord/apps/fixtures/mtib_sigma5/runner/deploy/deployment_new.yaml"

if __name__ == "__main__":
    # ClusterCreateTest().run_all_tests(SERVER_URL, DEPLOYMENT_PATH)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Instantiate a new client
    client:APIClient = APIClient(
        base_url=SERVER_URL
    )

    # Create a new cluster
    # response, status_code = client.create_cluster(CLUSTER_NAME, OLD_DEPLOYMENT_PATH)
    # if status_code != 200:
    #     logging.error(f"Could not create new cluster: {response}")
    #     sys.exit(1)

    # # Extract the uuid field from the response
    # cluster_uuid = response.get('uuid')
    # if not cluster_uuid:
    #     logging.error("No UUID in response; invalid server response.")
    #     sys.exit(1)

    # logging.info(f"Cluster created succesfully with id: {cluster_uuid}")

    # # Read cluster info
    # response, status_code = client.read_cluster_info(cluster_uuid)
    # if status_code != 200:
    #     logging.error(f"Could not create new cluster: {response}")
    #     sys.exit(1)

    # # Extract the uuid field from the response
    # cluster_name = response.get('name')
    # if not cluster_name:
    #     logging.error("No UUID in response; invalid server response.")
    #     sys.exit(1)

    # if cluster_name != CLUSTER_NAME:
    #     logging.error("Cluster name did not match! CREATE/READ routes issue?")
    #     sys.exit(1)

    # logging.info(f"Cluster name matches for {cluster_uuid}")

    # # Update deployment
    response, status_code = client.update_cluster_deployment("a1559972-4446-4d24-b90c-e752bc75e92d", NEW_DEPLOYMENT_PATH)
    if status_code != 200:
        logging.error(f"Unable to update deployment: {response}")
        sys.exit(1)