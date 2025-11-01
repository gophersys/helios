from datetime import datetime, timezone
from typing import Iterable, Optional, Type, Any

from .db_map import Env, Schema, SCHEMA_BY_ENV, RepositorySchemaConfig, message_mapper
from corekinect.core_cloud.db_interface import CoreCloudDBInterface


class DbQueryBase:
    """
    Schema-aware database query helper for reading messages from Core Cloud databases.

    This class provides a unified interface for querying message records across different
    database schema versions (V1_0 and V0_9). It abstracts away schema-specific differences
    in column names, timestamp handling, and ORM models.

    The query results are automatically mapped to domain dataclass instances using the
    schema-aware message_mapper system.

    Typical Usage:
        ```python
        # Create a query helper for PositionMsgV6 in the VAL_1_0 environment
        query = DbQueryBase(
            message_type=PositionMsgV6,
            env="VAL_1_0",
            schema_cfg=my_schema_config
        )

        # Get the most recent message for a device
        latest = query.last(dut_id=0x70B3D584C01E1445)

        # Get messages within a time range
        messages = query.since_server_time(
            dut_id=0x70B3D584C01E1445,
            start=datetime(2025, 1, 1),
            end=datetime(2025, 1, 31)
        )
        ```

    Attributes:
        _message_type (Type[Any]): The domain message dataclass type to instantiate from query results.
        _env (Env): The deployment environment identifier (e.g., "VAL_1_0", "DEV_0_9").
        _schema (Schema): The database schema version derived from the environment.
        _cfg (RepositorySchemaConfig): Configuration object containing schema-specific ORM details.
        _from_row (Callable): Function that converts ORM row objects to domain message instances.
    """

    def __init__(self, message_type: Type[Any], env: Env, schema_cfg: RepositorySchemaConfig):
        """
        Initialize a database query helper for a specific message type and environment.

        Args:
            message_type (Type[Any]): Domain dataclass type representing the message structure.
                                     Must have db_translation annotations for schema mapping.
            env (Env): Deployment environment identifier. Determines which database and
                      schema version to query. Valid values: "DEV_1_0", "VAL_1_0",
                      "PROD_1_0", "DEV_0_9", "VAL_0_9", "PROD_0_9".
            schema_cfg (RepositorySchemaConfig): Schema-specific configuration including
                                                 the ORM model and column accessor functions.
        """
        self._message_type = message_type
        self._env = env
        self._schema: Schema = SCHEMA_BY_ENV[env]
        self._cfg = schema_cfg

        # Create a converter function that maps ORM rows to domain objects
        # This is cached here to avoid repeated introspection overhead
        self._from_row = message_mapper(message_type, self._schema)

    def last(self, dut_id: int) -> Optional[Any]:
        """
        Retrieve the most recent message record for a specific device.

        This method queries for the latest record by sorting on the record ID in
        descending order and returning the first result.

        Args:
            dut_id (int): Device unique identifier. Typically a 64-bit integer
                         (e.g., 0x70B3D584C01E1445).

        Returns:
            Optional[Any]: The most recent message instance for the device, or None if
                          no records exist. The return type is the message_type provided
                          during initialization.

        Example:
            ```python
            query = DbQueryBase(PositionMsgV6, "VAL_1_0", config)
            latest_position = query.last(dut_id=0x70B3D584C01E1445)
            if latest_position:
                print(f"Last known position: {latest_position.latitude}, {latest_position.longitude}")
            ```
        """
        # Extract ORM model and configuration for this schema
        orm_model = self._cfg.model
        config = self._cfg

        # Open a database session using context manager (auto-cleanup)
        with CoreCloudDBInterface(db_env=self._env) as session:
            # Query: filter by device ID, order by record ID descending, take first
            result_row = (
                session.query(orm_model)
                .filter(config.device_id_col(orm_model) == dut_id)
                .order_by(config.record_id_col(orm_model).desc())
                .first()
            )

            # Convert ORM row to domain object (None if no results)
            return self._from_row(result_row) if result_row else None

    def since_server_time(self, dut_id: int, start: datetime, end: datetime | None = None) -> Iterable[Any]:
        """
        Retrieve messages received by the server after a specific timestamp.

        This method queries records based on when the server received them (not when
        the device recorded them). The time range is exclusive of the start time and
        inclusive of the end time.

        Timezone handling:
        - V1_0 schemas use naive UTC datetimes (timezone info is stripped)
        - V0_9 schemas use timezone-aware datetimes (converted to UTC if needed)

        Args:
            dut_id (int): Device unique identifier.
            start (datetime): Starting timestamp (exclusive). Messages received AFTER
                             this time are included in results.
            end (datetime | None): Optional ending timestamp (inclusive). Messages received
                                  ON OR BEFORE this time are included. If None, no upper
                                  bound is applied.

        Returns:
            Iterable[Any]: List of message instances within the time range, in the order
                          returned by the database (typically chronological by record ID).

        Example:
            ```python
            from datetime import datetime, timezone

            query = DbQueryBase(PositionMsgV6, "VAL_1_0", config)

            # Get all messages from January 2025
            messages = query.since_server_time(
                dut_id=0x70B3D584C01E1445,
                start=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end=datetime(2025, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
            )
            print(f"Found {len(messages)} messages in January")
            ```
        """
        orm_model = self._cfg.model
        config = self._cfg

        with CoreCloudDBInterface(db_env=self._env) as session:
            # Get the server timestamp column accessor
            server_time_column = config.server_time_col(orm_model)

            # Adjust start time based on schema's timezone awareness
            start_time_adjusted = start.astimezone(timezone.utc) if config.tz_aware_server_time else start

            # Build base query: filter by device ID and start time (exclusive)
            query = session.query(orm_model).filter(
                config.device_id_col(orm_model) == dut_id, server_time_column > start_time_adjusted
            )

            # Add optional end time filter (inclusive)
            if end:
                end_time_adjusted = end.astimezone(timezone.utc) if config.tz_aware_server_time else end
                query = query.filter(server_time_column <= end_time_adjusted)

            # Execute query and convert all results to domain objects
            result_rows = query.all()
            return [self._from_row(row) for row in result_rows]

    def since_device_time(self, dut_id: int, start: datetime, end: datetime | None = None) -> Iterable[Any]:
        """
        Retrieve messages based on device-recorded timestamps (not server receipt times).

        This method queries records using the timestamp from the device itself (e.g., GPS
        fix time for position messages). This is useful for analyzing events based on when
        they actually occurred on the device, rather than when the server received them.

        The device time expression is built by the schema config's device_time_expr function,
        which can handle both simple single-field timestamps and composite timestamps.

        Args:
            dut_id (int): Device unique identifier.
            start (datetime): Starting device timestamp (exclusive). Messages recorded AFTER
                             this time are included.
            end (datetime | None): Optional ending device timestamp (inclusive). Messages
                                  recorded ON OR BEFORE this time are included. If None,
                                  no upper bound is applied.

        Returns:
            Iterable[Any]: List of message instances within the device time range.

        Example:
            ```python
            from datetime import datetime, timezone

            query = DbQueryBase(PositionMsgV6, "VAL_1_0", config)

            # Get positions recorded by device during a specific window
            positions = query.since_device_time(
                dut_id=0x70B3D584C01E1445,
                start=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 15, 18, 0, tzinfo=timezone.utc)
            )
            print(f"Device recorded {len(positions)} positions in that 6-hour window")
            ```

        Note:
            Device timestamps may not be reliable if the device's clock is not synchronized
            or if GPS time is unavailable. Consider using since_server_time() for
            mission-critical time-based queries.
        """
        orm_model = self._cfg.model
        config = self._cfg

        with CoreCloudDBInterface(db_env=self._env) as session:
            # Build device time expression (handles both simple and composite timestamps)
            device_time_expression = config.device_time_expr(orm_model, config.device_time_fields)

            # Adjust start time based on schema's timezone awareness
            start_time_adjusted = start.astimezone(timezone.utc) if config.tz_aware_server_time else start

            # Build base query: filter by device ID and device start time (exclusive)
            query = session.query(orm_model).filter(
                config.device_id_col(orm_model) == dut_id, device_time_expression > start_time_adjusted
            )

            # Add optional end time filter (inclusive)
            if end:
                end_time_adjusted = end.astimezone(timezone.utc) if config.tz_aware_server_time else end
                query = query.filter(device_time_expression <= end_time_adjusted)

            # Execute query and convert all results to domain objects
            result_rows = query.all()
            return [self._from_row(row) for row in result_rows]

    def since_record_id(self, dut_id: int, start_id: int, end_id: int | None = None) -> Iterable[Any]:
        """
        Retrieve messages based on database record IDs (primary keys).

        This method is useful for pagination or resumable queries. Record IDs are typically
        auto-incrementing database primary keys that guarantee ordering. This allows efficient
        "give me the next N records after ID X" queries.

        Args:
            dut_id (int): Device unique identifier.
            start_id (int): Starting record ID (exclusive). Messages with record IDs GREATER
                           than this value are included.
            end_id (int | None): Optional ending record ID (inclusive). Messages with record
                                IDs LESS THAN OR EQUAL to this value are included. If None,
                                no upper bound is applied.

        Returns:
            Iterable[Any]: List of message instances within the record ID range, ordered
                          by record ID (typically chronological).

        Example:
            ```python
            query = DbQueryBase(PositionMsgV6, "VAL_1_0", config)

            # Process messages in batches of 100 for a specific device
            batch_size = 100
            last_id = 0

            while True:
                batch = query.since_record_id(
                    dut_id=0x70B3D584C01E1445,
                    start_id=last_id,
                    end_id=last_id + batch_size
                )

                if not batch:
                    break  # No more records

                # Process the batch
                for msg in batch:
                    process_message(msg)

                # Update for next iteration
                last_id += batch_size
            ```

        Note:
            Record IDs may have gaps (deleted records, different message types sharing
            the table, etc.). This method guarantees ordering but not contiguous IDs.
        """
        orm_model = self._cfg.model
        config = self._cfg

        with CoreCloudDBInterface(db_env=self._env) as session:
            # Get the record ID column accessor
            record_id_column = config.record_id_col(orm_model)

            # Build base query: filter by device ID and record ID range (start exclusive)
            query = session.query(orm_model).filter(
                config.device_id_col(orm_model) == dut_id, record_id_column > start_id
            )

            # Add optional end ID filter (inclusive)
            if end_id is not None:
                query = query.filter(record_id_column <= end_id)

            # Execute query and convert all results to domain objects
            result_rows = query.all()
            return [self._from_row(row) for row in result_rows]
