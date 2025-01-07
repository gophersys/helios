# openapi_client.DefaultApi

All URIs are relative to *http://127.0.0.1:5000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**v1_health_proxy_get**](DefaultApi.md#v1_health_proxy_get) | **GET** /v1/health/proxy | Health check endpoint
[**v1_storage_get**](DefaultApi.md#v1_storage_get) | **GET** /v1/storage | Storage usage information


# **v1_health_proxy_get**
> V1HealthProxyGet200Response v1_health_proxy_get()

Health check endpoint

Returns a 200 status if the server is running, confirming that the service is alive.

### Example


```python
import openapi_client
from openapi_client.models.v1_health_proxy_get200_response import V1HealthProxyGet200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://127.0.0.1:5000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://127.0.0.1:5000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)

    try:
        # Health check endpoint
        api_response = api_instance.v1_health_proxy_get()
        print("The response of DefaultApi->v1_health_proxy_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_health_proxy_get: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

[**V1HealthProxyGet200Response**](V1HealthProxyGet200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Service is alive and running |  -  |
**500** | Server error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_storage_get**
> V1StorageGet200Response v1_storage_get()

Storage usage information

Returns the current storage usage in megabytes and percentage used.

### Example


```python
import openapi_client
from openapi_client.models.v1_storage_get200_response import V1StorageGet200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://127.0.0.1:5000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://127.0.0.1:5000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)

    try:
        # Storage usage information
        api_response = api_instance.v1_storage_get()
        print("The response of DefaultApi->v1_storage_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_storage_get: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

[**V1StorageGet200Response**](V1StorageGet200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successfully retrieved storage information |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

