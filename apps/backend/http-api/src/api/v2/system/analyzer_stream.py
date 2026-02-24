import logging
import queue
import threading
import traceback

import eventlet
import grpc
from flask import request
from flask_socketio import SocketIO, emit

from protocols.mtib_v2.mtib_v2_pb2 import AnalyzerStreamRequest
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

MTIB_GRPC_PORT = 50052

# Active analyzer streams: "{sid}:{captureId}" -> {stop_event, channel, stub}
_active_streams: dict[str, dict] = {}
_lock = threading.Lock()

MAX_CONCURRENT_STREAMS = 10
MAX_NODE_ID_LENGTH = 255  # Maximum length for node/capture IDs


def register_analyzer_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for logic analyzer streaming.

    NOTE: Authentication is handled by the shared /kubernetes namespace connect handler
    in logs.py, which validates JWT tokens and checks ADMIN_SYSTEM_VIEW permission.
    This handler must be registered AFTER register_log_handlers() in router.py to
    inherit the authentication."""

    @socketio.on("subscribe_analyzer", namespace="/kubernetes")
    def handle_subscribe_analyzer(data):
        # Input validation: nodeId
        node_id = data.get("nodeId")
        if not node_id or not isinstance(node_id, str):
            emit("analyzer_error", {"captureId": "", "message": "Missing or invalid nodeId"})
            return
        if len(node_id) > MAX_NODE_ID_LENGTH:
            emit("analyzer_error", {"captureId": "", "message": "nodeId too long"})
            return

        # Input validation: captureId
        capture_id = data.get("captureId")
        if not capture_id or not isinstance(capture_id, str):
            emit("analyzer_error", {"captureId": "", "message": "Missing or invalid captureId"})
            return
        if len(capture_id) > MAX_NODE_ID_LENGTH:
            emit("analyzer_error", {"captureId": capture_id, "message": "captureId too long"})
            return

        sid = request.sid
        stream_key = f"{sid}:{capture_id}"

        with _lock:
            if stream_key in _active_streams:
                emit("analyzer_error", {"captureId": capture_id, "message": "Already subscribed to this capture"})
                return
            if len(_active_streams) >= MAX_CONCURRENT_STREAMS:
                emit("analyzer_error", {"captureId": capture_id, "message": "Too many active analyzer streams"})
                return

        # Look up node IP
        try:
            db = get_db_client()
            node = db.node.find_unique(where={"id": node_id})
            if not node or not node.ipAddress:
                emit("analyzer_error", {"captureId": capture_id, "message": "Node not found or no IP address"})
                return
            ip_address = node.ipAddress
        except Exception as e:
            logger.error("Analyzer subscribe - DB error: %s", e)
            emit("analyzer_error", {"captureId": capture_id, "message": "Failed to look up node"})
            return

        stop_event = threading.Event()
        with _lock:
            _active_streams[stream_key] = {"stop_event": stop_event}

        output_q = queue.Queue()

        def _blocking_analyzer_reader():
            """Run in a native OS thread to avoid eventlet/gRPC conflicts."""
            channel = None
            try:
                addr = f"{ip_address}:{MTIB_GRPC_PORT}"
                channel = grpc.insecure_channel(addr, options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 5000),
                ])
                stub = MtibV2Stub(channel)

                with _lock:
                    if stream_key in _active_streams:
                        _active_streams[stream_key].update({
                            "channel": channel,
                            "stub": stub,
                        })

                # Create gRPC streaming request
                req = AnalyzerStreamRequest(
                    capture_id=capture_id,
                    max_samples_per_chunk=1000,
                    interval_s=0.1
                )

                # Open streaming RPC
                response_stream = stub.AnalyzerStream(req, timeout=None)

                for resp in response_stream:
                    if stop_event.is_set():
                        break

                    if not resp.success:
                        output_q.put(("error", resp.message or "Stream error"))
                        break

                    # Parse samples from protobuf
                    samples = []
                    for sample in resp.samples:
                        samples.append({
                            "timestamp_ns": sample.timestamp_ns,
                            "digital_values": list(sample.digital_values),
                        })

                    if samples:
                        output_q.put(("data", {
                            "samples": samples,
                            "timestamp": resp.samples[-1].timestamp_ns / 1e9 if resp.samples else 0,
                        }))

                    # Check for completion
                    if resp.capture_complete:
                        output_q.put(("complete", {
                            "total_samples": resp.total_samples,
                            "samples_dropped": resp.samples_dropped,
                        }))
                        break

            except grpc.RpcError as e:
                if not stop_event.is_set():
                    code = e.code() if hasattr(e, "code") else None
                    if code != grpc.StatusCode.CANCELLED:
                        logger.error("Analyzer gRPC error for %s: %s", capture_id, e)
                        output_q.put(("error", "Analyzer stream connection lost"))
            except Exception as e:
                if not stop_event.is_set():
                    logger.error("Analyzer reader error: %s", e)
                    traceback.print_exc()
                    output_q.put(("error", "Analyzer stream error occurred"))
            finally:
                if channel:
                    try:
                        channel.close()
                    except Exception:
                        pass
                output_q.put(("done", None))

        def run_analyzer_stream():
            reader = threading.Thread(target=_blocking_analyzer_reader, daemon=True)
            reader.start()

            try:
                while True:
                    try:
                        msg_type, payload = output_q.get_nowait()
                    except queue.Empty:
                        if not reader.is_alive():
                            break
                        eventlet.sleep(0.05)
                        continue

                    if msg_type == "data":
                        socketio.emit("analyzer_data", {
                            "captureId": capture_id,
                            "samples": payload["samples"],
                            "timestamp": payload["timestamp"],
                        }, room=sid, namespace="/kubernetes")
                    elif msg_type == "complete":
                        socketio.emit("analyzer_complete", {
                            "captureId": capture_id,
                            "status": "complete",
                            "totalSamples": payload["total_samples"],
                            "samplesDropped": payload["samples_dropped"],
                        }, room=sid, namespace="/kubernetes")
                        break
                    elif msg_type == "error":
                        socketio.emit("analyzer_error", {
                            "captureId": capture_id,
                            "message": payload
                        }, room=sid, namespace="/kubernetes")
                        break
                    elif msg_type == "done":
                        break
            except Exception as e:
                logger.error("Analyzer emit error: %s", e)
                traceback.print_exc()
            finally:
                stop_event.set()
                reader.join(timeout=5)
                with _lock:
                    _active_streams.pop(stream_key, None)

        socketio.start_background_task(run_analyzer_stream)

    @socketio.on("unsubscribe_analyzer", namespace="/kubernetes")
    def handle_unsubscribe_analyzer(data):
        """Unsubscribe from analyzer stream."""
        try:
            capture_id = data.get("captureId", "")
            sid = request.sid
            stream_key = f"{sid}:{capture_id}"

            with _lock:
                stream = _active_streams.pop(stream_key, None)
            if stream:
                stop_event = stream.get("stop_event")
                if stop_event:
                    stop_event.set()
                logger.info("Client %s unsubscribed from analyzer capture %s", sid, capture_id)
        except Exception as e:
            logger.error("Analyzer unsubscribe error: %s", e)


def cleanup_analyzer_streams(sid: str):
    """Clean up all analyzer streams for a disconnected client."""
    try:
        with _lock:
            keys_to_remove = [k for k in _active_streams if k.startswith(f"{sid}:")]
            streams_to_clean = []
            for key in keys_to_remove:
                stream = _active_streams.pop(key, None)
                if stream:
                    streams_to_clean.append(stream)

        # Stop all streams outside the lock
        for stream in streams_to_clean:
            stop_event = stream.get("stop_event")
            if stop_event:
                stop_event.set()

        if streams_to_clean:
            logger.info("Cleaned up %d analyzer streams for client %s", len(streams_to_clean), sid)
    except Exception as e:
        logger.error("Analyzer cleanup error for %s: %s", sid, e)
