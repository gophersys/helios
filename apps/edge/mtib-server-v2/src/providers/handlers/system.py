"""System handler for HealthCheck and SystemInfo RPCs."""

import platform
import socket
import time
from typing import TYPE_CHECKING

from corekinect.utils import Logger
from src.shared.types import (
    HealthCheckRequest,
    HealthCheckResponse,
    SystemInfoRequest,
    SystemInfoResponse,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class SystemHandler:
    """Handles HealthCheck and SystemInfo RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext", start_time: float):
        self.logger = logger
        self.hardware = hardware
        self._start_time = start_time
        self._hostname = socket.gethostname()
        self.errors: list[str] = []

    def health_check(self, request: HealthCheckRequest, context) -> HealthCheckResponse:
        """Check server health status."""
        capabilities = {
            "hardware_revision": self.hardware.revision.name,
            "gpio": "true",
            "power": "true",
            "gpio_expander": str(self.hardware.has_gpio_expander).lower(),
            "jlink_mux": str(self.hardware.has_jlink_mux).lower(),
            "motor_power_switch": str(self.hardware.has_motor_power_switch).lower(),
        }

        return HealthCheckResponse(
            ready=True,
            version="2.0.0",
            errors=self.errors,
            capabilities=capabilities,
        )

    def system_info(self, request: SystemInfoRequest, context) -> SystemInfoResponse:
        """Get server system information."""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            memory_usage = memory.percent
            disk_usage = disk.percent
        except ImportError:
            cpu_usage = 0.0
            memory_usage = 0.0
            disk_usage = 0.0

        uptime_seconds = int(time.time() - self._start_time)

        return SystemInfoResponse(
            success=True,
            message="",
            hostname=self._hostname,
            os=f"{platform.system()} {platform.release()}",
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            uptime=Timestamp(seconds=uptime_seconds, nanos=0),
        )
