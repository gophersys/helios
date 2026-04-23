import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import grpc

from protocols.mtib.mtib_pb2 import Empty
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub

logger = logging.getLogger(__name__)

# gRPC port for MTIB servers
MTIB_GRPC_PORT = 50053

# Module-level singleton
_service = None


def init_observability_service(poll_interval_s=5):
    """Create and start the global MtibObservabilityService."""
    global _service
    _service = MtibObservabilityService(poll_interval_s=poll_interval_s)
    _service.start()
    return _service


def get_observability_service():
    """Get the global MtibObservabilityService instance."""
    return _service


def _snapshot_to_dict(snapshot) -> dict:
    """Convert a GetSnapshotResponse protobuf to a plain dict."""
    return {
        "timestamp_ms": snapshot.timestamp_ms,
        "hw_revision": snapshot.hw_revision,
        "powerReadings": [
            {
                "channel": p.channel,
                "enabled": p.enabled,
                "voltage_v": p.voltage_v,
                "current_ma": p.current_ma,
                "power_mw": p.voltage_v * p.current_ma if p.enabled else 0.0,
            }
            for p in snapshot.power
        ],
        "gpioStates": [
            {"gpio": g.gpio, "state": g.state}
            for g in snapshot.gpio
        ],
        "adcReadings": [
            {"channel": a.channel, "voltage_v": a.voltage_v}
            for a in snapshot.adc
        ],
    }


class MtibObservabilityService:
    """Service that aggregates observability data from all MTIB servers.

    Uses persistent gRPC channels (connection pooling) and parallel polling
    via ThreadPoolExecutor to handle large fleets efficiently.
    """

    def __init__(self, poll_interval_s=5, max_workers=10):
        self._poll_interval = poll_interval_s
        self._snapshots = {}  # node_id -> {snapshot, last_updated, error, ...}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

        # Persistent gRPC channels — keyed by ip_address
        self._channels = {}  # ip_address -> grpc.Channel
        self._stubs = {}     # ip_address -> MtibV1Stub
        self._channel_lock = threading.Lock()

        # Backoff tracking for down nodes — avoids hammering unreachable nodes
        self._fail_counts = {}  # ip_address -> consecutive failure count
        self._last_fail = {}    # ip_address -> timestamp of last failure

        # Thread pool for parallel polling
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="obsv-poll")

        # WebSocket subscribers: "{sid}:{nodeId}" -> {"sid": str, "nodeId": str, "features": list[str], "emit_fn": callable}
        self._subscribers = {}
        self._subscribers_lock = threading.Lock()

    def start(self):
        """Start background polling thread."""
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Observability service started (poll interval: %ds)", self._poll_interval)

    def stop(self):
        """Stop polling and clean up channels."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._executor.shutdown(wait=False)
        self._close_all_channels()

    def _close_all_channels(self):
        """Close all persistent gRPC channels."""
        with self._channel_lock:
            for addr, channel in self._channels.items():
                try:
                    channel.close()
                except Exception:
                    pass
            self._channels.clear()
            self._stubs.clear()

    def _get_stub(self, ip_address: str) -> MtibV1Stub:
        """Get or create a persistent gRPC stub for an MTIB server."""
        with self._channel_lock:
            if ip_address not in self._channels:
                addr = f"{ip_address}:{MTIB_GRPC_PORT}"
                channel = grpc.insecure_channel(addr, options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.max_reconnect_backoff_ms", 5000),
                ])
                self._channels[ip_address] = channel
                self._stubs[ip_address] = MtibV1Stub(channel)
            return self._stubs[ip_address]

    def _invalidate_channel(self, ip_address: str):
        """Close and remove a channel that has failed."""
        with self._channel_lock:
            channel = self._channels.pop(ip_address, None)
            self._stubs.pop(ip_address, None)
        if channel:
            try:
                channel.close()
            except Exception:
                pass

    def _should_skip_node(self, ip_address: str) -> bool:
        """Check if a node should be skipped due to backoff from consecutive failures."""
        fail_count = self._fail_counts.get(ip_address, 0)
        if fail_count == 0:
            return False
        # Exponential backoff: skip for 2^min(fail_count, 5) poll cycles
        # At fail_count=1: skip 2 cycles (10s), at 5+: skip 32 cycles (160s)
        last_fail = self._last_fail.get(ip_address, 0)
        backoff_s = min(2 ** min(fail_count, 5), 32) * self._poll_interval
        return (time.time() - last_fail) < backoff_s

    def _poll_loop(self):
        """Background loop: fetch snapshots from all registered nodes."""
        while not self._stop_event.is_set():
            try:
                self._poll_all_nodes()
            except Exception as e:
                logger.error("Observability poll error: %s", e)
            self._stop_event.wait(self._poll_interval)

    def _poll_all_nodes(self):
        """Fetch observability from all nodes in parallel."""
        try:
            from src.services.database.prisma import get_db_client
            db = get_db_client()
        except Exception:
            return

        try:
            nodes = db.node.find_many(where={"ipAddress": {"not": None}})
        except Exception as e:
            logger.debug("Failed to query nodes: %s", e)
            return

        # Filter to pollable nodes (have IP, not in backoff)
        pollable = []
        for node in nodes:
            if not node.ipAddress:
                continue
            if self._should_skip_node(node.ipAddress):
                continue
            pollable.append(node)

        if not pollable:
            return

        # Poll all nodes in parallel
        futures = {}
        for node in pollable:
            future = self._executor.submit(self._fetch_snapshot, node.ipAddress)
            futures[future] = node

        for future in as_completed(futures, timeout=10):
            node = futures[future]
            node_id = node.id
            try:
                snapshot_dict = future.result()
                # Success — clear backoff
                self._fail_counts.pop(node.ipAddress, None)
                self._last_fail.pop(node.ipAddress, None)
                with self._lock:
                    self._snapshots[node_id] = {
                        "snapshot": snapshot_dict,
                        "lastUpdated": time.time(),
                        "error": None,
                        "nodeId": node_id,
                        "nodeName": node.name,
                        "hostname": node.hostname,
                        "ipAddress": node.ipAddress,
                    }
                # Broadcast to WebSocket subscribers
                self._broadcast_snapshot(node_id, snapshot_dict)
            except Exception as e:
                # Failure — increment backoff, invalidate channel
                logger.debug("Observability poll failed for %s: %s", node.ipAddress, e)
                self._fail_counts[node.ipAddress] = self._fail_counts.get(node.ipAddress, 0) + 1
                self._last_fail[node.ipAddress] = time.time()
                self._invalidate_channel(node.ipAddress)
                with self._lock:
                    self._snapshots[node_id] = {
                        "snapshot": None,
                        "lastUpdated": time.time(),
                        "error": "Connection failed",
                        "nodeId": node_id,
                        "nodeName": node.name,
                        "hostname": node.hostname,
                        "ipAddress": node.ipAddress,
                    }

    def _fetch_snapshot(self, ip_address: str) -> dict:
        """Fetch a single observability snapshot using persistent channel."""
        stub = self._get_stub(ip_address)
        resp = stub.GetSnapshot(Empty(), timeout=3)
        if not resp.success:
            raise RuntimeError(f"GetSnapshot failed: {resp.message}")
        return _snapshot_to_dict(resp)

    def get_all_snapshots(self) -> dict:
        """Get cached snapshots for all nodes."""
        with self._lock:
            return dict(self._snapshots)

    def get_snapshot(self, node_id: str) -> dict | None:
        """Get cached snapshot for a single node."""
        with self._lock:
            return self._snapshots.get(node_id)

    def get_fleet_overview(self) -> dict:
        """Get summary stats across all nodes."""
        with self._lock:
            snapshots = dict(self._snapshots)

        total = len(snapshots)
        online = 0
        error_count = 0
        total_power_mw = 0.0

        for entry in snapshots.values():
            if entry.get("error"):
                error_count += 1
            else:
                online += 1
                snap = entry.get("snapshot")
                if snap and snap.get("powerReadings"):
                    for reading in snap["powerReadings"]:
                        if reading.get("enabled"):
                            total_power_mw += reading.get("power_mw", 0.0)

        return {
            "totalNodes": total,
            "onlineNodes": online,
            "errorNodes": error_count,
            "totalPowerMw": round(total_power_mw, 2),
        }

    def register_subscriber(self, sid: str, node_id: str, features: list[str], emit_fn: "Callable[..., Any]"):
        """Register a WebSocket client to receive observability updates for a node.

        Args:
            sid: Socket.IO session ID
            node_id: MTIB node ID to subscribe to
            features: List of features to include (e.g., ["power", "gpio", "adc", "system"])
            emit_fn: Callback function to emit data to the client
        """
        session_key = f"{sid}:{node_id}"
        with self._subscribers_lock:
            self._subscribers[session_key] = {
                "sid": sid,
                "nodeId": node_id,
                "features": features,
                "emit_fn": emit_fn,
            }
        logger.info("Registered observability subscriber: %s for node %s (features: %s)", sid, node_id, features)

    def unregister_subscriber(self, sid: str, node_id: str):
        """Unregister a WebSocket client from receiving updates."""
        session_key = f"{sid}:{node_id}"
        with self._subscribers_lock:
            removed = self._subscribers.pop(session_key, None)
        if removed:
            logger.info("Unregistered observability subscriber: %s for node %s", sid, node_id)

    def cleanup_subscribers(self, sid: str):
        """Remove all subscriptions for a disconnected client."""
        with self._subscribers_lock:
            keys_to_remove = [k for k in self._subscribers if k.startswith(f"{sid}:")]
            for key in keys_to_remove:
                self._subscribers.pop(key, None)
        if keys_to_remove:
            logger.info("Cleaned up %d observability subscriptions for sid %s", len(keys_to_remove), sid)

    def get_subscriber_count(self) -> int:
        """Get the total number of active subscriptions (for resource limit checking)."""
        with self._subscribers_lock:
            return len(self._subscribers)

    def _broadcast_snapshot(self, node_id: str, snapshot: dict):
        """Broadcast a snapshot to all subscribers for this node."""
        with self._subscribers_lock:
            subscribers = [
                sub for key, sub in self._subscribers.items()
                if sub["nodeId"] == node_id
            ]

        if not subscribers:
            return

        timestamp = time.time()
        for sub in subscribers:
            try:
                # Filter snapshot to only include requested features
                filtered = self._filter_snapshot(snapshot, sub["features"])
                filtered["nodeId"] = node_id
                filtered["timestamp"] = timestamp

                # Emit to client using the provided callback
                emit_fn = sub["emit_fn"]
                emit_fn(filtered)
            except Exception as e:
                logger.error("Failed to broadcast to subscriber %s: %s", sub["sid"], e)

    def _filter_snapshot(self, snapshot: dict, features: list[str]) -> dict:
        """Filter a snapshot to only include requested features.

        Features: "power", "gpio", "adc", "uart", "system", "clients"
        """
        result = {}

        # Map feature names to snapshot keys
        feature_map = {
            "power": "powerReadings",
            "gpio": "gpioStates",
            "adc": "adcReadings",
            "uart": "uartPorts",
            "system": "systemMetrics",
            "clients": "connectedClients",
        }

        for feature in features:
            key = feature_map.get(feature)
            if key and key in snapshot:
                result[key] = snapshot[key]

        return result
