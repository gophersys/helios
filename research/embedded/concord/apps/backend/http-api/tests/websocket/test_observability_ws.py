"""Tests for the /kubernetes namespace -- MTIB observability handlers.

Source: src/api/v2/system/observability_ws.py
"""

import types as stdlib_types
from unittest.mock import MagicMock, patch

import pytest

import src.api.v2.system.observability_ws as obs_mod

from .conftest import _FakeSocketIO, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    obs_mod.register_observability_handlers(fake_socketio)
    return fake_socketio


def _subscribe(sio, data):
    return sio.handlers[("subscribe_observability", "/kubernetes")](data)


def _unsubscribe(sio, data):
    return sio.handlers[("unsubscribe_observability", "/kubernetes")](data)


# =====================================================================
#  Mock observability service
# =====================================================================

def _make_mock_svc(subscriber_count=0):
    svc = MagicMock()
    svc.get_subscriber_count.return_value = subscriber_count
    svc.register_subscriber = MagicMock()
    svc.unregister_subscriber = MagicMock()
    svc.cleanup_subscribers = MagicMock()
    return svc


# =====================================================================
#  SUBSCRIBE_OBSERVABILITY -- input validation
# =====================================================================

class TestSubscribeObservability:

    def test_missing_node_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "", "message": "Missing or invalid nodeId"}
            )

    def test_non_string_node_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {"nodeId": 42})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "", "message": "Missing or invalid nodeId"}
            )

    def test_node_id_too_long(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {"nodeId": "x" * 256})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "", "message": "nodeId too long"}
            )

    def test_too_many_features(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {"nodeId": "node-1", "features": ["power"] * 11})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "node-1", "message": "Too many features requested"}
            )

    def test_invalid_feature_name(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {"nodeId": "node-1", "features": ["power", "invalid_feature"]})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "node-1", "message": "Invalid feature name"}
            )

    def test_node_not_found(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service"):
                _subscribe(sio, {"nodeId": "node-1"})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "node-1", "message": "Node not found"}
            )

    def test_service_not_available(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1")
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service", return_value=None):
                _subscribe(sio, {"nodeId": "node-1"})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "node-1", "message": "Observability service not available"}
            )

    def test_subscriber_limit_exceeded(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1")
        svc = _make_mock_svc(subscriber_count=50)
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            with patch.object(obs_mod, "get_observability_service", return_value=svc):
                _subscribe(sio, {"nodeId": "node-1"})
            ctx.emit.assert_called_once_with(
                "observability_error", {"nodeId": "node-1", "message": "Too many active subscriptions"}
            )

    def test_subscribe_success_default_features(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1")
        svc = _make_mock_svc()
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            with patch.object(obs_mod, "get_observability_service", return_value=svc):
                _subscribe(sio, {"nodeId": "node-1"})

        svc.register_subscriber.assert_called_once()
        args = svc.register_subscriber.call_args[0]
        assert args[0] == "sid-1"
        assert args[1] == "node-1"
        assert args[2] == ["power", "gpio", "adc", "uart", "system", "clients"]

    def test_subscribe_success_explicit_features(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1")
        svc = _make_mock_svc()
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            with patch.object(obs_mod, "get_observability_service", return_value=svc):
                _subscribe(sio, {"nodeId": "node-1", "features": ["power", "gpio"]})

        args = svc.register_subscriber.call_args[0]
        assert args[2] == ["power", "gpio"]

    def test_subscribe_passes_callable_emitter(self, fake_socketio, mock_db):
        mock_db.node.find_unique.return_value = stdlib_types.SimpleNamespace(id="node-1")
        svc = _make_mock_svc()
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            with patch.object(obs_mod, "get_observability_service", return_value=svc):
                _subscribe(sio, {"nodeId": "node-1"})

        emit_fn = svc.register_subscriber.call_args[0][3]
        assert callable(emit_fn)

        # Call the emitter and verify it uses socketio.emit
        emit_fn({"nodeId": "node-1", "timestamp": 1234})
        assert len(sio.emitted) == 1
        event, data, kwargs = sio.emitted[0]
        assert event == "observability_update"
        assert data["nodeId"] == "node-1"
        assert kwargs["room"] == "sid-1"
        assert kwargs["namespace"] == "/kubernetes"


# =====================================================================
#  UNSUBSCRIBE_OBSERVABILITY
# =====================================================================

class TestUnsubscribeObservability:

    def test_unsubscribe_calls_service(self, fake_socketio, mock_db):
        svc = _make_mock_svc()
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            with patch.object(obs_mod, "get_observability_service", return_value=svc):
                _unsubscribe(sio, {"nodeId": "node-1"})
        svc.unregister_subscriber.assert_called_once_with("sid-1", "node-1")

    def test_unsubscribe_no_service_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            with patch.object(obs_mod, "get_observability_service", return_value=None):
                _unsubscribe(sio, {"nodeId": "node-1"})


# =====================================================================
#  CLEANUP_OBSERVABILITY_SESSIONS
# =====================================================================

class TestCleanupObservabilitySessions:

    def test_cleanup_calls_service(self, fake_socketio, mock_db):
        svc = _make_mock_svc()
        with patch.object(obs_mod, "get_observability_service", return_value=svc):
            obs_mod.cleanup_observability_sessions("sid-1")
        svc.cleanup_subscribers.assert_called_once_with("sid-1")

    def test_cleanup_no_service_noop(self, fake_socketio, mock_db):
        with patch.object(obs_mod, "get_observability_service", return_value=None):
            obs_mod.cleanup_observability_sessions("sid-1")
