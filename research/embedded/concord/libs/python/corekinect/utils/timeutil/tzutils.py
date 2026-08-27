from datetime import datetime, timezone

from corekinect.utils import Logger


def dt_to_utc(timestamp: datetime, as_naive_utc: bool = False) -> datetime:
    """
    Convert a datetime object to Coordinated Universal Time (UTC).

        This function normalizes any datetime—naive or timezone-aware—into UTC.
        Naive datetimes are assumed to already represent UTC time and will have
        `tzinfo=timezone.utc` attached. Timezone-aware datetimes are converted
        to UTC using `astimezone(timezone.utc)`.

        Optionally, the returned datetime can be converted back to a naive format
        (`tzinfo=None`) while still representing a UTC moment in time.

        Args:
            timestamp (datetime):
                A datetime object to convert. May be naive (no tzinfo) or
                timezone-aware. Naive values are assumed to be in UTC.
            as_naive_utc (bool, optional):
                If True, returns the UTC timestamp as a naive datetime
                (`tzinfo=None`). Defaults to False.

        Returns:
            datetime: A datetime object normalized to UTC. The returned value is
            timezone-aware unless `as_naive_utc=True`.

        Raises:
            ValueError: If `timestamp` is not a `datetime` instance.

        Examples:
            Convert a naive datetime (assumed to be UTC):

                >>> from datetime import datetime
                >>> dt = datetime(2025, 1, 1, 12, 0, 0)  # naive, assumed UTC
                >>> dt_to_utc(dt)
                datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

            Convert an aware datetime from another timezone:

                >>> from datetime import datetime
                >>> from zoneinfo import ZoneInfo
                >>> dt = datetime(2025, 1, 1, 12, 0, tzinfo=ZoneInfo("US/Eastern"))
                >>> dt_to_utc(dt)
                datetime.datetime(2025, 1, 1, 17, 0, tzinfo=datetime.timezone.utc)

            Return UTC as a naive datetime:

                >>> dt_to_utc(dt, as_naive_utc=True)
                datetime.datetime(2025, 1, 1, 17, 0)
    """
    log = Logger(log_name=dt_to_utc.__name__)

    if not isinstance(timestamp, datetime):
        log.error(f"Timestamp not a datetime {timestamp=}")
        raise ValueError(
            f"Timestamp not a datetime {type(timestamp)}, " f"but {dt_to_utc.__name__} requires `timestamp: datetime`"
        )

    log.debug(f"Timestamp to convert to UTC {timestamp=}")
    converted_timestamp = timestamp

    if converted_timestamp.tzinfo is None:
        log.debug("Timestamp is naive; assuming UTC and attaching tzinfo=UTC")
        converted_timestamp = converted_timestamp.replace(tzinfo=timezone.utc)
    else:
        log.debug("Timestamp is aware; converting to UTC")
        converted_timestamp = converted_timestamp.astimezone(timezone.utc)

    if as_naive_utc:
        log.debug("Stripping tzinfo to return naive UTC timestamp")
        converted_timestamp = converted_timestamp.replace(tzinfo=None)

    log.debug(f"Timestamp converted to UTC {converted_timestamp=}")
    return converted_timestamp
