"""Background system metrics collector."""

import platform
import socket
import threading
import time
from typing import TYPE_CHECKING, Optional

from corekinect.utils import Logger

if TYPE_CHECKING:
    from src.hardware import HardwareContext

SERVER_VERSION = "2.0.0"


class SystemMetricsCollector:
    """Background daemon thread that periodically samples system metrics.

    Collects CPU, memory, disk usage and maintains counters for
    gRPC connections and requests.
    """

    def __init__(self, logger: Logger, hardware: "HardwareContext", sample_interval_s: float = 2):
        self.logger = logger
        self.hardware = hardware
        self._sample_interval = max(0.5, sample_interval_s)

        self._metrics: dict = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # gRPC counters
        self._connection_count = 0
        self._request_count = 0
        self._counter_lock = threading.Lock()

        # Static info
        self._hostname = socket.gethostname()
        self._os_info = f"{platform.system()} {platform.release()}"
        self._hardware_revision = hardware.revision.name if hasattr(hardware.revision, "name") else str(hardware.revision)
        self._start_time = time.time()

    def _sample_loop(self) -> None:
        """Continuously sample system metrics."""
        while not self._stop.is_set():
            try:
                import psutil
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                memory_percent = memory.percent
                disk_percent = disk.percent
            except ImportError:
                cpu_percent = 0.0
                memory_percent = 0.0
                disk_percent = 0.0

            uptime_seconds = time.time() - self._start_time

            with self._counter_lock:
                conn_count = self._connection_count
                req_count = self._request_count

            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "uptime_seconds": uptime_seconds,
                "hostname": self._hostname,
                "os_info": self._os_info,
                "hardware_revision": self._hardware_revision,
                "server_version": SERVER_VERSION,
                "grpc_active_connections": conn_count,
                "grpc_total_requests": req_count,
            }

            with self._lock:
                self._metrics = metrics

            self._stop.wait(self._sample_interval)

    def start(self) -> None:
        """Start the background metrics collection thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._sample_loop, daemon=True, name="system-metrics"
        )
        self._thread.start()
        self.logger.info("SystemMetricsCollector: Started")

    def stop(self) -> None:
        """Stop the background metrics collection thread."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self.logger.info("SystemMetricsCollector: Stopped")

    def increment_connections(self) -> None:
        """Thread-safe connection count increment."""
        with self._counter_lock:
            self._connection_count += 1

    def decrement_connections(self) -> None:
        """Thread-safe connection count decrement."""
        with self._counter_lock:
            self._connection_count = max(0, self._connection_count - 1)

    def record_request(self) -> None:
        """Thread-safe request count increment."""
        with self._counter_lock:
            self._request_count += 1

    def get_metrics(self) -> dict:
        """Return the latest cached system metrics."""
        with self._lock:
            return dict(self._metrics) if self._metrics else {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "uptime_seconds": time.time() - self._start_time,
                "hostname": self._hostname,
                "os_info": self._os_info,
                "hardware_revision": self._hardware_revision,
                "server_version": SERVER_VERSION,
                "grpc_active_connections": 0,
                "grpc_total_requests": 0,
            }
