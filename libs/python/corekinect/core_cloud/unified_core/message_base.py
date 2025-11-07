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
from typing import Iterable, Optional, Protocol, Type, Any, TypeVar, Generic, Dict

from .db_map import Env, Schema, SCHEMA_BY_ENV, RepositorySchemaConfig
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from .db_query import DbQueryBase

# Type variable bound to MessageBase for generic typing
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

        Example:
            ```python
            # Get the latest position message from validation environment
            latest_position = PositionMsgV6.get_last(
                dut_id=0x70B3D584C01E1445,
                env="VAL_1_0"
            )

            if latest_position:
                print(f"Last known location: {latest_position.latitude}, {latest_position.longitude}")
                print(f"Recorded at: {latest_position.time_of_fix}")
            else:
                print("No position messages found for this device")
            ```

        Performance:
            - Uses an index on (device_id, record_id) for efficient queries
            - Returns only one row, so very fast even for devices with many messages
        """
        message_reader = _get_message_reader(cls, env)
        query_result = message_reader.last(dut_id)
        return query_result  # type: ignore[return-value]

    @classmethod
    def since_server_time(
        cls: Type[TMsg], *, dut_id: int, start_time: datetime, end_time: datetime | None = None, env: Env = "VAL_1_0"
    ) -> list[TMsg]:
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

        Example:
            ```python
            from datetime import datetime, timezone

            # Query all positions received in January 2025
            positions = PositionMsgV6.get_since_server_time(
                dut_id=0x70B3D584C01E1445,
                start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
                env="VAL_1_0"
            )

            print(f"Device sent {len(positions)} positions in January")

            # Analyze communication delays
            for pos in positions:
                delay = pos.time_of_record - pos.time_of_fix
                print(f"Message delay: {delay.total_seconds()} seconds")
            ```

        Timezone Handling:
            - V1_0 schemas: Timestamps are stored as naive UTC. If you pass a
              timezone-aware datetime, the timezone info is stripped and the time
              is treated as UTC.
            - V0_9 schemas: Timestamps are timezone-aware. If you pass a naive
              datetime, it's assumed to be UTC and converted to timezone-aware.

        Performance:
            - Uses an index on (device_id, server_time) for efficient range queries
            - Can return large result sets; consider adding an end time for queries
              spanning long periods
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_server_time(dut_id, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_device_time(
        cls: Type[TMsg], *, dut_id: int, start_time: datetime, end_time: datetime | None = None, env: Env = "VAL_1_0"
    ) -> list[TMsg]:
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

        Example:
            ```python
            from datetime import datetime, timezone

            # Get all positions recorded by device during a mission window
            mission_start = datetime(2025, 1, 15, 8, 0, tzinfo=timezone.utc)
            mission_end = datetime(2025, 1, 15, 16, 30, tzinfo=timezone.utc)

            positions = PositionMsgV6.get_since_device_time(
                dut_id=0x70B3D584C01E1445,
                start_time=mission_start,
                end_time=mission_end,
                env="VAL_1_0"
            )

            print(f"Device recorded {len(positions)} positions during mission")

            # Analyze movement during the mission
            for i, pos in enumerate(positions):
                print(f"Position {i+1} at {pos.time_of_fix}: "
                      f"({pos.latitude}, {pos.longitude})")
            ```

        Device Time Fields:
            The device time is determined by the message class's device_time_fields
            attribute. This can be:
            - A single field name (e.g., "timeoffix" for position messages)
            - Multiple field names for composite timestamps
            - Defaults: "timeoffix" (V1_0), "TimeOfFix" (V0_9)

        Important Notes:
            - Device timestamps may not be reliable if:
              * The device's clock is not synchronized
              * GPS time is unavailable (no fix)
              * The device's RTC battery is dead
            - Consider using get_since_server_time() for mission-critical queries
              where timestamp reliability is paramount
            - Device time may be in the future if the device clock is ahead

        Performance:
            - Performance depends on whether device time fields are indexed
            - May be slower than server time queries for large datasets
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_device_time(dut_id, start_time, end_time)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def since_record_id(
        cls: Type[TMsg], *, dut_id: int, start_id: int, end_id: int | None = None, env: Env = "VAL_1_0"
    ) -> list[TMsg]:
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
            A list of message instances within the record ID range, ordered by record ID
            (typically chronological). Returns an empty list if no messages match.

        Example - Batch Processing:
            ```python
            # Process all messages for a device in batches of 100
            batch_size = 100
            last_processed_id = 0

            while True:
                batch = PositionMsgV6.get_since_record_id(
                    dut_id=0x70B3D584C01E1445,
                    start_id=last_processed_id,
                    end_id=last_processed_id + batch_size,
                    env="VAL_1_0"
                )

                if not batch:
                    break  # No more messages to process

                # Process the batch
                for msg in batch:
                    analyze_position(msg)

                # Update for next iteration
                last_processed_id = batch[-1].record_id
            ```

        Example - Resumable Processing:
            ```python
            # Save progress and resume later
            def process_messages(device_id, checkpoint_file):
                # Load last processed ID from checkpoint
                with open(checkpoint_file, 'r') as f:
                    last_id = int(f.read().strip() or '0')

                # Get next batch of messages
                messages = PositionMsgV6.get_since_record_id(
                    dut_id=device_id,
                    start_id=last_id,
                    env="VAL_1_0"
                )

                # Process messages
                for msg in messages:
                    process(msg)

                    # Save checkpoint after each message
                    with open(checkpoint_file, 'w') as f:
                        f.write(str(msg.record_id))
            ```

        Important Notes:
            - Record IDs may have gaps due to:
              * Deleted records
              * Different message types sharing the same table
              * Database operations that don't use auto-increment
            - This method guarantees ordering but NOT contiguous IDs
            - Record IDs are database-specific and not portable across environments
            - Never assume specific record ID values or ranges

        Performance:
            - Very efficient for batch processing (uses indexed primary key lookups)
            - Ideal for paginated queries or streaming large datasets
            - Faster than time-based queries for sequential access patterns
        """
        message_reader = _get_message_reader(cls, env)
        query_results = message_reader.since_record_id(dut_id, start_id, end_id)
        return list(query_results)  # type: ignore[return-value]

    @classmethod
    def _get_reason_from_mapping(cls, value: Optional[int], mapping: Dict[int, str]) -> str:
        """Get the reason string from a bit mask value."""
        if value is None:
            return "No value provided"
        return mapping.get(value, f"Unknown: {value}")
