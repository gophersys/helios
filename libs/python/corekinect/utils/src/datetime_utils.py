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
