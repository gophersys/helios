from flask import Flask


def hosts_register(api: Flask):
    pass
    ## Host Routes
    # List Hosts: GET /v1/catalog/hosts
    # Create Host: POST /v1/catalog/hosts
    #   Request Body:
    #   {
    #       "name": "string"  # Host name (e.g., "nrf9160")
    #   }
    #   Response:
    #   {
    #       "id": "string",   # UUID of the host
    #       "name": "string"  # Host name
    #   }
    # Delete Host by UUID: DELETE /v1/catalog/hosts/{hostId}
