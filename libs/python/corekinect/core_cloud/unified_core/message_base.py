"""
Message base classes for database query operations.

This module provides a generic message base class that adds Active Record-style
query methods to message dataclasses. It enables domain objects to query themselves
from the database without requiring separate repository classes.

Key Features:
    - Schema-agnostic queries via environment configuration
    - Automatic ORM-to-domain object mapping
    - Type-safe return values with Generic support
    - Cached message readers for performance
"""

from datetime import datetime
from typing import Iterable, Optional, Protocol, Type, Any, TypeVar, Generic, Dict, List

from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from .db_map import Env, Schema, SCHEMA_BY_ENV, RepositorySchemaConfig
from .db_query import DbQueryBase

# Needed for generic typing
TMsg = TypeVar("TMsg", bound="MessageBase")


class MessageReaderProtocol(Protocol):
    """
    Protocol defining the interface for database query operations.

    This protocol specifies the contract that all message readers must fulfill,
    enabling polymorphic query operations across different message types and schemas.

    Methods:
        last: Retrieve the most recent message for a device.
        since_server_time: Query messages by server receipt timestamp.
        since_device_time: Query messages by device-recorded timestamp.
        since_record_id: Query messages by database record ID.
    """

    def last(self, dut_id: int) -> Optional[Any]: ...

    def since_server_time(
        self, dut_id: int, start_time: datetime, end_time: datetime | None = None
    ) -> Iterable[Any]: ...

    def since_device_time(
        self, dut_id: int, start_time: datetime, end_time: datetime | None = None
    ) -> Iterable[Any]: ...

    def since_record_id(self, dut_id: int, start_id: int, end_id: int | None = None) -> Iterable[Any]: ...

    def since_server_time_multi(
        self, dut_ids: Iterable[int], start_time: datetime, end_time: datetime | None = None
    ) -> dict[int, list[Any]]: ...

    def since_device_time_multi(
        self, dut_ids: Iterable[int], start_time: datetime, end_time: datetime | None = None
    ) -> dict[int, list[Any]]: ...

    def since_record_id_multi(
        self, dut_ids: Iterable[int], start_id: int, end_id: int | None = None
    ) -> dict[int, list[Any]]: ...


# Global cache: (message_class, environment) -> MessageReaderProtocol instance
# This cache improves performance by avoiding repeated schema configuration lookups
_MESSAGE_READERS: dict[tuple[type, Env], MessageReaderProtocol] = {}


def _default_schema_config_for(message_class: Type[Any], environment: Env) -> RepositorySchemaConfig:
    """
    Build a default schema configuration for a message class in a specific environment.

    This function introspects a message class to extract its schema mapping metadata
    and constructs a RepositorySchemaConfig with the appropriate ORM model and
    column accessors for the target environment's schema version.

    Args:
        message_class: The message dataclass type to configure. Must have a _schema
                      class variable mapping Schema versions to ORM models.
        environment: The deployment environment identifier (e.g., "VAL_1_0", "DEV_0_9").

    Returns:
        A fully configured RepositorySchemaConfig ready for database queries.

    Raises:
        ValueError: If the message class lacks a _schema mapping for the target schema.

    Example:
        ```python
        config = _default_schema_config_for(PositionMsgV6, "VAL_1_0")
        # Result: RepositorySchemaConfig with V1_0 ORM model and column accessors
        ```

    Notes:
        - V1_0 schemas use lowercase column names (e.g., "deviceid", "timeofrecord")
        - V0_9 schemas use PascalCase column names (e.g., "DeviceId", "TimeReceived")
        - V1_0 uses naive UTC timestamps; V0_9 uses timezone-aware timestamps
        - Device time fields can be customized via the class's device_time_fields attribute
    """
    # Determine which schema version this environment uses
    schema_version: Schema = SCHEMA_BY_ENV[environment]

    # Extract the schema-to-ORM-model mapping from the message class
    schema_mapping: dict[str, Any] = getattr(message_class, "_schema", None)
    if not schema_mapping or schema_version not in schema_mapping:
        raise ValueError(
            f"{message_class.__name__}: missing _schema mapping for schema version {schema_version}. "
            f"Please define a _schema class variable with a {schema_version} entry."
        )

    # Get the ORM model for this schema version
    orm_model = schema_mapping[schema_version]

    # Configure schema-specific column names and settings
    if schema_version == "V1_0":
        # V1_0 uses lowercase column names and naive UTC timestamps
        device_id_column_accessor = lambda Model: getattr(Model, "deviceid")
        server_time_column_accessor = lambda Model: getattr(Model, "timeofrecord")
        record_id_column_accessor = lambda Model: getattr(Model, "recordid")
        use_timezone_aware_timestamps = False
        device_time_field_names = getattr(message_class, "_device_time_fields", "timeoffix")
    else:
        # V0_9 uses PascalCase column names and timezone-aware timestamps
        device_id_column_accessor = lambda Model: getattr(Model, "DeviceId")
        server_time_column_accessor = lambda Model: getattr(Model, "TimeReceived")
        record_id_column_accessor = lambda Model: getattr(Model, "CheckinId")
        use_timezone_aware_timestamps = True
        device_time_field_names = getattr(message_class, "_device_time_fields", "TimeOfFix")

    # Build and return the configuration object
    return RepositorySchemaConfig(
        model=orm_model,
        device_id_col=device_id_column_accessor,
        server_time_col=server_time_column_accessor,
        record_id_col=record_id_column_accessor,
        device_time_expr=CoreCloudDBInterface.device_time_expr,
        device_time_fields=device_time_field_names,
        tz_aware_server_time=use_timezone_aware_timestamps,
    )


def _get_message_reader(message_class: Type[Any], environment: Env) -> MessageReaderProtocol:
    """
    Get or create a cached message reader for a specific message class and environment.

    This function implements a singleton pattern for message readers, ensuring that
    each (message_class, environment) combination has only one reader instance. This
    improves performance by avoiding repeated configuration overhead.

    Args:
        message_class: The message dataclass type to create a reader for.
        environment: The deployment environment identifier.

    Returns:
        A MessageReaderProtocol implementation configured for the specified
        message class and environment.

    Example:
        ```python
        # First call creates and caches the reader
        reader1 = _get_message_reader(PositionMsgV6, "VAL_1_0")

        # Second call returns the cached instance
        reader2 = _get_message_reader(PositionMsgV6, "VAL_1_0")

        assert reader1 is reader2  # Same object
        ```

    Thread Safety:
        This function is NOT thread-safe. If used in a multi-threaded environment,
        external synchronization is required to prevent race conditions during
        cache initialization.
    """
    # Create a unique cache key from the class and environment
    cache_key = (message_class, environment)

    # Check if we already have a reader for this combination
    cached_reader = _MESSAGE_READERS.get(cache_key)
    if cached_reader:
        return cached_reader

    # Create a new reader with default configuration
    schema_config = _default_schema_config_for(message_class, environment)
    new_reader = DbQueryBase(message_type=message_class, env=environment, schema_cfg=schema_config)

    # Cache for future use
    _MESSAGE_READERS[cache_key] = new_reader

    return new_reader


class MessageBase(Generic[TMsg]):
    """
    Base class that adds Active Record-style database query methods to message dataclasses.

    This mixin class enables message dataclasses to query themselves from the database
    without requiring separate repository classes. It provides a clean, type-safe API
    for common query operations like fetching the latest message or querying by time range.

    Usage Pattern:
        1. Define a message dataclass with db_translation annotations
        2. Add a _schema class variable mapping Schema versions to ORM models
        3. Inherit from MessageBase[YourMessageClass] for type safety
        4. Use the class methods to query the database

    Type Safety:
        The Generic[TMsg] parameter enables IDE autocomplete and type checking for
        query results. When you inherit as MessageBase[PositionMsgV6], all query
        methods will return PositionMsgV6 instances.

    Example:
        ```python
        from dataclasses import dataclass
        from typing import Annotated

        @dataclass
        class PositionMsgV6(MessageBase["PositionMsgV6"]):
            device_id: Annotated[int, db_translation(
                V1_0="deviceid",
                V0_9="DeviceId"
            )]
            latitude: float
            longitude: float

            # Map schema versions to ORM models
            _schema = {
                "V1_0": Messagespositionv5tbl,
                "V0_9": PositionV6MsgTbl
            }

        # Query the latest position
        latest = PositionMsgV6.get_last(
            dut_id=0x70B3D584C01E1445,
            env="VAL_1_0"
        )

        # Query positions in a time range
        positions = PositionMsgV6.get_since_server_time(
            dut_id=0x70B3D584C01E1445,
            start=datetime(2025, 1, 1),
            end=datetime(2025, 1, 31),
            env="VAL_1_0"
        )
        ```

    Class Methods:
        get_last: Retrieve the most recent message for a device.
        get_since_server_time: Query messages by server receipt timestamp.
        get_since_device_time: Query messages by device-recorded timestamp.
        get_since_record_id: Query messages by database record ID.

    Requirements:
        Subclasses must define:
        - _schema: ClassVar[dict[Schema, Type]] mapping schema versions to ORM models
        - db_translation annotations on fields for column name mapping
    """

    @classmethod
    def get_last(cls: Type[TMsg], *, dut_id: int, env: Env = "VAL_1_0") -> Optional[TMsg]:
        """
        Retrieve the most recent message record for a specific device.

        This method queries for the latest message by sorting on the record ID
        in descending order and returning the first result. Record IDs are typically
        auto-incrementing primary keys, making them a reliable chronological ordering.

        Args:
            dut_id: Device unique identifier. Typically a 64-bit integer representing
                   the device's hardware ID (e.g., 0x70B3D584C01E1445).
            env: Deployment environment identifier. Determines which database and schema
                version to query. Valid options: "DEV_1_0", "VAL_1_0", "PROD_1_0",
                "DEV_0_9", "VAL_0_9", "PROD_0_9". Default: "VAL_1_0".

        Returns:
            The most recent message instance for the device, or None if no records
            exist in the database.
        """
        message_reader = _get_message_reader(cls, env)
        query_result = message_reader.last(dut_id)
        return query_result  # type: ignore[return-value]

    @classmethod
    def since_server_time(
        cls: Type[TMsg], *, dut_id: int, start_time: datetime, end_time: datetime | None = None, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages received by the server within a specific time range.

        This method queries records based on when the server received them (the server
        timestamp), not when the device recorded them. This is useful for analyzing
        communication patterns, troubleshooting connectivity issues, or auditing
        data arrival times.

        The time range is exclusive of the start time and inclusive of the end time:
        - Messages received AFTER start are included
        - Messages received ON OR BEFORE end are included

        Args:
            dut_id: Device unique identifier.
            start_time: Starting timestamp (exclusive). Messages received after this time
                  are included in results.
            end_time: Optional ending timestamp (inclusive). Messages received on or before
                this time are included. If None, no upper bound is applied.
            env: Deployment environment identifier. Default: "VAL_1_0".

        Returns:
            A list of message instances within the specified time range. Returns an
            empty list if no messages match the criteria.
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_server_time(dut_id, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_device_time(
        cls: Type[TMsg], dut_id: int, start_time: datetime, end_time: datetime | None = None, *, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages based on device-recorded timestamps (not server receipt times).

        This method queries records using the timestamp from the device itself (e.g.,
        GPS fix time for position messages, event time for sensor readings). This is
        useful for analyzing events based on when they actually occurred on the device,
        rather than when the server received them.

        The time range follows the same convention as get_since_server_time:
        - Exclusive of start time (messages recorded AFTER start)
        - Inclusive of end time (messages recorded ON OR BEFORE end)

        Args:
            dut_id: Device unique identifier.
            start_time: Starting device timestamp (exclusive). Messages recorded after
                  this time are included.
            end_time: Optional ending device timestamp (inclusive). Messages recorded on
                or before this time are included. If None, no upper bound is applied.
            env: Deployment environment identifier. Default: "VAL_1_0".

        Returns:
            A list of message instances within the device time range. Returns an
            empty list if no messages match the criteria.
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_device_time(dut_id, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_record_id(
        cls: Type[TMsg], *, dut_id: int, start_id: int, end_id: int | None = None, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages based on database record IDs (primary keys).

        This method is useful for pagination, resumable queries, or processing messages
        in batches. Record IDs are typically auto-incrementing database primary keys
        that guarantee chronological ordering within a table.

        The ID range is exclusive of the start ID and inclusive of the end ID:
        - Messages with record IDs GREATER than start_id are included
        - Messages with record IDs LESS THAN OR EQUAL to end_id are included

        Args:
            dut_id: Device unique identifier.
            start_id: Starting record ID (exclusive). Messages with record IDs greater
                     than this value are included.
            end_id: Optional ending record ID (inclusive). Messages with record IDs
                   less than or equal to this value are included. If None, no upper
                   bound is applied.
            env: Deployment environment identifier. Default: "VAL_1_0".

        Returns:
            A list of message instances within the record ID range, ordered by record ID.
            Returns an empty list if no messages match.
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_record_id(dut_id, start_id, end_id)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_server_time_multi(
        cls: Type[TMsg],
        dut_ids: Iterable[int],
        start_time: datetime,
        end_time: datetime | None = None,
        *,
        env: Env = "VAL_1_0",
    ) -> List[TMsg]:
        """
        Multi-device variant of since_server_time.

        Returns:
            { device_id: [messages...] }
        """
        reader = _get_message_reader(cls, env)
        query_results = reader.since_server_time_multi(dut_ids, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_device_time_multi(
        cls: Type[TMsg],
        dut_ids: Iterable[int],
        start_time: datetime,
        end_time: datetime | None = None,
        *,
        env: Env = "VAL_1_0",
    ) -> List[TMsg]:
        """
        Multi-device variant of since_device_time.

        Returns:
            { device_id: [messages...] }
        """
        reader = _get_message_reader(cls, env)
        query_results = reader.since_device_time_multi(dut_ids, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_record_id_multi(
        cls: Type[TMsg],
        *,
        dut_ids: Iterable[int],
        start_id: int,
        end_id: int | None = None,
        env: Env = "VAL_1_0",
    ) -> List[TMsg]:
        """
        Multi-device variant of since_record_id.

        Returns:
            { device_id: [messages...] }
        """
        reader = _get_message_reader(cls, env)
        query_results = reader.since_record_id_multi(dut_ids, start_id, end_id)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def _get_reason_from_mapping(cls, value: Optional[int], mapping: Dict[int, str]) -> str:
        """Get the reason string from a bit mask value."""
        if value is None:
            return "No value provided"
        return mapping.get(value, f"Unknown: {value}")
