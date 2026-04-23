"""Tests for the /kubernetes namespace -- ICLE device subscription handlers.

Source: src/api/v2/system/observability_ws.py (register_icle_handlers, bottom half)
        src/api/v2/icle/heartbeat.py (emit_icle_update)
"""

import types as stdlib_types
from unittest.mock import MagicMock

import pytest

import src.api.v2.system.observability_ws as obs_mod

from .conftest import _FakeSocketIO, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    obs_mod._icle_subscribers.clear()
    obs_mod.register_icle_handlers(fake_socketio)
    return fake_socketio


def _subscribe(sio, data):
    return sio.handlers[("subscribe_icle", "/kubernetes")](data)


def _unsubscribe(sio, data):
    return sio.handlers[("unsubscribe_icle", "/kubernetes")](data)


# =====================================================================
#  SUBSCRIBE_ICLE
# =====================================================================

class TestSubscribeIcle:

    def test_subscribe_specific_device_ok(self, fake_socketio, mock_db):
        mock_db.icledevice.find_unique.return_value = stdlib_types.SimpleNamespace(id="dev-1")
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"deviceId": "dev-1"})
            ctx.emit.assert_called_once_with("icle_subscribed", {"deviceId": "dev-1", "subscribed": True})
        assert "sid-1" in obs_mod._icle_subscribers
        assert "dev-1" in obs_mod._icle_subscribers["sid-1"]

    def test_subscribe_wildcard_no_device_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {})
            ctx.emit.assert_called_once_with("icle_subscribed", {"deviceId": "*", "subscribed": True})
        assert "*" in obs_mod._icle_subscribers["sid-1"]

    def test_subscribe_explicit_wildcard(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"deviceId": "*"})
            ctx.emit.assert_called_once_with("icle_subscribed", {"deviceId": "*", "subscribed": True})
        assert "*" in obs_mod._icle_subscribers["sid-1"]

    def test_subscribe_invalid_device_id_type(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"deviceId": 123})
            ctx.emit.assert_called_once_with("icle_error", {"deviceId": "", "message": "Invalid deviceId"})

    def test_subscribe_device_id_too_long(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"deviceId": "x" * 256})
            ctx.emit.assert_called_once_with("icle_error", {"deviceId": "", "message": "deviceId too long"})

    def test_subscribe_device_not_found(self, fake_socketio, mock_db):
        mock_db.icledevice.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"deviceId": "nonexistent"})
            ctx.emit.assert_called_once_with(
                "icle_error", {"deviceId": "nonexistent", "message": "Device not found"}
            )

    def test_subscribe_multiple_devices(self, fake_socketio, mock_db):
        mock_db.icledevice.find_unique.return_value = stdlib_types.SimpleNamespace(id="dev-1")
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="sid-1"):
            _subscribe(sio, {"deviceId": "dev-1"})
            mock_db.icledevice.find_unique.return_value = stdlib_types.SimpleNamespace(id="dev-2")
            _subscribe(sio, {"deviceId": "dev-2"})
        assert obs_mod._icle_subscribers["sid-1"] == {"dev-1", "dev-2"}


# =====================================================================
#  UNSUBSCRIBE_ICLE
# =====================================================================

class TestUnsubscribeIcle:

    def test_unsubscribe_specific_device(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"dev-1", "dev-2"}
        with mock_ws_context(obs_mod, sid="sid-1"):
            _unsubscribe(sio, {"deviceId": "dev-1"})
        assert "dev-1" not in obs_mod._icle_subscribers["sid-1"]
        assert "dev-2" in obs_mod._icle_subscribers["sid-1"]

    def test_unsubscribe_wildcard_clears_all(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"dev-1", "dev-2", "*"}
        with mock_ws_context(obs_mod, sid="sid-1"):
            _unsubscribe(sio, {"deviceId": "*"})
        assert "sid-1" not in obs_mod._icle_subscribers

    def test_unsubscribe_last_device_removes_sid(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"dev-1"}
        with mock_ws_context(obs_mod, sid="sid-1"):
            _unsubscribe(sio, {"deviceId": "dev-1"})
        assert "sid-1" not in obs_mod._icle_subscribers

    def test_unsubscribe_unknown_sid_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(obs_mod, sid="unknown-sid"):
            _unsubscribe(sio, {"deviceId": "dev-1"})

    def test_unsubscribe_no_device_id_defaults_wildcard(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"*", "dev-1"}
        with mock_ws_context(obs_mod, sid="sid-1"):
            _unsubscribe(sio, {})
        # device_id defaults to "*", which triggers .clear() -> removes sid entry
        assert "sid-1" not in obs_mod._icle_subscribers


# =====================================================================
#  CLEANUP_ICLE_SESSIONS
# =====================================================================

class TestCleanupIcleSessions:

    def test_cleanup_removes_sid(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"dev-1", "dev-2"}
        obs_mod._icle_subscribers["sid-2"] = {"dev-3"}

        obs_mod.cleanup_icle_sessions("sid-1")

        assert "sid-1" not in obs_mod._icle_subscribers
        assert "sid-2" in obs_mod._icle_subscribers

    def test_cleanup_nonexistent_noop(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        obs_mod.cleanup_icle_sessions("no-such-sid")


# =====================================================================
#  GET_ICLE_SUBSCRIBERS
# =====================================================================

class TestGetIcleSubscribers:

    def test_returns_reference(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        obs_mod._icle_subscribers["sid-1"] = {"dev-1"}
        assert obs_mod.get_icle_subscribers() is obs_mod._icle_subscribers


# =====================================================================
#  EMIT_ICLE_UPDATE (from heartbeat.py)
# =====================================================================

class TestEmitIcleUpdate:

    def test_emit_with_socketio(self, mock_db):
        from src.api.v2.icle.heartbeat import emit_icle_update, set_socketio
        fake_sio = MagicMock()
        set_socketio(fake_sio)
        try:
            data = {"id": "1", "deviceId": "ICLE-001", "status": "ONLINE"}
            emit_icle_update(data)
            fake_sio.emit.assert_called_once_with("icle_update", data, namespace="/kubernetes")
        finally:
            set_socketio(None)

    def test_emit_no_socketio_noop(self, mock_db):
        from src.api.v2.icle.heartbeat import emit_icle_update, set_socketio
        set_socketio(None)
        emit_icle_update({"id": "1"})

    def test_emit_exception_handled(self, mock_db):
        from src.api.v2.icle.heartbeat import emit_icle_update, set_socketio
        mock_sio = MagicMock()
        mock_sio.emit.side_effect = Exception("socket error")
        set_socketio(mock_sio)
        try:
            emit_icle_update({"id": "1"})  # Should not raise
        finally:
            set_socketio(None)
