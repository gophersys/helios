from typing import Iterator, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import Empty, ObservabilityStreamRequest

from ._base import BaseClient


class ObservabilityMixin(BaseClient):
    """Observability data retrieval operations."""

    def get_observability_snapshot(self) -> Tuple[Optional[str], Optional[dict]]:
        """Get full observability snapshot from MTIB server.

        Returns:
            (error, snapshot_dict) tuple. error is None on success.
        """
        try:
            resp = self._call("GetObservabilitySnapshot", Empty())
            return None, _snapshot_to_dict(resp)
        except Exception as e:
            return f"get_observability_snapshot error: {e}", None

    def observability_stream(
        self,
        interval_ms: int = 1000,
        include_power: bool = True,
        include_gpio: bool = True,
        include_uart: bool = True,
        include_system: bool = True,
        include_clients: bool = True,
        include_uart_output: bool = False,
        timeout: float = None,
    ) -> Iterator:
        """Stream observability updates.

        Args:
            interval_ms: Sampling interval in milliseconds (minimum 100).
            include_power: Include power readings.
            include_gpio: Include GPIO states.
            include_uart: Include UART status.
            include_system: Include system metrics.
            include_clients: Include connected client info.
            include_uart_output: Include recent UART output lines.
            timeout: Stream timeout in seconds. None for no deadline.

        Returns:
            Iterator of ObservabilityStreamResponse messages.
        """
        req = ObservabilityStreamRequest(
            interval_ms=interval_ms,
            include_power=include_power,
            include_gpio=include_gpio,
            include_uart=include_uart,
            include_system=include_system,
            include_clients=include_clients,
            include_uart_output=include_uart_output,
        )
        return self._server_stream("ObservabilityStream", req, timeout=timeout)


def _timestamp_to_dict(ts):
    """Convert a protobuf Timestamp to a dict."""
    if not ts or (ts.seconds == 0 and ts.nanos == 0):
        return None
    return {"seconds": ts.seconds, "nanos": ts.nanos}


def _snapshot_to_dict(snapshot) -> dict:
    """Convert an ObservabilitySnapshot protobuf to a plain dict."""
    return {
        "timestamp": _timestamp_to_dict(snapshot.timestamp),
        "powerReadings": [
            {
                "channel": r.channel,
                "voltage_v": r.voltage_v,
                "current_ma": r.current_ma,
                "power_mw": r.power_mw,
                "enabled": r.enabled,
                "timestamp": _timestamp_to_dict(r.timestamp),
            }
            for r in snapshot.power_readings
        ],
        "gpioStates": [
            {
                "pin": g.pin,
                "direction": g.direction,
                "value": g.value,
                "configured": g.configured,
                "lastChanged": _timestamp_to_dict(g.last_changed),
            }
            for g in snapshot.gpio_states
        ],
        "uartPorts": [
            {
                "portName": u.port_name,
                "isOpen": u.is_open,
                "baudRate": u.baud_rate,
                "bytesReceived": u.bytes_received,
                "bytesSent": u.bytes_sent,
                "clientCount": u.client_count,
                "recentLines": list(u.recent_lines),
            }
            for u in snapshot.uart_ports
        ],
        "systemMetrics": _system_metrics_to_dict(snapshot.system_metrics) if snapshot.system_metrics else None,
        "connectedClients": [
            {
                "clientId": c.client_id,
                "remoteAddr": c.remote_addr,
                "connectedSince": _timestamp_to_dict(c.connected_since),
                "activeRpcs": list(c.active_rpcs),
            }
            for c in snapshot.connected_clients
        ],
        "adcReadings": [
            {
                "channel": a.channel,
                "voltageV": a.voltage_v,
                "rawValue": a.raw_value,
            }
            for a in snapshot.adc_readings
        ],
    }


def _system_metrics_to_dict(m) -> dict:
    """Convert ObservabilitySystemMetrics to dict."""
    return {
        "cpuPercent": m.cpu_percent,
        "memoryPercent": m.memory_percent,
        "diskPercent": m.disk_percent,
        "uptimeSeconds": m.uptime_seconds,
        "hostname": m.hostname,
        "osInfo": m.os_info,
        "hardwareRevision": m.hardware_revision,
        "serverVersion": m.server_version,
        "grpcActiveConnections": m.grpc_active_connections,
        "grpcTotalRequests": m.grpc_total_requests,
    }
