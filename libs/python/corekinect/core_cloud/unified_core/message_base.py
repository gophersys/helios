import csv
from dataclasses import fields
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Type,
    TypeVar,
    Annotated,
    get_args,
    get_origin,
    get_type_hints,
)

from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.utils import Logger
from corekinect.utils.serde import convert_str_to_type
from corekinect.utils.timeutil.tzutils import dt_to_utc
from .db_map import Env, Schema, SCHEMA_BY_ENV, RepositorySchemaConfig, message_mapper, db_translation

# Needed for generic typing
TMsg = TypeVar("TMsg", bound="MessageBase")


class MessageBase(Generic[TMsg]):
    """
    Base class that adds Active Record-style database query methods to message dataclasses.


    Public API Methods:
        last:
            Retrieve the most recent message for a device.
        since_server_time:
            Query messages for a single device using server-receipt timestamps.
        since_device_time:
            Query messages for a single device using device-recorded timestamps.
        since_record_id:
            Query messages for a single device using database record ID ranges.
        since_server_time_multi:
            Query messages by server-receipt timestamp for multiple device IDs.
        since_device_time_multi:
            Query messages by device-recorded timestamp for multiple device IDs.
        since_record_id_multi:
            Query messages by record ID for multiple device IDs.

    Message Implementer API:
        _get_reason_from_mapping:
            Utility for mapping integer reason codes to human-readable strings.
            Intended for subclasses defining reason/enum tables.

    Requirements for Subclasses:
        Must define a class variable `_schema` mapping:
                  { "V1_0": <ORM model>, "V0_9": <ORM model or None> }
        Should define `_device_time_fields` mapping:
              { "V1_0": "<column_name>", "V0_9": "<column_name>" }
          This identifies the device-recorded timestamp column for each schema.
        Message fields must use `db_translation` annotations to map
          dataclass attributes to the appropriate database column names.

    """

    # Subclasses set these:
    _schema: ClassVar[Dict[Schema, Any]] = None
    _device_time_fields: ClassVar[Dict[Schema, Any]] = None

    # --------------------------------------------------|  Schema config stuff, cached for less overhead on MTIB  |----------
    @classmethod
    @lru_cache(maxsize=64)
    def _schema_config(cls, env: Env) -> RepositorySchemaConfig:
        schema_version: Schema = SCHEMA_BY_ENV[env]
        schema_mapping = cls._schema

        if not schema_mapping or schema_version not in schema_mapping:
            raise ValueError(f"{cls.__name__}: missing schema {schema_mapping=} for {schema_version=}")

        # Get the ORM model for this schema version
        orm_model = schema_mapping[schema_version]

        # Configure schema-specific column names and settings
        if schema_version == "V1_0":
            device_id_column_accessor = lambda Model: getattr(Model, "deviceid")
            server_time_column_accessor = lambda Model: getattr(Model, "timeofrecord")
            record_id_column_accessor = lambda Model: getattr(Model, "recordid")
            use_timezone_aware_timestamps = False
            try:
                device_time_field_names = cls._device_time_fields["V1_0"]
            except (AttributeError, KeyError):
                raise ValueError(f"{cls.__name__}: missing device_time_fields for {schema_version=}")
        elif schema_version == "V0_9":
            device_id_column_accessor = lambda Model: getattr(Model, "DeviceId")
            server_time_column_accessor = lambda Model: getattr(Model, "TimeReceived")
            record_id_column_accessor = lambda Model: getattr(Model, "CheckinId")
            use_timezone_aware_timestamps = True
            try:
                device_time_field_names = cls._device_time_fields["V0_9"]
            except (AttributeError, KeyError):
                raise ValueError(f"{cls.__name__}: missing device_time_fields for {schema_version=}")
        else:
            raise NotImplementedError(f"{cls.__name__}: schema_version={schema_version=} Not yet implemented")

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

    @classmethod
    @lru_cache(maxsize=64)
    def _get_message_mapper(cls, env: Env):
        schema_version: Schema = SCHEMA_BY_ENV[env]
        return message_mapper(cls, schema_version)

    # --------------------------------------------------|  Message implementer helpers  |----------

    @classmethod
    def _get_reason_from_mapping(cls, value: Optional[int], mapping: Dict[int, str]) -> str:
        """Get the reason string from a bit mask value."""
        if value is None:
            return "No value provided"
        return mapping.get(value, f"Unknown: {value}")

    # --------------------------------------------------|  Load from Database  |----------

    @classmethod
    def last(cls: Type[TMsg], *, dut_id: int, env: Env = "VAL_1_0") -> Optional[TMsg]:
        """
        Retrieve the most recent message record for a specific device.

        Args:
            dut_id: Device unique identifier (e.g., 0x70B3D584C01E1445).
            env: Deployment environment Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9"

        Returns:
            The most recent message instance for the device, or None if no records exist in the database.
        """
        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        with CoreCloudDBInterface(env=env) as session:
            row = (
                session.query(model)
                .filter(config.device_id_col(model) == dut_id)
                .order_by(config.record_id_col(model).desc())
                .first()
            )

        return row_to_message if row else None

    @classmethod
    def since_server_time(
        cls: Type[TMsg], *, dut_id: int, start_time: datetime, end_time: datetime | None = None, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages received by the server within a specific time range for a single device.

        Args:
            dut_id: Device unique identifier.
            start_time: Starting timestamp (exclusive). Messages received after this time
                are included.
            end_time: Optional ending timestamp (inclusive). Messages received on or before
                this time are included. If None, no upper bound is applied.
            env: Deployment environment. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of message instances received by the server in the specified time range.
            Returns an empty list if no messages match the criteria.
        """

        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        start_time = dt_to_utc(start_time)
        end_time = dt_to_utc(end_time)

        with CoreCloudDBInterface(env=env) as session:
            query = session.query(model).filter(
                config.server_time_col(model) == dut_id,
                config.server_time_col(model) > start_time,  # Don't include any message at start time
            )

            if end_time is not None:
                query = query.filter(
                    config.server_time_col(model) <= end_time,  # Do include any messages at end time
                )

            result_rows = query.all()

        return [row_to_message(row) for row in result_rows]

    @classmethod
    def since_device_time(
        cls: Type[TMsg], dut_id: int, start_time: datetime, end_time: datetime | None = None, *, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages based on device-recorded timestamps for a single device.

        Args:
            dut_id: Device unique identifier.
            start_time: Starting device timestamp (exclusive). Messages recorded after this
                time are included.
            end_time: Optional ending device timestamp (inclusive). Messages recorded on or
                before this time are included. If None, no upper bound is applied.
            env: Deployment environment. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of message instances recorded by the device in the specified time range.
            Returns an empty list if no messages match the criteria.
        """

        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        start_time = dt_to_utc(start_time)
        end_time = dt_to_utc(end_time)

        device_time_col = config.device_time_expr(model, config.device_time_fields)

        with CoreCloudDBInterface(env=env) as session:
            query = session.query(model).filter(
                config.device_id_col(model) == dut_id,
                device_time_col > start_time,  # Don't include any message at start time
            )

            if end_time is not None:
                query = query.filter(
                    device_time_col <= end_time,  # Do include any messages at end time
                )

            result_rows = query.all()

        return [row_to_message(row) for row in result_rows]

    @classmethod
    def since_record_id(
        cls: Type[TMsg], *, dut_id: int, start_id: int, end_id: int | None = None, env: Env = "VAL_1_0"
    ) -> List[TMsg]:
        """
        Query messages by database record ID range for a single device.

        Args:
            dut_id: Device unique identifier.
            start_id: Starting record ID (exclusive). Messages with record IDs greater
                than this value are included.
            end_id: Optional ending record ID (inclusive). Messages with record IDs less
                than or equal to this value are included. If None, no upper bound is applied.
            env: Deployment environment. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of message instances whose record IDs fall within the specified range.
            Returns an empty list if no messages match the criteria.
        """

        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        with CoreCloudDBInterface(env=env) as session:
            query = session.query(model).filter(
                config.device_id_col(model) == dut_id,
                config.record_id_col(model) > start_id,  # Don't include any message at start time
            )

            if end_id is not None:
                query = query.filter(
                    config.record_id_col(model) <= end_id,  # Do include any messages at end time
                )

            result_rows = query.all()

        return [row_to_message(row) for row in result_rows]

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
        Query messages received by the server within a specific time range for multiple devices.

        Args:
            dut_ids: Iterable of device unique identifiers.
            start_time: Starting timestamp (exclusive). Messages received after this time
                are included.
            end_time: Optional ending timestamp (inclusive). Messages received on or before
                this time are included. If None, no upper bound is applied.
            env: Deployment environment. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of messages from all specified devices that were received by the server
            in the specified time window. Returns an empty list if no messages match.
        """

        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        start_time = dt_to_utc(start_time)
        end_time = dt_to_utc(end_time)

        with CoreCloudDBInterface(env=env) as session:
            query = session.query(model).filter(
                config.device_id_col(model).in_(dut_ids),
                config.server_time_col(model) > start_time,  # Don't include any message at start time
            )

            if end_time is not None:
                query = query.filter(
                    config.server_time_col(model) <= end_time,  # Do include any messages at end time
                )

            result_rows = query.all()

        return [row_to_message(row) for row in result_rows]

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
        Query messages based on device-recorded timestamps for multiple devices.

        Args:
            dut_ids: Iterable of device unique identifiers.
            start_time: Starting device timestamp (exclusive). Messages recorded after this
                time are included.
            end_time: Optional ending device timestamp (inclusive). Messages recorded on or
                before this time are included. If None, no upper bound is applied.
            env: Deployment environment. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of messages from all specified devices whose device-recorded timestamps
            fall within the specified time window. Returns an empty list if none match.
        """

        config = cls._schema_config(env)
        row_to_message = cls._get_message_mapper(env)
        model = config.model

        start_time = dt_to_utc(start_time)
        end_time = dt_to_utc(end_time)

        device_time_col = config.device_time_expr(model, config.device_time_fields)

        with CoreCloudDBInterface(env=env) as session:
            query = session.query(model).filter(
                config.device_id_col(model).in_(dut_ids),
                device_time_col > start_time,  # Don't include any message at start time
            )

            if end_time is not None:
                query = query.filter(
                    device_time_col <= end_time,  # Do include any messages at end time
                )

            result_rows = query.all()

        return [row_to_message(row) for row in result_rows]

    # --------------------------------------------------|  Load from CSV   |----------
    @classmethod
    def from_csv_file(cls, csv_file_path: str | Path, *, env: Env = "VAL_1_0") -> List[TMsg]:
        """
        Get messages from an SQL query dumped to a CSV file.

        Args:
            csv_file_path: Path to the CSV file.
            env: Environment to use. Valid options: "DEV_1_0", "VAL_1_0", "DEV_0_9".

        Returns:
            A list of messages from the specified CSV file.
        """
        log = Logger(log_name=cls.from_csv_file.__name__)
        csv_file_path = Path(csv_file_path)
        schema = SCHEMA_BY_ENV[env]
        messages: list[TMsg] = []

        type_hints = get_type_hints(cls, include_extras=True)

        # --------------------|  Get field + type to column name mappings  |--------------------
        field_defs: list[tuple[str, Any, str]] = []

        for field in fields(cls):
            if not field.init:
                continue  # skip non-init fields

            field_type = type_hints.get(field.name, field.type)
            column_name: str | None = None

            # Get field mapping to correct schema ORM column name
            if get_origin(field_type) is Annotated:
                meta_items = get_args(field_type)[1:]
                for meta in meta_items:
                    if isinstance(meta, db_translation):
                        mapped = meta.by_schema.get(schema)
                        if mapped:
                            column_name = mapped
                        break

            # if not found we stop
            if column_name is None:
                msg = f"No db_translation mapping for field {field.name=} in {schema=}."
                log.warning(msg)
                # raise ValueError(msg)

            field_defs.append((field.name, field_type, column_name))

        # --------------------|  Read messages in from CSV  |--------------------
        with csv_file_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)

            # Check this file has the columns we are expecting
            csv_columns = set(reader.fieldnames or [])
            expected_columns = {col for _, _, col in field_defs if col is not None}
            missing = expected_columns - csv_columns

            if missing:
                msg = f"CSV file '{csv_file_path}' is missing required columns for {schema=}, {sorted(missing)}"
                log.critical(msg)
                raise ValueError(msg)

            # Build messages
            for row in reader:
                msg_kwargs: dict[str, Any] = {}

                for field_name, field_type, column_name in field_defs:
                    raw_value = row.get(column_name)
                    if raw_value == "NULL":
                        raw_value = None

                    msg_kwargs[field_name] = convert_str_to_type(raw_value, field_type)

                messages.append(cls(**msg_kwargs))

        return messages
