"""Observability gRPC handler for GetObservabilitySnapshot and ObservabilityStream RPCs."""

import time
from typing import Iterator

from corekinect.utils import Logger
from src.providers.observability.engine import ObservabilityEngine
from src.shared.types import (
    ObservabilityAdcReading,
    ObservabilityGpioState,
    ObservabilityPowerReading,
    ObservabilitySnapshot,
    ObservabilityStreamRequest,
    ObservabilityStreamResponse,
    ObservabilitySystemMetrics,
    ObservabilityUartStatus,
    PowerChannel,
    Timestamp,
)

# Map channel index to PowerChannel enum
_CHANNEL_ENUM = {
    0: PowerChannel.POWER_MAIN,
    1: PowerChannel.POWER_VBAT,
}


class ObservabilityHandler:
    """Handles the GetObservabilitySnapshot and ObservabilityStream RPCs."""

    def __init__(self, logger: Logger, engine: ObservabilityEngine):
        self.logger = logger
        self.engine = engine

    def _make_timestamp(self, ts: float) -> Timestamp:
        return Timestamp(seconds=int(ts), nanos=int((ts % 1) * 1e9))

    def _build_snapshot(self, data: dict) -> ObservabilitySnapshot:
        """Convert engine snapshot dict to protobuf ObservabilitySnapshot."""
        now = data.get("timestamp", time.time())

        # Power readings
        power_readings = []
        for r in data.get("power_readings", []):
            power_readings.append(ObservabilityPowerReading(
                channel=_CHANNEL_ENUM.get(r["channel"], PowerChannel.POWER_MAIN),
                voltage_v=r["voltage_v"],
                current_ma=r["current_ma"],
                power_mw=r["power_mw"],
                enabled=r["enabled"],
                timestamp=self._make_timestamp(r["timestamp"]),
            ))

        # GPIO states
        gpio_states = []
        for s in data.get("gpio_states", []):
            gpio_states.append(ObservabilityGpioState(
                pin=s["pin"],
                direction=s["direction"],
                value=s["value"],
                configured=s["configured"],
                last_changed=self._make_timestamp(s["last_changed"]),
            ))

        # UART statuses
        uart_ports = []
        for u in data.get("uart_ports", []):
            uart_ports.append(ObservabilityUartStatus(
                port_name=u["port_name"],
                is_open=u["is_open"],
                baud_rate=u["baud_rate"],
                bytes_received=u["bytes_received"],
                bytes_sent=u["bytes_sent"],
                client_count=u["client_count"],
                recent_lines=u.get("recent_lines", []),
            ))

        # System metrics
        sm = data.get("system_metrics", {})
        system_metrics = None
        if sm:
            system_metrics = ObservabilitySystemMetrics(
                cpu_percent=sm.get("cpu_percent", 0.0),
                memory_percent=sm.get("memory_percent", 0.0),
                disk_percent=sm.get("disk_percent", 0.0),
                uptime_seconds=sm.get("uptime_seconds", 0.0),
                hostname=sm.get("hostname", ""),
                os_info=sm.get("os_info", ""),
                hardware_revision=sm.get("hardware_revision", ""),
                server_version=sm.get("server_version", ""),
                grpc_active_connections=sm.get("grpc_active_connections", 0),
                grpc_total_requests=sm.get("grpc_total_requests", 0),
            )

        # ADC readings
        adc_readings = []
        for ar in data.get("adc_readings", []):
            adc_readings.append(ObservabilityAdcReading(
                channel=ar["channel"],
                voltage_v=ar["voltage_v"],
                raw_value=ar.get("raw_value", 0),
            ))

        return ObservabilitySnapshot(
            timestamp=self._make_timestamp(now),
            power_readings=power_readings,
            gpio_states=gpio_states,
            uart_ports=uart_ports,
            system_metrics=system_metrics,
            adc_readings=adc_readings,
        )

    def get_snapshot(self, request, context) -> ObservabilitySnapshot:
        """Handle GetObservabilitySnapshot RPC."""
        data = self.engine.get_snapshot()
        return self._build_snapshot(data)

    def stream(self, request: ObservabilityStreamRequest, context) -> Iterator[ObservabilityStreamResponse]:
        """Handle ObservabilityStream server-streaming RPC."""
        filters = {
            "include_power": request.include_power,
            "include_gpio": request.include_gpio,
            "include_uart": request.include_uart,
            "include_system": request.include_system,
            "include_clients": request.include_clients,
            "include_uart_output": request.include_uart_output,
        }

        self.logger.info(f"ObservabilityStream started: interval={request.interval_ms}ms")
        try:
            for snapshot_data in self.engine.stream(request.interval_ms, filters):
                if not context.is_active():
                    break
                snapshot = self._build_snapshot(snapshot_data)
                yield ObservabilityStreamResponse(snapshot=snapshot)
        finally:
            self.logger.info("ObservabilityStream ended")
