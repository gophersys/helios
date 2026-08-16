"""Shared helpers for the builds module."""

_socketio = None


def set_ci_socketio(sio):
    """Store the SocketIO instance for CI event emission."""
    global _socketio
    _socketio = sio


def _emit_ci_event(event: str, data: dict):
    """Emit a CI event via WebSocket if SocketIO is available."""
    if _socketio:
        _socketio.emit(event, data, namespace="/kubernetes")
