"""Tests for the /kubernetes namespace -- UART streaming handlers.

Source: src/api/v2/system/uart.py
"""

import threading
import types as stdlib_types
from unittest.mock import MagicMock

import pytest

import src.api.v2.system.uart as uart_mod

from .conftest import _FakeSocketIO, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    uart_mod._active_sessions.clear()
    uart_mod.register_uart_handlers(fake_socketio)
    return fake_socketio


def _subscribe(sio, data):
    return sio.handlers[("subscribe_uart", "/kubernetes")](data)


def _unsubscribe(sio, data):
    return sio.handlers[("unsubscribe_uart", "/kubernetes")](data)


# =====================================================================
#  SUBSCRIBE_UART -- input validation
# =====================================================================

class TestSubscribeUart:

    def test_missing_node_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Missing nodeId or portName"}
            )

    def test_missing_port_name(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "", "message": "Missing nodeId or portName"}
            )

    def test_missing_both(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {})
            assert ctx.emit.called
            assert "Missing nodeId or portName" in ctx.emit.call_args[0][1]["message"]

    def test_already_subscribed(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        uart_mod._active_sessions["sid-1:node-1:uart0"] = {"stop_event": threading.Event()}
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Already subscribed to this port"}
            )

    def test_concurrent_limit_exceeded(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        for i in range(uart_mod.MAX_CONCURRENT_UART):
            uart_mod._active_sessions[f"other-sid:{i}:port{i}"] = {"stop_event": threading.Event()}

        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Too many active UART streams"}
            )

    def test_node_not_found(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Node not found or no IP address"}
            )

    def test_node_no_ip(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1", ipAddress=None)
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Node not found or no IP address"}
            )

    def test_db_lookup_error(self, fake_socketio, mock_db):
        mock_db.node.find_unique.side_effect = Exception("DB down")
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
            ctx.emit.assert_called_once_with(
                "uart_error", {"portName": "uart0", "message": "Failed to look up node"}
            )

    def test_successful_subscribe_spawns_task(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(
            id="node-1", ipAddress="10.0.0.1"
        )
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1"):
            _subscribe(sio, {"nodeId": "node-1", "portName": "uart0", "baud": 9600})

        assert len(sio._background_tasks) == 1
        assert "sid-1:node-1:uart0" in uart_mod._active_sessions


# =====================================================================
#  UNSUBSCRIBE_UART
# =====================================================================

class TestUnsubscribeUart:

    def test_unsubscribe_stops_stream(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        stop = threading.Event()
        uart_mod._active_sessions["sid-1:node-1:uart0"] = {"stop_event": stop}

        with mock_ws_context(uart_mod, sid="sid-1"):
            _unsubscribe(sio, {"nodeId": "node-1", "portName": "uart0"})
        assert stop.is_set()
        assert "sid-1:node-1:uart0" not in uart_mod._active_sessions

    def test_unsubscribe_nonexistent_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(uart_mod, sid="sid-1"):
            _unsubscribe(sio, {"nodeId": "node-1", "portName": "uart0"})


# =====================================================================
#  CLEANUP_UART_SESSIONS
# =====================================================================

class TestCleanupUartSessions:

    def test_cleanup_removes_all_for_sid(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        stop1 = threading.Event()
        stop2 = threading.Event()
        stop_other = threading.Event()
        uart_mod._active_sessions["sid-1:node-1:uart0"] = {"stop_event": stop1}
        uart_mod._active_sessions["sid-1:node-2:uart1"] = {"stop_event": stop2}
        uart_mod._active_sessions["sid-2:node-1:uart0"] = {"stop_event": stop_other}

        uart_mod.cleanup_uart_sessions("sid-1")

        assert stop1.is_set()
        assert stop2.is_set()
        assert not stop_other.is_set()
        assert "sid-1:node-1:uart0" not in uart_mod._active_sessions
        assert "sid-2:node-1:uart0" in uart_mod._active_sessions

    def test_cleanup_nonexistent_sid_noop(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        uart_mod.cleanup_uart_sessions("nonexistent")
