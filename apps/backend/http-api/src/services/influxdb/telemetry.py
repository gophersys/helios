from datetime import datetime, timezone
from typing import Dict, Optional

from influxdb_client import Point, WritePrecision

from config.env import env_config
from src.services.influxdb.client import get_write_api


def write_device_telemetry(
    device_id: str,
    serial_number: str,
    product: str,
    session_id: str,
    sensor_type: str,
    fields: Dict[str, float],
    timestamp: Optional[datetime] = None,
) -> None:
    """Write device sensor telemetry to the telemetry_raw bucket."""
    write_api = get_write_api()
    if write_api is None:
        return

    point = (
        Point("device_telemetry")
        .tag("device_id", device_id)
        .tag("serial_number", serial_number)
        .tag("product", product)
        .tag("session_id", session_id)
        .tag("sensor_type", sensor_type)
    )

    for key, value in fields.items():
        point = point.field(key, value)

    point = point.time(timestamp or datetime.now(timezone.utc), WritePrecision.MS)

    write_api.write(
        bucket=env_config.INFLUXDB_BUCKET_TELEMETRY,
        org=env_config.INFLUXDB_ORG,
        record=point,
    )


def write_test_execution_metric(
    product: str,
    test_name: str,
    test_category: str,
    node_id: str,
    session_id: str,
    status: str,
    duration_ms: float,
    passed: bool,
    step_count: int,
    timestamp: Optional[datetime] = None,
) -> None:
    """Write test execution metrics to the metrics bucket."""
    write_api = get_write_api()
    if write_api is None:
        return

    point = (
        Point("test_execution")
        .tag("product", product)
        .tag("test_name", test_name)
        .tag("test_category", test_category)
        .tag("node_id", node_id)
        .tag("session_id", session_id)
        .tag("status", status)
        .field("duration_ms", duration_ms)
        .field("passed", passed)
        .field("step_count", step_count)
        .time(timestamp or datetime.now(timezone.utc), WritePrecision.MS)
    )

    write_api.write(
        bucket=env_config.INFLUXDB_BUCKET_METRICS,
        org=env_config.INFLUXDB_ORG,
        record=point,
    )
