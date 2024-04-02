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

    def test_list_tests(self):
        """Test the /v1/Tests route for listing tests."""
        response = requests.get(f"{self.base_url}/v1/Tests")
        if response.status_code == 200:
            response_data = response.json()
            # Basic validation of the response structure
            if "tests" in response_data and isinstance(response_data["tests"], list):
                print("ListTests Passed:", json.dumps(response_data, indent=4))
                return
        # Handle failure cases
        print("ListTests Failed:", json.dumps(response.json(), indent=4))

    def run_single_test(self, test_id, slots_info):
        """Run a specific test by test_id on designated slots."""
        url = f"{self.base_url}/v1/tests/{test_id}/run"
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps(slots_info)
        
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            print(f"Test {test_id} execution result:", json.dumps(response.json(), indent=4))
        else:
            print(f"Test {test_id} execution failed with status {response.status_code}:", response.text)

    def run_tests(self):
        """Run all tests."""
        # print("Testing HealthCheck...")
        # self.test_health_check()
        print("Testing ListTests...")
        self.test_list_tests()

        response = requests.get(f"{self.base_url}/v1/Tests")
        if response.status_code == 200:
            tests = response.json().get('tests', [])
            if not tests:
                print("No tests to run.")
                return

            # Define slots information based on your criteria
            slots_info = {
                "single": False,
                "slot-1": True,
                "slot-2": False,
                "slot-3": True,
                "slot-4": False,
                "slot-5": True,
            }

            for test in tests:
                test_id = test.get('id')
                print(f"Running test: {test['name']} (ID: {test_id})")
                self.run_single_test(test_id, slots_info)
        else:
            print("Failed to retrieve list of tests:", response.text)

if __name__ == "__main__":
    client = APITestClient()
    client.run_tests()
