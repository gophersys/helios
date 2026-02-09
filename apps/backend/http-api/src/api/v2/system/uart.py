import logging
import queue
import threading
import traceback

import eventlet
import grpc
from flask import request
from flask_socketio import SocketIO, emit

from protocols.mtib_v2.mtib_v2_pb2 import (
    UartCloseRequest,
    UartConfig,
    UartOpenRequest,
    UartStreamRequest,
)
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

MTIB_GRPC_PORT = 50052

# Active UART sessions: "{sid}:{nodeId}:{portName}" -> {stop_event, stream_id, channel, stub}
_active_sessions: dict[str, dict] = {}
_lock = threading.Lock()

MAX_CONCURRENT_UART = 20


def register_uart_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for UART streaming."""

    @socketio.on("subscribe_uart", namespace="/kubernetes")
    def handle_subscribe_uart(data):
        node_id = data.get("nodeId")
        port_name = data.get("portName")
        baud = data.get("baud", 115200)

        if not node_id or not port_name:
            emit("uart_error", {"portName": port_name or "", "message": "Missing nodeId or portName"})
            return

        sid = request.sid
        session_key = f"{sid}:{node_id}:{port_name}"

        with _lock:
            if session_key in _active_sessions:
                emit("uart_error", {"portName": port_name, "message": "Already subscribed to this port"})
                return
            if len(_active_sessions) >= MAX_CONCURRENT_UART:
                emit("uart_error", {"portName": port_name, "message": "Too many active UART streams"})
                return

        # Look up node IP
        try:
            db = get_db_client()
            node = db.node.find_unique(where={"id": node_id})
            if not node or not node.ipAddress:
                emit("uart_error", {"portName": port_name, "message": "Node not found or no IP address"})
                return
            ip_address = node.ipAddress
        except Exception as e:
            logger.error("UART subscribe - DB error: %s", e)
            emit("uart_error", {"portName": port_name, "message": "Failed to look up node"})
            return

        stop_event = threading.Event()
        with _lock:
            _active_sessions[session_key] = {"stop_event": stop_event}

        output_q = queue.Queue()

        def _blocking_uart_reader():
            """Run in a native OS thread to avoid eventlet/gRPC conflicts."""
            channel = None
            stream_id = None
            try:
                addr = f"{ip_address}:{MTIB_GRPC_PORT}"
                channel = grpc.insecure_channel(addr, options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 5000),
                ])
                stub = MtibV2Stub(channel)

                # Open the UART port
                config = UartConfig(baud=baud, data_bits=8, parity=0, stop_bits=0, flow_control=0)
                open_resp = stub.UartOpen(
                    UartOpenRequest(target_id="dut", port_name=port_name, config=config),
                    timeout=5,
                )
                if not open_resp.success:
                    output_q.put(("error", open_resp.message or "Failed to open UART"))
                    return

                stream_id = open_resp.stream_id

                with _lock:
                    if session_key in _active_sessions:
                        _active_sessions[session_key].update({
                            "stream_id": stream_id,
                            "channel": channel,
                            "stub": stub,
                        })

                output_q.put(("opened", stream_id))

                # Create a request iterator that sends the stream_id once then waits
                def request_iter():
                    # Send initial request with stream_id to identify the stream
                    yield UartStreamRequest(stream_id=stream_id)
                    # Keep iterator alive until stopped
                    while not stop_event.is_set():
                        stop_event.wait(1.0)

                # Open bidirectional stream
                response_stream = stub.UartStream(request_iter(), timeout=None)

                for resp in response_stream:
                    if stop_event.is_set():
                        break
                    if resp.data:
                        decoded = resp.data.decode("utf-8", errors="replace")
                        output_q.put(("data", decoded))

            except grpc.RpcError as e:
                if not stop_event.is_set():
                    code = e.code() if hasattr(e, "code") else None
                    if code != grpc.StatusCode.CANCELLED:
                        output_q.put(("error", f"UART stream error: {e.details() if hasattr(e, 'details') else str(e)}"))
            except Exception as e:
                if not stop_event.is_set():
                    logger.error("UART reader error: %s", e)
                    traceback.print_exc()
                    output_q.put(("error", "UART stream error occurred"))
            finally:
                # Close the UART port
                if stream_id and channel:
                    try:
                        stub_for_close = MtibV2Stub(channel)
                        stub_for_close.UartClose(UartCloseRequest(stream_id=stream_id), timeout=3)
                        logger.info("UART closed: %s/%s", node_id, port_name)
                    except Exception:
                        pass
                if channel:
                    try:
                        channel.close()
                    except Exception:
                        pass
                output_q.put(("done", None))

        def run_uart_stream():
            reader = threading.Thread(target=_blocking_uart_reader, daemon=True)
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

                    if msg_type == "opened":
                        socketio.emit("uart_opened", {"portName": port_name, "streamId": payload},
                                      room=sid, namespace="/kubernetes")
                    elif msg_type == "data":
                        socketio.emit("uart_data", {"portName": port_name, "data": payload},
                                      room=sid, namespace="/kubernetes")
                    elif msg_type == "error":
                        socketio.emit("uart_error", {"portName": port_name, "message": payload},
                                      room=sid, namespace="/kubernetes")
                        break
                    elif msg_type == "done":
                        break
            except Exception as e:
                logger.error("UART emit error: %s", e)
                traceback.print_exc()
            finally:
                stop_event.set()
                reader.join(timeout=5)
                with _lock:
                    _active_sessions.pop(session_key, None)

        socketio.start_background_task(run_uart_stream)

    @socketio.on("unsubscribe_uart", namespace="/kubernetes")
    def handle_unsubscribe_uart(data):
        node_id = data.get("nodeId", "")
        port_name = data.get("portName", "")
        sid = request.sid
        session_key = f"{sid}:{node_id}:{port_name}"

        with _lock:
            session = _active_sessions.pop(session_key, None)
        if session:
            stop_event = session.get("stop_event")
            if stop_event:
                stop_event.set()


def cleanup_uart_sessions(sid: str):
    """Clean up all UART sessions for a disconnected client."""
    with _lock:
        keys_to_remove = [k for k in _active_sessions if k.startswith(f"{sid}:")]
        sessions_to_clean = []
        for key in keys_to_remove:
            session = _active_sessions.pop(key, None)
            if session:
                sessions_to_clean.append(session)

    for session in sessions_to_clean:
        stop_event = session.get("stop_event")
        if stop_event:
            stop_event.set()
