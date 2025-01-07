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
        health_rsp: ApiResponse = api.v1_health_proxy_get_with_http_info()
        logging.info(f"v1_health_proxy_get_with_http_info ({health_rsp.status_code}): {health_rsp.data}")
    except Exception as e:
        logging.error(f"v1_health_proxy_get_with_http_info failed: {e}")

    # Platforms test
    try:
        platform_create_rsp: ApiResponse = api.v1_catalog_platforms_post_with_http_info()
        logging.info(f"v1_catalog_platforms_post_with_http_info ({health_rsp.status_code}): {health_rsp.data}")
    except Exception as e:
        logging.error(f"v1_catalog_platforms_post_with_http_info failed: {e}")

    try:
        platform_create_rsp: ApiResponse = api.v1_catalog_platforms_get_with_http_info()
        logging.info(f"v1_catalog_platforms_get_with_http_info ({health_rsp.status_code}): {health_rsp.data}")
    except Exception as e:
        logging.error(f"v1_catalog_platforms_get_with_http_info failed: {e}")

    logging.info("All routes passed!")
