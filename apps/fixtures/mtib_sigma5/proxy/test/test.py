import requests
import json  # Import the json module

class APITestClient:
    def __init__(self, base_url="http://localhost:6969"):
        self.base_url = base_url

    def test_health_check(self):
        """Test the /v1/HealthCheck route."""
        response = requests.get(f"{self.base_url}/v1/HealthCheck")
        if response.status_code == 200:
            # Use json.loads to parse the response content
            response_data = response.json()
            # Check the status in the parsed JSON data
            if response_data.get('status') == 'Ready':
                print(json.dumps(response_data, indent=4))
                print("HealthCheck Passed")
            else:
                # Use json.dumps to print the formatted JSON
                print("HealthCheck Failed", json.dumps(response_data, indent=4))
        else:
            # In case of non-200 responses, also print the response as formatted JSON
            # This assumes the response is in JSON format; you might adjust error handling as needed
            try:
                error_data = response.json()
                formatted_error = json.dumps(error_data, indent=4)
            except ValueError:
                # If response is not in JSON format, fallback to raw content
                formatted_error = response.text
            print(f"HealthCheck Failed with status {response.status_code}: {formatted_error}")

    def test_register_cluster(self):
        """Test the /v1/cluster/register route."""
        payload = {
            "cluster_id": "test-cluster-001",
            "ip": "192.168.1.1",
            # Include additional metadata as needed
        }
        response = requests.post(f"{self.base_url}/v1/cluster/register", json=payload)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('status') == 'Registered' and response_data.get('cluster_id') == payload['cluster_id']:
                print("RegisterCluster Passed", json.dumps(response_data, indent=4))
            else:
                print("RegisterCluster Failed", json.dumps(response_data, indent=4))
        else:
            try:
                error_data = response.json()
                formatted_error = json.dumps(error_data, indent=4)
            except ValueError:
                formatted_error = response.text
            print(f"RegisterCluster Failed with status {response.status_code}: {formatted_error}")

    def run_tests(self):
        """Run all tests."""

        print("Testing HealthCheck...")
        self.test_health_check()

        print("Testing RegisterCluster...")
        self.test_register_cluster()


if __name__ == "__main__":
    client = APITestClient()
    client.run_tests()
