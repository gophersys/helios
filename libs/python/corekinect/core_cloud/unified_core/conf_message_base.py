"""
Configuration message base classes for REST API interaction.

This module provides base classes for configuration messages that communicate
with REST APIs. It handles serialization/deserialization between Python dataclasses
and API JSON payloads using the api_translation annotation system.
"""

from dataclasses import dataclass, fields
from typing import Any, ClassVar, Dict, Mapping, Tuple, Type

from .api_map import extract_api_field_specs
from ..api_interface import CoreCloudRestInterface


@dataclass(frozen=True, slots=True)
class ConfigMessageBase:
    """
    Base class for configuration messages that interact with REST APIs.

    This class provides automatic serialization/deserialization between Python
    dataclasses and API JSON payloads. Subclasses should be dataclasses with fields
    annotated using api_translation to define API field mappings.

    Subclasses must define:
        api_set_endpoint: ClassVar[Tuple[str, str]]
            HTTP method and endpoint path for setting configuration.
            Example: ("PUT", "/System/Devices/Configurations/Gps")

    Attributes:
        api_set_endpoint (ClassVar[Tuple[str, str]]): HTTP method and endpoint path
            for sending this configuration to the API.

    Example:
        ```python
        @dataclass(frozen=True, slots=True)
        class GpsConfig(ConfigMessageBase):
            # Define the API endpoint for this config
            api_set_endpoint: ClassVar[Tuple[str, str]] = (
                "PUT",
                "/System/Devices/Configurations/Gps"
            )

            # Field with API mapping
            update_frequency: Annotated[int, api_translation(
                api='gnssUpdateFrequency',
                coerce=int,
                required=True
            )]

            # Another API-mapped field
            psm_enabled: Annotated[bool, api_translation(
                api='isPsmEnabled',
                coerce=bool,
                required=False
            )]

        # Create and send configuration
        config = GpsConfig(update_frequency=60, psm_enabled=True)
        config.send_via_api(device_id_hex="70B3D584C01E1445", env="DEV_1_0")
        ```

    Methods:
        to_api_payload: Convert this message instance to an API JSON payload dict.
        from_api_payload: Create a message instance from an API JSON payload.
        send_via_api: Send this configuration to the API endpoint.
    """

    # Subclasses must define the API endpoint (method, path)
    api_set_endpoint: ClassVar[Tuple[str, str]]

    @classmethod
    def _api_specs(cls):
        """
        Extract API field specifications from this dataclass's annotations.

        This method caches and returns the field mapping specifications that define
        how dataclass fields map to API JSON keys. It uses extract_api_field_specs()
        to introspect api_translation annotations.

        Returns:
            Dict[str, _ApiFieldSpec]: Mapping of Python field names to their API specs.

        Note:
            This is called internally by to_api_payload() and from_api_payload().
            Results are not cached, so repeated calls perform fresh introspection.
        """
        return extract_api_field_specs(cls)

    def to_api_payload(self) -> Dict[str, Any]:
        """
        Convert this message instance to an API-compatible JSON payload.

        This method serializes the dataclass fields to a dictionary suitable for
        sending to the REST API. It:
        1. Extracts API field specifications from annotations
        2. Iterates through dataclass fields
        3. Applies type coercion if specified
        4. Validates required fields
        5. Omits fields marked with omit=True
        6. Maps Python field names to API JSON keys

        Returns:
            Dict[str, Any]: A dictionary with API field names as keys and serialized
                           values ready for JSON encoding.

        Raises:
            ValueError: If a required field is None or missing.
            TypeError: If type coercion fails for a field value.

        Example:
            ```python
            config = GpsConfig(update_frequency=60, psm_enabled=True)
            payload = config.to_api_payload()
            # Result: {
            #   'gnssUpdateFrequency': 60,
            #   'isPsmEnabled': True
            # }
            ```

        Note:
            Fields without api_translation annotations are silently ignored.
            This allows mixing API-mapped and internal-only fields in the same dataclass.
        """
        # Get the API specifications for all fields
        field_specifications = type(self)._api_specs()

        # Build the payload dictionary
        api_payload: Dict[str, Any] = {}

        # Iterate through all dataclass fields
        for dataclass_field in fields(self):
            # Get the API spec for this field (if it exists)
            api_spec = field_specifications.get(dataclass_field.name)

            # Skip fields without API mapping
            if not api_spec:
                continue

            # Skip fields marked as omit (local-only fields)
            if api_spec.omit:
                continue

            # Get the current value of this field
            field_value = getattr(self, dataclass_field.name)

            # Validate required fields
            if field_value is None:
                if api_spec.required:
                    raise ValueError(
                        f"Field '{dataclass_field.name}' is required for API send " f"but is currently None."
                    )
                # Skip optional None values
                continue

            # Apply type coercion if specified
            if api_spec.coerce and not isinstance(field_value, api_spec.coerce):
                try:
                    field_value = api_spec.coerce(field_value)
                except Exception as e:
                    raise TypeError(
                        f"Failed to coerce field '{dataclass_field.name}' to " f"{api_spec.coerce.__name__}: {e}"
                    ) from e

            # Add to payload using the API field name
            api_payload[api_spec.json] = field_value

        return api_payload

    @classmethod
    def from_api_payload(cls: Type[Any], api_data: Mapping[str, Any]) -> Any:
        """
        Create a message instance from an API JSON payload.

        This method deserializes an API JSON response into a dataclass instance.
        It performs the reverse mapping of to_api_payload(), converting API field
        names back to Python attribute names.

        Args:
            api_data (Mapping[str, Any]): Dictionary from API JSON response with
                                          API field names as keys.

        Returns:
            Instance of this configuration message class with fields populated
            from the API data.

        Example:
            ```python
            api_response = {
                'gnssUpdateFrequency': 60,
                'isPsmEnabled': True
            }
            config = GpsConfig.from_api_payload(api_response)
            # Result: GpsConfig(update_frequency=60, psm_enabled=True)
            ```

        Note:
            - Unknown API fields (not in api_translation annotations) are ignored
            - Type coercion is NOT automatically applied during deserialization
            - Missing optional fields default to None
        """
        # Get API specifications for reverse mapping
        field_specifications = cls._api_specs()

        # Build reverse map: API field name -> Python field name
        api_name_to_python_name = {
            api_spec.json: python_field_name for python_field_name, api_spec in field_specifications.items()
        }

        # Extract only the fields we recognize and map them to Python names
        constructor_kwargs = {
            api_name_to_python_name[api_key]: api_value
            for api_key, api_value in api_data.items()
            if api_key in api_name_to_python_name
        }

        # Construct and return the instance
        return cls(**constructor_kwargs)  # type: ignore[arg-type]

    def send_via_api(self, device_id_hex: str, *, env: str = "DEV_1_0") -> None:
        """
        Send this configuration to the API endpoint for a specific device.

        This method:
        1. Converts the message to an API payload using to_api_payload()
        2. Opens a connection to the Core Cloud REST interface
        3. Sends the configuration to the endpoint defined in api_set_endpoint
        4. Raises an exception if the request fails

        Args:
            device_id_hex (str): Device identifier as a hexadecimal string.
                                Example: "70B3D584C01E1445"
            env (str): Environment namespace for the API connection.
                      Options: "DEV_1_0", "VAL_1_0", "DEV_0_9"
                      Default: "DEV_1_0"

        Raises:
            NotImplementedError: If api_set_endpoint is not defined in the subclass.
            HTTPError: If the API request fails (via raise_for_status()).
            ValueError: If required fields are missing (from to_api_payload()).

        Example:
            ```python
            config = GpsConfig(update_frequency=60, psm_enabled=True)

            # Send to development environment
            config.send_via_api(
                device_id_hex="70B3D584C01E1445",
                env="DEV_1_0"
            )

            # Send to validation environment
            config.send_via_api(
                device_id_hex="70B3D584C01E1445",
                env="VAL_1_0"
            )
            ```

        Note:
            The API connection is automatically closed after the request completes
            (context manager handles cleanup).
        """
        # Extract HTTP method and path from class variable
        http_method, api_endpoint_path = type(self).api_set_endpoint

        # Convert this message to API payload format
        request_payload = self.to_api_payload()

        # Open API connection and send request
        with CoreCloudRestInterface(env_namespace=env) as api_client:
            # Make the API request
            response = api_client.request(
                http_method, api_endpoint_path, params={"deviceId": device_id_hex}, json=request_payload
            )

            # Raise exception if request failed
            response.raise_for_status()
