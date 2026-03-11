"""Tests for the /kubernetes namespace -- logic analyzer streaming handlers.

Source: src/api/v2/system/analyzer_stream.py
"""

import threading
import types as stdlib_types
from unittest.mock import MagicMock

import pytest

import src.api.v2.system.analyzer_stream as analyzer_mod

from .conftest import _FakeSocketIO, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    analyzer_mod._active_streams.clear()
    analyzer_mod.register_analyzer_handlers(fake_socketio)
    return fake_socketio


def _subscribe(sio, data):
    return sio.handlers[("subscribe_analyzer", "/kubernetes")](data)


def _unsubscribe(sio, data):
    return sio.handlers[("unsubscribe_analyzer", "/kubernetes")](data)


# =====================================================================
#  SUBSCRIBE_ANALYZER -- input validation
# =====================================================================

class TestSubscribeAnalyzer:

    def test_missing_node_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "", "message": "Missing or invalid nodeId"}
            )

    def test_non_string_node_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": 123, "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "", "message": "Missing or invalid nodeId"}
            )

    def test_node_id_too_long(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "x" * 256, "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "", "message": "nodeId too long"}
            )

    def test_missing_capture_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "", "message": "Missing or invalid captureId"}
            )

    def test_non_string_capture_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": 42})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "", "message": "Missing or invalid captureId"}
            )

    def test_capture_id_too_long(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "c" * 256})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "c" * 256, "message": "captureId too long"}
            )

    def test_already_subscribed(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        analyzer_mod._active_streams["sid-1:cap-1"] = {"stop_event": threading.Event()}
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "cap-1", "message": "Already subscribed to this capture"}
            )

    def test_concurrent_limit_exceeded(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        for i in range(analyzer_mod.MAX_CONCURRENT_STREAMS):
            analyzer_mod._active_streams[f"other:{i}"] = {"stop_event": threading.Event()}

        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "cap-1", "message": "Too many active analyzer streams"}
            )

    def test_node_not_found(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "cap-1", "message": "Node not found or no IP address"}
            )

    def test_node_no_ip(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="n1", ipAddress=None)
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "cap-1", "message": "Node not found or no IP address"}
            )

    def test_db_error(self, fake_socketio, mock_db):
        mock_db.node.find_unique.side_effect = Exception("boom")
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})
            ctx.emit.assert_called_once_with(
                "analyzer_error", {"captureId": "cap-1", "message": "Failed to look up node"}
            )

    def test_successful_subscribe_spawns_task(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(
            id="node-1", ipAddress="10.0.0.1"
        )
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1"):
            _subscribe(sio, {"nodeId": "node-1", "captureId": "cap-1"})

        assert len(sio._background_tasks) == 1
        assert "sid-1:cap-1" in analyzer_mod._active_streams


# =====================================================================
#  UNSUBSCRIBE_ANALYZER
# =====================================================================

class TestUnsubscribeAnalyzer:

    def test_unsubscribe_stops_stream(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        stop = threading.Event()
        analyzer_mod._active_streams["sid-1:cap-1"] = {"stop_event": stop}

        with mock_ws_context(analyzer_mod, sid="sid-1"):
            _unsubscribe(sio, {"captureId": "cap-1"})
        assert stop.is_set()
        assert "sid-1:cap-1" not in analyzer_mod._active_streams

    def test_unsubscribe_nonexistent_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(analyzer_mod, sid="sid-1"):
            _unsubscribe(sio, {"captureId": "cap-1"})


# =====================================================================
#  CLEANUP_ANALYZER_STREAMS
# =====================================================================

class TestCleanupAnalyzerStreams:

    def test_cleanup_stops_all_for_sid(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        stop1 = threading.Event()
        stop2 = threading.Event()
        stop_other = threading.Event()
        analyzer_mod._active_streams["sid-1:cap-a"] = {"stop_event": stop1}
        analyzer_mod._active_streams["sid-1:cap-b"] = {"stop_event": stop2}
        analyzer_mod._active_streams["sid-2:cap-a"] = {"stop_event": stop_other}

        analyzer_mod.cleanup_analyzer_streams("sid-1")

        assert stop1.is_set()
        assert stop2.is_set()
        assert not stop_other.is_set()
        assert "sid-1:cap-a" not in analyzer_mod._active_streams
        assert "sid-2:cap-a" in analyzer_mod._active_streams

    def test_cleanup_nonexistent_sid_noop(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        analyzer_mod.cleanup_analyzer_streams("no-such-sid")
