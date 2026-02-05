from typing import Optional

from influxdb_client import InfluxDBClient, BucketRetentionRules
from influxdb_client.client.write_api import SYNCHRONOUS

from config.env import env_config

# Global singleton instances
appInfluxClient: Optional[InfluxDBClient] = None
appInfluxWriteApi = None
appInfluxQueryApi = None


def init_influxdb_client() -> None:
    """Initialize the global InfluxDB client and auto-create the metrics bucket if missing."""
    global appInfluxClient, appInfluxWriteApi, appInfluxQueryApi

    if appInfluxClient is not None:
        return

    appInfluxClient = InfluxDBClient(
        url=env_config.INFLUXDB_URL,
        token=env_config.INFLUXDB_TOKEN,
        org=env_config.INFLUXDB_ORG,
    )

    appInfluxWriteApi = appInfluxClient.write_api(write_options=SYNCHRONOUS)
    appInfluxQueryApi = appInfluxClient.query_api()

    # Auto-create the metrics bucket (infinite retention) if it doesn't exist
    try:
        buckets_api = appInfluxClient.buckets_api()
        existing = buckets_api.find_bucket_by_name(env_config.INFLUXDB_BUCKET_METRICS)
        if existing is None:
            buckets_api.create_bucket(
                bucket_name=env_config.INFLUXDB_BUCKET_METRICS,
                retention_rules=[BucketRetentionRules(type="expire", every_seconds=0)],
                org=env_config.INFLUXDB_ORG,
            )
            print(f"Created InfluxDB bucket: {env_config.INFLUXDB_BUCKET_METRICS}")
        else:
            print(f"InfluxDB bucket already exists: {env_config.INFLUXDB_BUCKET_METRICS}")
    except Exception as e:
        print(f"Warning: Could not ensure InfluxDB metrics bucket exists: {e}")

    print("InfluxDB client initialized")


def get_influxdb_client() -> Optional[InfluxDBClient]:
    return appInfluxClient


def get_write_api():
    return appInfluxWriteApi


def get_query_api():
    return appInfluxQueryApi


def close_influxdb_client() -> None:
    global appInfluxClient, appInfluxWriteApi, appInfluxQueryApi
    if appInfluxClient is not None:
        appInfluxClient.close()
        appInfluxClient = None
        appInfluxWriteApi = None
        appInfluxQueryApi = None
