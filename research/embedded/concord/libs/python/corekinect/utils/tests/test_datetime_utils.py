from datetime import datetime

import pytest

from ..timeutil.formaters import (
    mst_datetime_to_utc_str,
    mst_str_to_utc_datetime,
    str_to_datetime,
    utc_datetime_to_mst_str,
    utc_str_to_mst_datetime,
)


def test_str_to_datetime():
    """Test str to datetime."""
    date_str = "2023-10-15 12:30:45"
    expected = datetime(2023, 10, 15, 12, 30, 45)
    assert str_to_datetime(date_str) == expected

    date_str = "2020-01-01 00:00:00"
    expected = datetime(2020, 1, 1, 0, 0, 0)
    assert str_to_datetime(date_str) == expected


def test_str_to_datetime_custom_format():
    """Test str to datetime custom format."""
    date_str = "15/10/2023 12:30"
    expected = datetime(2023, 10, 15, 12, 30)
    assert str_to_datetime(date_str, "%d/%m/%Y %H:%M") == expected


def test_str_to_datetime_invalid_format():
    """Test str to datetime invalid format."""
    date_str = "2023/10/15"
    with pytest.raises(ValueError):
        str_to_datetime(date_str, "%Y-%m-%d %H:%M:%S")


def test_mst_str_to_utc_datetime():
    """Test mst str to utc datetime."""
    mst_str = "2023-10-15 12:30:45"
    expected = datetime(2023, 10, 15, 19, 30, 45)  # MST +7 hours
    assert mst_str_to_utc_datetime(mst_str) == expected


def test_utc_str_to_mst_datetime():
    """Test utc str to mst datetime."""
    utc_str = "2023-10-15 19:30:45"
    expected = datetime(2023, 10, 15, 12, 30, 45)  # UTC -7 hours
    assert utc_str_to_mst_datetime(utc_str) == expected


def test_utc_datetime_to_mst_str():
    """Test utc datetime to mst str."""
    utc_dt = datetime(2023, 10, 15, 19, 30, 45)
    expected_str = "2023-10-15 12:30:45"
    assert utc_datetime_to_mst_str(utc_dt) == expected_str


def test_mst_datetime_to_utc_str():
    """Test mst datetime to utc str."""
    mst_dt = datetime(2023, 10, 15, 12, 30, 45)
    expected_str = "2023-10-15 19:30:45"
    assert mst_datetime_to_utc_str(mst_dt) == expected_str
