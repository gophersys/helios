# V1StorageGet200Response


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**used_mb** | **float** |  | [optional] 
**total_mb** | **float** |  | [optional] 
**percent_used** | **float** |  | [optional] 

## Example

```python
from openapi_client.models.v1_storage_get200_response import V1StorageGet200Response

# TODO update the JSON string below
json = "{}"
# create an instance of V1StorageGet200Response from a JSON string
v1_storage_get200_response_instance = V1StorageGet200Response.from_json(json)
# print the JSON string representation of the object
print(V1StorageGet200Response.to_json())

# convert the object into a dict
v1_storage_get200_response_dict = v1_storage_get200_response_instance.to_dict()
# create an instance of V1StorageGet200Response from a dict
v1_storage_get200_response_from_dict = V1StorageGet200Response.from_dict(v1_storage_get200_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


