"""Tests for the /kubernetes namespace -- log streaming handlers.

Source: src/api/v2/system/logs.py
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

import src.api.v2.system.logs as logs_mod
from src.lib.permissions import Permissions

from .conftest import _FakeSocketIO, make_perm_set, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    logs_mod._active_streams.clear()
    logs_mod.register_log_handlers(fake_socketio)
    return fake_socketio


def _connect(sio, auth):
    return sio.handlers[("connect", "/kubernetes")](auth)


def _subscribe(sio, data):
    return sio.handlers[("subscribe_logs", "/kubernetes")](data)


def _unsubscribe(sio, data):
    return sio.handlers[("unsubscribe_logs", "/kubernetes")](data)


def _k8s_disconnect(sio):
    return sio.handlers[("disconnect", "/kubernetes")]()


# =====================================================================
#  CONNECT -- JWT + system:view / system:manage
# =====================================================================

class TestKubernetesConnect:

    def test_connect_no_auth_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, None) is False

    def test_connect_empty_auth_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {}) is False

    def test_connect_no_token_field_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"other": "value"}) is False

    def test_connect_invalid_token_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": "bad.token.here"}) is False

    def test_connect_no_perm_set_id_returns_false(self, fake_socketio, mock_db, token_no_perm_set):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": token_no_perm_set}) is False

    def test_connect_perm_set_not_found_returns_false(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = None
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is False

    def test_connect_wrong_permissions_returns_false(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set("products:view")
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is False

    def test_connect_system_view_succeeds(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_VIEW)
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is None

    def test_connect_system_manage_succeeds(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is None


# =====================================================================
#  SUBSCRIBE_LOGS
# =====================================================================

class TestSubscribeLogs:

    def test_subscribe_missing_namespace(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("log_error", {"message": "Missing namespace, pod, or container"})

    def test_subscribe_missing_pod(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"namespace": "ns", "container": "c"})
            ctx.emit.assert_called_once_with("log_error", {"message": "Missing namespace, pod, or container"})

    def test_subscribe_missing_container(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"namespace": "ns", "pod": "p"})
            ctx.emit.assert_called_once_with("log_error", {"message": "Missing namespace, pod, or container"})

    def test_subscribe_valid_params_joins_room_and_spawns_task(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"namespace": "default", "pod": "web-1", "container": "app", "tailLines": 50})
            ctx.join_room.assert_called_once_with("pod-logs:default:web-1:app")
            assert len(sio._background_tasks) == 1

    def test_subscribe_bad_tail_lines_defaults_to_100(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"namespace": "ns", "pod": "p", "container": "c", "tailLines": -5})
            ctx.join_room.assert_called_once()

    def test_subscribe_exceeds_concurrent_limit(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        for i in range(logs_mod.MAX_CONCURRENT_STREAMS):
            logs_mod._active_streams[f"fake-key-{i}"] = threading.Event()

        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("log_error", {"message": "Too many active log streams"})
            ctx.join_room.assert_not_called()


# =====================================================================
#  UNSUBSCRIBE_LOGS
# =====================================================================

class TestUnsubscribeLogs:

    def test_unsubscribe_stops_stream_and_leaves_room(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        stop = threading.Event()
        logs_mod._active_streams["sid-1:pod-logs:ns:p:c"] = stop

        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _unsubscribe(sio, {"namespace": "ns", "pod": "p", "container": "c"})
            assert stop.is_set()
            assert "sid-1:pod-logs:ns:p:c" not in logs_mod._active_streams
            ctx.leave_room.assert_called_once_with("pod-logs:ns:p:c")

    def test_unsubscribe_nonexistent_stream_still_leaves_room(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(logs_mod, sid="sid-1") as ctx:
            _unsubscribe(sio, {"namespace": "ns", "pod": "p", "container": "c"})
            ctx.leave_room.assert_called_once()


# =====================================================================
#  DISCONNECT -- cleanup all streams for the sid
# =====================================================================

class TestKubernetesDisconnect:

    def test_disconnect_cleans_all_streams(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)

        stop1 = threading.Event()
        stop2 = threading.Event()
        stop_other = threading.Event()
        logs_mod._active_streams["sid-1:room-a"] = stop1
        logs_mod._active_streams["sid-1:room-b"] = stop2
        logs_mod._active_streams["sid-2:room-c"] = stop_other

        with mock_ws_context(logs_mod, sid="sid-1"):
            # The disconnect handler uses lazy imports: `from .exec import cleanup_exec_session`
            # Patch the functions at their source modules so the lazy imports find mocks.
            with patch("src.api.v2.system.logs.cleanup_exec_session") as m_exec, \
                 patch("src.api.v2.system.logs.cleanup_observability_sessions") as m_obs:
                _k8s_disconnect(sio)

                assert stop1.is_set()
                assert stop2.is_set()
                assert "sid-1:room-a" not in logs_mod._active_streams
                assert "sid-1:room-b" not in logs_mod._active_streams
                assert "sid-2:room-c" in logs_mod._active_streams

                m_exec.assert_called_once_with("sid-1")
                m_obs.assert_called_once_with("sid-1")
