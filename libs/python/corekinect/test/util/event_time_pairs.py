from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Collection, Dict, Iterable, List, Tuple, TypeVar

T = TypeVar("T")


def get_event_time_pairs(
    obj_type: type[T],
    objects: Iterable[T],
    *,
    group_attribute: str,
    time_attribute: str,
    event_attribute: str,
    start_event_values: Collection[Any],
    end_event_values: Collection[Any],
    sort: bool = True,
    allow_unclosed: bool = False,
    ignore_bad_times: bool = False,
    bad_time: datetime = datetime(1990, 1, 1, 0, 0),
) -> Dict[Any, List[Tuple[datetime, datetime, timedelta]]]:
    """
    Find (start, end, duration) intervals per group based on event values.

    Args:
        obj_type:
            Expected type of all objects.
        objects:
            Iterable of objects containing event & time info.
        group_attribute:
            Attribute used to group objects, e.g. "device_id".
        time_attribute:
            Datetime attribute name, e.g. "time_of_fix".
        event_attribute:
            Attribute that encodes the event/state, e.g. "charger_state".
        start_event_values:
            Values that begin an interval (e.g. {"plugged_in"}).
        end_event_values:
            Values that end an interval (e.g. {"unplugged"}).
        sort:
            If True, sort by (group_attribute, time_attribute).
            If False, assume input is already ordered per group.
        allow_unclosed:
            If True, and a start is seen with no end by the end of data,
            close it at the last seen timestamp for that group.
        ignore_bad_times:
            if True, any time_attribute under bad_time will not be included.
        bad_time:
            Datetime to filter bad times

    Returns:
        Dict[group_key, List[(start_dt, end_dt, duration_td)]]

    Example:
        @dataclass
        class ChargerEvent:
            device_id: int
            ts: datetime
            charger_state: str  # "plugged_in" or "unplugged"


        example_events = [
            ChargerEvent(0xA1, datetime(2025, 9, 25, 12, 0, tzinfo=timezone.utc), "plugged_in"),
            ChargerEvent(0xA1, datetime(2025, 9, 25, 14, 0, tzinfo=timezone.utc), "unplugged"),
            ChargerEvent(0xA1, datetime(2025, 9, 25, 15, 0, tzinfo=timezone.utc), "plugged_in"),
            ChargerEvent(0xA1, datetime(2025, 9, 25, 16, 30, tzinfo=timezone.utc), "unplugged"),
            ChargerEvent(0xB2, datetime(2025, 9, 25, 13, 0, tzinfo=timezone.utc), "plugged_in"),
            ChargerEvent(0xB2, datetime(2025, 9, 25, 18, 0, tzinfo=timezone.utc), "unplugged"),
        ]

        charger_intervals = get_event_time_pairs(
            ChargerEvent,
            example_events,
            group_attribute="device_id",
            time_attribute="ts",
            event_attribute="charger_state",
            start_event_values={"plugged_in"},
            end_event_values={"unplugged"},
            sort=True,
            allow_unclosed=False,
        )

        for device_id, intervals in charger_intervals.items():
            for start, end, dur in intervals:
                print(f"{device_id:X}: on charger {start} -> {end} ({dur.total_seconds()/3600:.2f} h)")
    """
    objs = list(objects)
    if not objs:
        return {}

    # Type check
    for o in objs:
        if not isinstance(o, obj_type):
            raise TypeError(f"Object {o!r} is not of type {obj_type.__name__}")

    # --------------------|  Optional sort  |--------------------
    if sort:
        try:
            objs.sort(
                key=lambda o: (
                    getattr(o, group_attribute),
                    getattr(o, time_attribute),
                )
            )
        except AttributeError as e:
            raise AttributeError(
                f"Missing group_attribute '{group_attribute}' or " f"time_attribute '{time_attribute}' on some object"
            ) from e

    # --------------------|  Start Grouping  |--------------------
    intervals_by_group: Dict[Any, List[Tuple[datetime, datetime, timedelta]]] = {}
    open_start_by_group: Dict[Any, datetime] = {}
    last_time_by_group: Dict[Any, datetime] = {}

    start_set = set(start_event_values)
    end_set = set(end_event_values)

    for obj in objs:
        try:
            group_key = getattr(obj, group_attribute)
            current_time = getattr(obj, time_attribute)
            event_value = getattr(obj, event_attribute)
        except AttributeError as e:
            raise AttributeError(
                f"Object {obj!r} missing one of: " f"{group_attribute!r}, {time_attribute!r}, {event_attribute!r}"
            ) from e

        if not isinstance(current_time, datetime):
            raise TypeError(f"{time_attribute!r} must be a datetime on {obj!r}, " f"got {type(current_time)}")

        # Ignore bad timestamps
        if ignore_bad_times and current_time < bad_time:
            continue

        last_time_by_group[group_key] = current_time

        open_start = open_start_by_group.get(group_key)

        # Start event
        if event_value in start_set:
            if open_start is None:
                open_start_by_group[group_key] = current_time

        # End event
        elif event_value in end_set:
            if open_start is not None:
                if current_time >= open_start:
                    duration = current_time - open_start
                    intervals_by_group.setdefault(group_key, []).append((open_start, current_time, duration))
                open_start_by_group[group_key] = None

    # --------------------|  Close unclosed intervals at last seen time  |--------------------
    if allow_unclosed:
        for group_key, start_time in open_start_by_group.items():
            if start_time is not None:
                end_time = last_time_by_group[group_key]
                if end_time >= start_time:
                    duration = end_time - start_time
                    intervals_by_group.setdefault(group_key, []).append((start_time, end_time, duration))

    return intervals_by_group
