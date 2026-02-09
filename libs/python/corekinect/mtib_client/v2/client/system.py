from typing import Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import HealthCheckRequest, SystemInfoRequest

from ._base import BaseClient
from ..types.common import HealthStatus, SystemInfo


class SystemMixin(BaseClient):
    """System and health check operations."""

    def health_check(self) -> Tuple[Optional[str], Optional[HealthStatus]]:
        """Perform a health check on the MTIB server.

        Returns:
            (error, HealthStatus) tuple. error is None on success.
        """
        try:
            resp = self._call("HealthCheck", HealthCheckRequest())
            return None, HealthStatus(
                ready=resp.ready,
                version=resp.version,
                errors=list(resp.errors),
                capabilities=dict(resp.capabilities),
            )
        except Exception as e:
            return f"health_check error: {e}", None

    def system_info(self) -> Tuple[Optional[str], Optional[SystemInfo]]:
        """Get system information from the MTIB server.

        Returns:
            (error, SystemInfo) tuple. error is None on success.
        """
        try:
            resp = self._call("SystemInfo", SystemInfoRequest())
            if not resp.success:
                return resp.message, None
            uptime_s = resp.uptime.seconds + resp.uptime.nanos / 1e9 if resp.uptime else 0.0
            return None, SystemInfo(
                hostname=resp.hostname,
                os=resp.os,
                cpu_usage=resp.cpu_usage,
                memory_usage=resp.memory_usage,
                disk_usage=resp.disk_usage,
                uptime_s=uptime_s,
            )
        except Exception as e:
            return f"system_info error: {e}", None
