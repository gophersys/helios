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

    def test_cluster_list(self):
        """Test the /v1/cluster/list route."""
        response = requests.get(f"{self.base_url}/v1/cluster/list")
        if response.status_code == 200:
            response_data = response.json()
            if 'clusters' in response_data:
                print("ClusterList Passed", json.dumps(response_data, indent=4))
                return response_data['clusters']  # Return the list of clusters for further testing
            else:
                print("ClusterList Failed", json.dumps(response_data, indent=4))
                return None
        else:
            try:
                error_data = response.json()
                formatted_error = json.dumps(error_data, indent=4)
            except ValueError:
                formatted_error = response.text
            print(f"ClusterList Failed with status {response.status_code}: {formatted_error}")
            return None

    def test_cluster_info(self, cluster_ids):
        """Test the /v1/cluster/{clusterId}/info route for each cluster ID."""
        for cluster in cluster_ids:
            response = requests.get(f"{self.base_url}/v1/cluster/{cluster['uuid']}/info")
            if response.status_code == 200:
                response_data = response.json()
                print(f"ClusterInfo Passed for {cluster['uuid']}", json.dumps(response_data, indent=4))
            else:
                try:
                    error_data = response.json()
                    formatted_error = json.dumps(error_data, indent=4)
                except ValueError:
                    formatted_error = response.text
                print(f"ClusterInfo Failed for {cluster['uuid']} with status {response.status_code}: {formatted_error}")

    def test_cluster_list_tests(self, cluster_ids):
        """Test the /v1/cluster/{clusterId}/tests route for each cluster ID."""
        for cluster in cluster_ids:
            response = requests.get(f"{self.base_url}/v1/cluster/{cluster['uuid']}/tests")
            if response.status_code == 200:
                response_data = response.json()
                print(f"ClusterTests Passed for {cluster['uuid']}", json.dumps(response_data, indent=4))
            else:
                try:
                    error_data = response.json()
                    formatted_error = json.dumps(error_data, indent=4)
                except ValueError:
                    formatted_error = response.text
                print(f"ClusterTest Failed for {cluster['uuid']} with status {response.status_code}: {formatted_error}")

    def test_execute_test(self, cluster_ids):
        """Test the /v1/cluster/{clusterId}/tests/{testId}/execute route."""
        for cluster in cluster_ids:
            test_id = "d23d0e5b-1123-4219-8ba7-0a6539bb613f"  # Adjust based on your test setup
            response = requests.post(f"{self.base_url}/v1/cluster/{cluster['uuid']}/tests/{test_id}/execute")
            
            if response.status_code == 200:
                print(f"Test execution started for cluster {cluster} and test {test_id}.")
            else:
                try:
                    error_data = response.json()
                    formatted_error = json.dumps(error_data, indent=4)
                except ValueError:
                    formatted_error = response.text
                print(f"Test execution failed for cluster {cluster} with status {response.status_code}: {formatted_error}")

    def run_tests(self):
        """Run all tests."""
        print("Testing HealthCheck...")
        self.test_health_check()

        print("Testing ClusterList...")
        cluster_ids = self.test_cluster_list()

        if cluster_ids:
            print("Testing ClusterInfo for each cluster...")
            self.test_cluster_info(cluster_ids)

            print("Testing ClusterTests for each cluster...")
            self.test_cluster_list_tests(cluster_ids)

            print("Testing ExecuteTest for each cluster...")
            self.test_execute_test(cluster_ids)

if __name__ == "__main__":
    client = APITestClient()
    client.run_tests()