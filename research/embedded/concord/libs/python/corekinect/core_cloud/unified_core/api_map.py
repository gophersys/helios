from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, get_args, get_origin, Annotated


class api_translation:
    """
    Annotation class for explicit API field mapping.

    This class is used as metadata in type annotations to define how a dataclass field
    should be mapped to/from API JSON payloads. It provides explicit control over:
    - Field name translation between Python and API naming conventions
    - Type coercion/conversion rules
    - Required field validation
    - Field omission from API payloads

    Usage:
        Use this class with typing.Annotated to attach API metadata to dataclass fields:

        ```python
        @dataclass
        class MyMessage:
            temperature: Annotated[float, api_translation(
                api='temperatureCelsius',
                coerce=float,
                required=True,
                omit=False
            )]
        ```

    Attributes:
        api (str): The exact field name as it appears in the API JSON payload.
                   This is the key name used when serializing to/from JSON.
        coerce (type | None): Optional type to coerce the value to during conversion.
                              Common types: int, float, str, bool. If None, no coercion
                              is performed. Default: None.
        required (bool): Whether this field must be present in API payloads.
                        If True, validation will fail if the field is missing or None.
                        Default: False.
        omit (bool): Whether to exclude this field from outgoing API payloads.
                    Useful for fields that are read-only or computed locally.
                    Default: False.

    Example:
        ```python
        @dataclass
        class DeviceConfig:
            # Maps Python 'device_id' to API 'deviceId', always required
            device_id: Annotated[int, api_translation(
                api='deviceId',
                coerce=int,
                required=True
            )]

            # Optional temperature field with coercion to float
            temperature: Annotated[float, api_translation(
                api='tempCelsius',
                coerce=float,
                required=False
            )]

            # Local-only field not sent to API
            cached_timestamp: Annotated[datetime, api_translation(
                api='cachedTimestamp',
                omit=True
            )]
        ```
    """

    def __init__(self, *, api: str, coerce: type | None = None, required: bool = False, omit: bool = False):
        """
        Initialize API field translation metadata.

        Args:
            api (str): The API field name (JSON key) for this field.
            coerce (type | None): Type to coerce values to. None means no coercion.
            required (bool): If True, this field must have a non-None value.
            omit (bool): If True, this field is excluded from API payloads.
        """
        self.api = api
        self.coerce = coerce
        self.required = required
        self.omit = omit


class _ApiFieldSpec:
    """
    Internal specification object for a single dataclass field's API mapping.

    This class encapsulates all the information needed to convert a dataclass field
    to/from its API representation. It is an internal implementation detail extracted
    from api_translation annotations during dataclass introspection.

    Attributes:
        json (str): The JSON key name used in API payloads for this field.
        coerce (type | None): Optional type to coerce values to/from during conversion.
        required (bool): Whether this field is mandatory in API operations.
        omit (bool): Whether to exclude this field from outgoing API payloads.

    Note:
        This class is not intended for direct instantiation by users. It is created
        internally by extract_api_field_specs() when processing dataclass definitions.
    """

    def __init__(self, *, json: str, coerce: type | None, required: bool, omit: bool):
        """
        Initialize an API field specification.

        Args:
            json (str): The JSON key name for this field in API payloads.
            coerce (type | None): Type for value coercion. None means no coercion.
            required (bool): True if this field must be present and non-None.
            omit (bool): True if this field should not be included in API payloads.
        """
        self.json = json
        self.coerce = coerce
        self.required = required
        self.omit = omit


def extract_api_field_specs(dataclass_type: Type[Any]) -> Dict[str, _ApiFieldSpec]:
    """
    Extract API field specifications from a dataclass's type annotations.

    This function performs introspection on a dataclass to build a mapping of field names
    to their API specifications. It searches for api_translation() annotations within
    Annotated type hints and constructs _ApiFieldSpec objects containing the mapping rules.

    Only fields with explicit api_translation annotations are included in the result.
    Fields without annotations are silently skipped, allowing dataclasses to have both
    API-mapped fields and internal-only fields.

    Args:
        dataclass_type (Type[Any]): The dataclass type to introspect. Must be a valid
                                     dataclass decorated with @dataclass.

    Returns:
        Dict[str, _ApiFieldSpec]: A dictionary mapping Python field names (str) to their
                                  API specifications (_ApiFieldSpec objects). Only fields
                                  with api_translation annotations are included.

    Raises:
        TypeError: If the provided type is not a dataclass.

    Example:
        ```python
        @dataclass
        class SensorReading:
            # API-mapped field
            temperature: Annotated[float, api_translation(api='temp', required=True)]

            # Internal field without API mapping (will be skipped)
            cached_value: float

            # Another API-mapped field
            humidity: Annotated[int, api_translation(api='humidityPercent')]

        specs = extract_api_field_specs(SensorReading)
        # Result: {
        #   'temperature': _ApiFieldSpec(json='temp', coerce=None, required=True, omit=False),
        #   'humidity': _ApiFieldSpec(json='humidityPercent', coerce=None, required=False, omit=False)
        # }
        # Note: 'cached_value' is not in specs because it lacks api_translation
        ```

    Implementation Notes:
        - Uses dataclasses.fields() to iterate over all fields in the dataclass
        - Checks each field's type annotation for Annotated[...] wrappers
        - Extracts metadata from Annotated to find api_translation instances
        - Builds _ApiFieldSpec objects from the extracted metadata
        - Silently ignores fields without api_translation (not an error)
    """
    # Validate that we're working with a dataclass
    if not is_dataclass(dataclass_type):
        raise TypeError(f"{dataclass_type!r} is not a dataclass")

    # Dictionary to accumulate field specifications
    field_specs: Dict[str, _ApiFieldSpec] = {}

    # Iterate over all fields defined in the dataclass
    for field in fields(dataclass_type):
        field_type_annotation = field.type

        # Initialize variables to collect API mapping metadata
        api_json_name: Optional[str] = None
        coercion_type: type | None = None
        is_required = False
        should_omit = False

        # Check if the field uses Annotated[...] type hint
        if get_origin(field_type_annotation) is Annotated:
            # Extract metadata objects from Annotated (everything after the first type arg)
            metadata_objects = get_args(field_type_annotation)[1:]

            # Search through metadata for api_translation instances
            for metadata_item in metadata_objects:
                if isinstance(metadata_item, api_translation):
                    # Found API translation metadata - extract all attributes
                    api_json_name = metadata_item.api
                    coercion_type = metadata_item.coerce
                    is_required = metadata_item.required
                    should_omit = metadata_item.omit
                    # Only use the first api_translation found (in case of duplicates)
                    break

        # Only include fields that have explicit API mapping
        if api_json_name is None:
            # This field doesn't have api_translation metadata
            # It's either a DB-only field or an internal field - skip it silently
            continue

        # Create the specification object and add to results
        field_specs[field.name] = _ApiFieldSpec(
            json=api_json_name, coerce=coercion_type, required=is_required, omit=should_omit
        )

    return field_specs
