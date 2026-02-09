"""Observability engine that aggregates all monitors into a single interface."""

import time
from typing import TYPE_CHECKING, Generator

from corekinect.utils import Logger

from .adc_observer import AdcObserver
from .gpio_tracker import GpioStateTracker
from .power_monitor import PowerMonitor
from .system_metrics import SystemMetricsCollector
from .uart_observer import UartObserver

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class ObservabilityEngine:
    """Aggregates all observability sub-monitors into a unified interface.

    Provides snapshot and streaming APIs that assemble data from the
    PowerMonitor, GpioStateTracker, UartObserver, and SystemMetricsCollector.
    """

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.power_monitor = PowerMonitor(logger, hardware)
        self.gpio_tracker = GpioStateTracker(logger)
        self.uart_observer = UartObserver(logger)
        self.system_metrics = SystemMetricsCollector(logger, hardware)
        self.adc_observer = AdcObserver(logger)

    def start(self) -> None:
        """Start background monitoring threads."""
        self.power_monitor.start()
        self.system_metrics.start()
        self.logger.info("ObservabilityEngine: Started")

    def stop(self) -> None:
        """Stop all background monitoring threads."""
        self.power_monitor.stop()
        self.system_metrics.stop()
        self.logger.info("ObservabilityEngine: Stopped")

    def get_snapshot(self) -> dict:
        """Assemble a full observability snapshot from all sub-monitors.

        Returns:
            Dict matching the ObservabilitySnapshot protobuf structure.
        """
        now = time.time()
        return {
            "timestamp": now,
            "power_readings": self.power_monitor.get_all_readings(),
            "gpio_states": self.gpio_tracker.get_all_states(),
            "uart_ports": self.uart_observer.get_all_statuses(),
            "system_metrics": self.system_metrics.get_metrics(),
            "adc_readings": self.adc_observer.get_all_readings(),
        }

    def stream(self, interval_ms: int, filters: dict) -> Generator[dict, None, None]:
        """Yield snapshots at the requested interval.

        Args:
            interval_ms: Milliseconds between snapshots (minimum 100).
            filters: Dict with bool keys: include_power, include_gpio,
                     include_uart, include_system, include_clients,
                     include_uart_output.

        Yields:
            Snapshot dicts filtered per the request.
        """
        interval_s = max(0.1, interval_ms / 1000.0)

        while True:
            start = time.time()
            now = time.time()
            snapshot: dict = {"timestamp": now}

            if filters.get("include_power", False):
                snapshot["power_readings"] = self.power_monitor.get_all_readings()
            else:
                snapshot["power_readings"] = []

            if filters.get("include_gpio", False):
                snapshot["gpio_states"] = self.gpio_tracker.get_all_states()
            else:
                snapshot["gpio_states"] = []

            if filters.get("include_uart", False):
                statuses = self.uart_observer.get_all_statuses()
                if not filters.get("include_uart_output", False):
                    for s in statuses:
                        s["recent_lines"] = []
                snapshot["uart_ports"] = statuses
            else:
                snapshot["uart_ports"] = []

            if filters.get("include_system", False):
                snapshot["system_metrics"] = self.system_metrics.get_metrics()
            else:
                snapshot["system_metrics"] = {}

            # ADC readings — always included (cheap to read)
            snapshot["adc_readings"] = self.adc_observer.get_all_readings()

            yield snapshot

            elapsed = time.time() - start
            sleep_time = interval_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
