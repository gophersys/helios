import requests
import json

class ClusterCreateTest:    
    def test_missing_name(self):
        """Test creating a cluster without a name."""
        url = f"{self.base_url}/v1/cluster"
        # Assume `dummy_deployment.yaml` is a valid deployment file in the current directory
        files = {'deployment_file': open(self.deployment_path, 'rb')}
        response = requests.post(url, files=files)
        assert response.status_code == 400, "Expected 400 Bad Request for missing name"
        print("Test missing name passed")
    
    def test_missing_deployment_file(self):
        """Test creating a cluster without a deployment file."""
        url = f"{self.base_url}/v1/cluster"
        data = {'name': 'TestCluster'}
        response = requests.post(url, data=data)
        assert response.status_code == 400, "Expected 400 Bad Request for missing deployment file"
        print("Test missing deployment file passed")
    
    def test_duplicate_name(self):
        """Test creating two clusters with the same name."""
        url = f"{self.base_url}/v1/cluster"
        name = "DuplicateNameTest"
        # Assume `valid_deployment.yaml` is a valid deployment file
        files = {'deployment_file': open(self.deployment_path, 'rb')}
        data = {'name': name}
        # Create the first cluster
        response1 = requests.post(url, data=data, files=files)
        assert response1.status_code == 200, "Expected 200 OK for first cluster creation"
        # Attempt to create the second cluster with the same name
        response2 = requests.post(url, data=data, files=files)
        assert response2.status_code == 400, "Expected 400 Bad Request for duplicate name"
        print("Test duplicate name passed")
    
    def test_valid_cluster_creation(self):
        """Test creating a cluster with valid input."""
        url = f"{self.base_url}/v1/cluster"
        name = "ValidClusterTest"
        files = {'deployment_file': open(self.deployment_path, 'rb')}
        data = {'name': name}
        response = requests.post(url, data=data, files=files)
        assert response.status_code == 200, "Expected 200 OK for valid cluster creation"
        print("Test valid cluster creation passed")
    
    def run_all_tests(self, base_url, deployment_path):
        """Run all the test cases."""
        self.base_url = base_url
        self.deployment_path = deployment_path
        print("Starting cluster creation tests...")
        self.test_missing_name()
        self.test_missing_deployment_file()
        self.test_duplicate_name()
        self.test_valid_cluster_creation()
        print("All tests completed.")
