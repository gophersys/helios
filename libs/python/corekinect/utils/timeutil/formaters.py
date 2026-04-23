from datetime import datetime, timedelta


def str_to_datetime(date_str: str, date_format: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Converts a string to a datetime object.
    """
    return datetime.strptime(date_str, date_format)


def mst_str_to_utc_datetime(mst_str: str) -> datetime:
    """
    Converts a string in MST to a UTC datetime object.
    """
    return datetime.strptime(mst_str, "%Y-%m-%d %H:%M:%S") + timedelta(hours=7)


def utc_str_to_mst_datetime(utc_str: str) -> datetime:
    """
    Converts a string in UTC to an MST datetime object.
    """
    return datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S") - timedelta(hours=7)


def utc_datetime_to_mst_str(utc_datetime: datetime) -> str:
    """
    Converts a UTC datetime object to a string in MST format.
    """
    return (utc_datetime - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")


def mst_datetime_to_utc_str(mst_datetime: datetime) -> str:
    """
    Converts an MST datetime object to a string in UTC format.
    """
    return (mst_datetime + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")


def auto_format_time_elapsed(seconds: float) -> str:
    """
    Automatically formats a time-elapsed string in seconds, minutes, hours, or days

    - < 60 sec: "12.3s"
    - < 3600 sec: "5m 12s"
    - < 86400 sec: "1h 03m 55s"
    - else: "2d 1h 12m"

    Args:
        seconds: Elapsed time in seconds.

    Returns:
        Formatted time-elapsed string.
    """
    sec = seconds

    if sec < 60:
        return f"{sec:.1f}s"

    minutes = int(sec // 60)
    sec_rem = int(sec % 60)

    if minutes < 60:
        return f"{minutes}m {sec_rem}s"

    hours = int(minutes // 60)
    min_rem = int(minutes % 60)

    if hours < 24:
        return f"{hours}h {min_rem}m {sec_rem}s"

    days = int(hours // 24)
    hr_rem = int(hours % 24)

    return f"{days}d {hr_rem}h {min_rem}m"
