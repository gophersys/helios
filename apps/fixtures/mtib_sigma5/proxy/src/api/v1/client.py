import os
import requests

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url

    # -------------------------------------------------------------------------------------------------
    #                                                                                    Cluster Create
    # -----------------------------------------------------------------------------------------------*/
    def create_cluster(self, name, deployment_file_path):
        """
        Creates a new cluster by uploading a deployment file and specifying a cluster name.

        Parameters:
        name (str): The unique name for the cluster.
        deployment_file_path (str): The file path to the Kubernetes deployment file.

        Returns:
        tuple: JSON response from the API and the status code of the response.
        """
        url = f"{self.base_url}/v1/cluster"
        files = {'deployment_file': (deployment_file_path, open(deployment_file_path, 'rb'))}
        data = {'name': name}
        try:
            response = requests.post(url, files=files, data=data)
            return response.json(), response.status_code
        finally:
            files['deployment_file'][1].close()
    # -------------------------------------------------------------------------------------------------
    #                                                                                      Cluster Read
    # -----------------------------------------------------------------------------------------------*/
    def read_cluster_info(self, uuid):
        """
        Retrieves the metadata of a cluster identified by the UUID.

        Parameters:
        uuid (str): The unique identifier for the cluster.

        Returns:
        tuple: JSON response from the API and the status code of the response.
        """
        url = f"{self.base_url}/v1/cluster/{uuid}"
        response = requests.get(url)
        return response.json(), response.status_code

    # -------------------------------------------------------------------------------------------------
    #                                                                                    Cluster Create
    # -----------------------------------------------------------------------------------------------*/
    def update_cluster_deployment(self, uuid, deployment_file_path):
        url = f"{self.base_url}/v1/cluster/{uuid}"
        files = {'deployment_file': open(deployment_file_path, 'rb')}
        response = requests.patch(url, files=files)

        if response.status_code == 200:
            # The response is expected to be an empty response with a 200 status code
            return {}, response.status_code
        else:
            try:
                json_response = response.json()
            except requests.exceptions.JSONDecodeError:
                # Handle the case where the response is not valid JSON
                return {"error": "Invalid response from server"}, response.status_code
            else:
                return json_response, response.status_code

    def delete_cluster(self, uuid):
        url = f"{self.base_url}/v1/cluster/{uuid}"
        response = requests.delete(url)
        return response.json(), response.status_code
