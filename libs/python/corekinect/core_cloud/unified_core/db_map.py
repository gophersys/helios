"""
Database schema mapping utilities for Core Cloud messages.

This module provides a type-safe abstraction layer for mapping domain model dataclasses
to database ORM models across multiple schema versions (V1_0 and V0_9). It handles:

- Per-field database column name translation using annotation metadata
- Schema-specific ORM model configuration
- Query time expressions for device timestamps
- Row-to-domain-object mapping

Key Components:
    - db_translation: Annotation class for marking database column mappings
    - RepositorySchemaConfig: Configuration for ORM repository access
    - message_mapper: Factory function that creates ORM-to-domain converters
"""

from dataclasses import dataclass, fields, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Sequence,
    Type,
    get_args,
    get_origin,
    Annotated,
    Literal,
    get_type_hints,
)

# Type aliases for schema and environment identifiers
Schema = Literal["V1_0", "V0_9"]
Env = Literal["DEV_1_0", "VAL_1_0", "PROD_1_0", "DEV_0_9", "VAL_0_9", "PROD_0_9"]

# Mapping from deployment environment names to their corresponding schema versions
SCHEMA_BY_ENV: Dict[Env, Schema] = {
    "DEV_1_0": "V1_0",
    "VAL_1_0": "V1_0",
    "PROD_1_0": "V1_0",
    "DEV_0_9": "V0_9",
    "VAL_0_9": "V0_9",
    "PROD_0_9": "V0_9",
}


class db_translation:
    """
    Annotation metadata for mapping dataclass fields to schema-specific ORM column names.

    This class is used with typing.Annotated to provide explicit per-schema database
    column name mappings. It allows a single domain dataclass to work across multiple
    database schemas where column naming conventions differ.

    The annotation supports multiple schemas in a single declaration, with each schema
    specifying its own column name.

    Attributes:
        by_schema (Dict[str, str]): Mapping from schema identifiers (e.g., "V1_0", "V0_9")
                                    to database column names for that schema.

    Example:
        ```python
        @dataclass
        class PositionMessage:
            # Maps to 'deviceid' in V1_0, 'DeviceId' in V0_9
            device_id: Annotated[int, db_translation(
                V1_0="deviceid",
                V0_9="DeviceId"
            )]

            # Maps to 'latitude' in both schemas (when names match, can use one)
            latitude: Annotated[float, db_translation(
                V1_0="latitude",
                V0_9="latitude"
            )]
        ```

    Usage Pattern:
        1. Apply to dataclass fields via Annotated type hints
        2. message_mapper() extracts these annotations during introspection
        3. The mapper uses the appropriate column name for the target schema
        4. Database rows are automatically mapped to domain objects

    Note:
        - If a schema is not specified in by_schema, the field name itself is used
        - Case sensitivity depends on the underlying database system
        - This is metadata only - it doesn't validate against actual database schemas
    """

    def __init__(self, **by_schema: str) -> None:
        """
        Initialize database column name mappings for multiple schemas.

        Args:
            **by_schema: Keyword arguments where keys are schema identifiers
                        (e.g., V1_0="deviceid", V0_9="DeviceId") and values
                        are the corresponding database column names.

        Example:
            db_translation(V1_0="timeofrecord", V0_9="TimeReceived")
        """
        self.by_schema = by_schema


@dataclass(frozen=True)
class RepositorySchemaConfig:
    """
    Configuration for database repository operations specific to a schema version.

    This immutable configuration object encapsulates all schema-specific details needed
    to query messages from the database. It provides:
    - The ORM model class to use for queries
    - Column accessor functions for common query filters (device ID, timestamps, record ID)
    - Device time expression builder for time-based queries
    - Timezone awareness settings for timestamp comparisons

    This configuration allows query logic to remain schema-agnostic by abstracting
    away the differences in column names and time handling between schema versions.

    Attributes:
        model (Any): The SQLAlchemy ORM model class for the target schema.
                    Example: Messagespositionv5tbl for V1_0 position messages.

        device_id_col (Callable[[Any], Any]): Function that takes an ORM model class
                                              and returns its device ID column accessor.
                                              Example: lambda M: M.deviceid

        server_time_col (Callable[[Any], Any]): Function that returns the server timestamp
                                                column (when the message was received).
                                                Example: lambda M: M.timeofrecord

        record_id_col (Callable[[Any], Any]): Function that returns the unique record ID
                                              column (primary key or auto-increment ID).
                                              Example: lambda M: M.recordid

        device_time_expr (Callable[[Any, Sequence[str] | str], Any]): Function that builds
                                                                       a SQLAlchemy expression
                                                                       for device time queries.
                                                                       Takes model and field name(s).

        device_time_fields (Sequence[str] | str): Field name(s) representing device timestamp.
                                                  Can be a single field like "timeoffix" or
                                                  multiple fields for composite timestamps.

        tz_aware_server_time (bool): Whether server timestamps in this schema include
                                    timezone information. V0_9 uses timezone-aware datetimes,
                                    V1_0 uses naive datetimes in UTC.

    Example:
        ```python
        # V1_0 configuration for position messages
        config = RepositorySchemaConfig(
            model=Messagespositionv5tbl,
            device_id_col=lambda M: M.deviceid,
            server_time_col=lambda M: M.timeofrecord,
            record_id_col=lambda M: M.recordid,
            device_time_expr=CoreCloudDBInterface.device_time_expr,
            device_time_fields="timeoffix",
            tz_aware_server_time=False  # V1_0 uses naive UTC timestamps
        )

        # Use in a query
        with CoreCloudDBInterface(db_env="VAL_1_0") as session:
            query = session.query(config.model).filter(
                config.device_id_col(config.model) == device_id
            )
        ```

    Thread Safety:
        This class is immutable (frozen=True) and thread-safe after construction.
    """

    model: Any
    device_id_col: Callable[[Any], Any]
    server_time_col: Callable[[Any], Any]
    record_id_col: Callable[[Any], Any]
    device_time_expr: Callable[[Any, Sequence[str] | str], Any]
    device_time_fields: Sequence[str] | str
    tz_aware_server_time: bool


def message_mapper(domain_type: Type[Any], schema: Schema):
    """
    Create a function that maps database ORM rows to domain dataclass instances.

    This factory function performs introspection on a domain dataclass to extract
    db_translation annotations, then returns a converter function that can transform
    ORM query results into strongly-typed domain objects. The converter handles:

    - Schema-specific column name resolution via db_translation metadata
    - Automatic attribute extraction from ORM row objects
    - Fallback to field names when no translation is specified
    - Graceful handling of missing columns (defaults to None)

    The returned function is optimized for repeated use - it pre-computes the field
    mappings during creation, so each row conversion is efficient.

    Args:
        domain_type (Type[Any]): The target dataclass type to convert rows into.
                                 Must be a valid dataclass with @dataclass decorator.
        schema (Schema): The schema version to use for column name resolution.
                        Must be one of: "V1_0" or "V0_9".

    Returns:
        Callable[[Any], Any]: A converter function that takes an ORM row object
                             and returns an instance of domain_type, or None if
                             the input row is None.

    Raises:
        TypeError: If domain_type is not a dataclass.

    Example:
        ```python
        @dataclass
        class DevicePosition:
            device_id: Annotated[int, db_translation(
                V1_0="deviceid",
                V0_9="DeviceId"
            )]
            latitude: Annotated[float, db_translation(
                V1_0="latitude",
                V0_9="latitude"
            )]
            timestamp: datetime  # No translation - uses field name as column name

        # Create a mapper for V1_0 schema
        convert_row = message_mapper(DevicePosition, "V1_0")

        # Use in a query
        with CoreCloudDBInterface(db_env="VAL_1_0") as session:
            rows = session.query(Messagespositionv5tbl).filter(...).all()
            positions = [convert_row(row) for row in rows]
            # positions is now a list of DevicePosition instances

        # The same dataclass works with V0_9 schema
        convert_row_v09 = message_mapper(DevicePosition, "V0_9")
        with CoreCloudDBInterface(db_env="VAL_0_9") as session:
            rows = session.query(PositionV6MsgTbl).filter(...).all()
            positions = [convert_row_v09(row) for row in rows]
        ```

    Implementation Details:
        - Uses get_type_hints() to extract Annotated metadata with proper forward refs
        - Searches metadata for db_translation instances
        - Builds a field-to-column mapping dictionary at creation time
        - The returned function performs attribute access and dataclass construction
        - Missing columns return None rather than raising AttributeError

    Performance:
        - Introspection cost is paid once at mapper creation
        - Each row conversion is a simple dictionary comprehension + constructor call
        - Suitable for converting thousands of rows efficiently
    """
    # Validate input is a dataclass
    if not is_dataclass(domain_type):
        raise TypeError(f"{domain_type!r} is not a dataclass")

    # Extract type hints including Annotated metadata (handles forward references)
    type_hints_with_metadata = get_type_hints(domain_type, include_extras=True)

    # Build mapping: dataclass field name -> database column name
    column_name_by_field: Dict[str, str] = {}

    for dataclass_field in fields(domain_type):
        field_name = dataclass_field.name
        field_type_annotation = type_hints_with_metadata.get(field_name, dataclass_field.type)

        # Default: use field name as column name (for fields without db_translation)
        resolved_column_name: Optional[str] = None

        # Check if this field uses Annotated[...]
        if get_origin(field_type_annotation) is Annotated:
            # Extract all metadata items (everything after the first type argument)
            metadata_items = get_args(field_type_annotation)[1:]

            # Search for db_translation metadata
            for metadata_obj in metadata_items:
                if isinstance(metadata_obj, db_translation):
                    # Look up the column name for the target schema
                    resolved_column_name = metadata_obj.by_schema.get(schema)
                    # Use first db_translation found (ignore duplicates)
                    break

        # Store the column name (or fall back to field name if no translation found)
        column_name_by_field[field_name] = resolved_column_name or field_name

    def from_row(orm_row: Any) -> Any:
        """
        Convert a single ORM row object to a domain dataclass instance.

        Args:
            orm_row: SQLAlchemy ORM row/model instance from a database query.
                    Can be None, in which case None is returned.

        Returns:
            An instance of the domain dataclass with fields populated from the row,
            or None if orm_row is None.
        """
        if orm_row is None:
            return None

        # Build constructor kwargs by extracting each field's value from the row
        constructor_kwargs = {
            field_name: getattr(orm_row, column_name_by_field[field_name], None)
            for field_name in (f.name for f in fields(domain_type))
        }

        # Construct and return the domain object
        return domain_type(**constructor_kwargs)  # type: ignore[call-arg]

    return from_row
