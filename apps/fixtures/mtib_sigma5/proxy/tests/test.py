import requests
import json  # Import the json module

# 
from tests.api.v1.cluster.create_test import ClusterCreateTest

SERVER_URL="http://localhost:6969"
DEPLOYMENT_PATH="/workspaces/concord/apps/fixtures/mtib_sigma5/runner/deploy/deployment.yaml"

if __name__ == "__main__":
    ClusterCreateTest().run_all_tests(SERVER_URL, DEPLOYMENT_PATH)