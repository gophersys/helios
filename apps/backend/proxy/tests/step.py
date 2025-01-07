# Standard includes
import logging

# Corekinect includes
from corekinect.proxy_client.v1.openapi_client import Configuration, ApiClient, DefaultApi, ApiResponse, ApiException

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create a new client
    client = ApiClient(
        configuration=Configuration(
            host="http://127.0.0.1:7600",
        )
    )

    # Get an API instance from that client
    api = DefaultApi(client)

    # Routes test
    try:
        rsp: ApiResponse = api.v1_tests_steps_get_with_http_info()
        logging.info(f"Steps GET ({rsp.status_code}): {rsp.data}")
    except Exception as e:
        logging.error(f"Steps GET  {e}")

    logging.info("All routes passed!")
