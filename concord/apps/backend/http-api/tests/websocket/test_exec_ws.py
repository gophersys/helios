"""Tests for the /kubernetes namespace -- pod exec handlers.

Source: src/api/v2/system/exec.py
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

import src.api.v2.system.exec as exec_mod
from src.lib.permissions import Permissions

from .conftest import _FakeSocketIO, make_perm_set, mock_ws_context


# ---------------------------------------------------------------------------
#  Setup helper
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    exec_mod._active_sessions.clear()
    exec_mod.register_exec_handlers(fake_socketio)
    return fake_socketio


def _exec_start(sio, data):
    return sio.handlers[("exec_start", "/kubernetes")](data)


def _exec_input(sio, data):
    return sio.handlers[("exec_input", "/kubernetes")](data)


def _exec_resize(sio, data):
    return sio.handlers[("exec_resize", "/kubernetes")](data)


def _exec_stop(sio):
    return sio.handlers[("exec_stop", "/kubernetes")]()


# =====================================================================
#  EXEC_START -- authentication
# =====================================================================

class TestExecStartAuth:

    def test_no_token(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("exec_error", {"message": "Authentication required"})

    def test_invalid_token(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"token": "bad.token", "namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("exec_error", {"message": "Invalid or expired token"})

    def test_token_no_perm_set_id(self, fake_socketio, mock_db, token_no_perm_set):
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"token": token_no_perm_set, "namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("exec_error", {"message": "Authorization required"})

    def test_perm_set_not_found(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"token": valid_token, "namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with("exec_error", {"message": "Authorization required"})

    def test_system_view_insufficient(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_VIEW)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"token": valid_token, "namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with(
                "exec_error", {"message": "Insufficient permissions \u2014 system:manage required"}
            )

    def test_validation_manage_insufficient(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.VALIDATION_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            _exec_start(sio, {"token": valid_token, "namespace": "ns", "pod": "p", "container": "c"})
            ctx.emit.assert_called_once_with(
                "exec_error", {"message": "Insufficient permissions \u2014 system:manage required"}
            )


# =====================================================================
#  EXEC_START -- parameter validation
# =====================================================================

class TestExecStartParams:

    def test_missing_namespace(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            with patch.object(exec_mod, "log_audit"):
                _exec_start(sio, {"token": valid_token, "pod": "p", "container": "c"})
            ctx.emit.assert_called_with("exec_error", {"message": "Missing namespace, pod, or container"})

    def test_missing_pod(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            with patch.object(exec_mod, "log_audit"):
                _exec_start(sio, {"token": valid_token, "namespace": "ns", "container": "c"})
            ctx.emit.assert_called_with("exec_error", {"message": "Missing namespace, pod, or container"})

    def test_missing_container(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod) as ctx:
            with patch.object(exec_mod, "log_audit"):
                _exec_start(sio, {"token": valid_token, "namespace": "ns", "pod": "p"})
            ctx.emit.assert_called_with("exec_error", {"message": "Missing namespace, pod, or container"})


# =====================================================================
#  EXEC_START -- success (spawns background task)
# =====================================================================

class TestExecStartSuccess:

    def test_spawns_task(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod, sid="sid-1") as ctx:
            with patch.object(exec_mod, "log_audit") as mock_audit:
                _exec_start(sio, {
                    "token": valid_token,
                    "namespace": "staging",
                    "pod": "web-1",
                    "container": "app",
                    "command": ["/bin/bash"],
                })
                assert len(sio._background_tasks) == 1
                mock_audit.assert_called_once()

    def test_default_command(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "log_audit") as mock_audit:
                _exec_start(sio, {
                    "token": valid_token,
                    "namespace": "ns",
                    "pod": "p",
                    "container": "c",
                })
                assert mock_audit.call_args[0][3]["command"] == ["/bin/sh"]


# =====================================================================
#  EXEC_START -- concurrent limit
# =====================================================================

class TestExecConcurrentLimit:

    def test_over_limit(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.SYSTEM_MANAGE)
        sio = _setup(fake_socketio)
        for i in range(exec_mod.MAX_CONCURRENT_EXEC):
            exec_mod._active_sessions[f"sid-{i}"] = threading.Event()

        with mock_ws_context(exec_mod, sid="sid-new") as ctx:
            with patch.object(exec_mod, "log_audit"):
                _exec_start(sio, {
                    "token": valid_token,
                    "namespace": "ns",
                    "pod": "p",
                    "container": "c",
                })
            ctx.emit.assert_called_with("exec_error", {"message": "Too many concurrent exec sessions"})


# =====================================================================
#  EXEC_INPUT
# =====================================================================

class TestExecInput:

    def test_forwards_data(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        mock_stream = MagicMock()
        mock_stream.is_open.return_value = True
        exec_mod._active_sessions["sid-1:stream"] = mock_stream

        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "tpool") as mock_tpool:
                _exec_input(sio, {"data": "ls\n"})
                mock_tpool.execute.assert_called_once_with(mock_stream.write_stdin, "ls\n")

    def test_no_stream_is_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "tpool") as mock_tpool:
                _exec_input(sio, {"data": "ls\n"})
                mock_tpool.execute.assert_not_called()

    def test_closed_stream_is_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        mock_stream = MagicMock()
        mock_stream.is_open.return_value = False
        exec_mod._active_sessions["sid-1:stream"] = mock_stream

        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "tpool") as mock_tpool:
                _exec_input(sio, {"data": "ls\n"})
                mock_tpool.execute.assert_not_called()


# =====================================================================
#  EXEC_RESIZE
# =====================================================================

class TestExecResize:

    def test_sends_dimensions(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        mock_stream = MagicMock()
        mock_stream.is_open.return_value = True
        exec_mod._active_sessions["sid-1:stream"] = mock_stream

        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "tpool") as mock_tpool:
                _exec_resize(sio, {"cols": 120, "rows": 40})
                mock_tpool.execute.assert_called_once_with(
                    mock_stream.write_channel, 4, '{"Width":120,"Height":40}'
                )

    def test_default_dimensions(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        mock_stream = MagicMock()
        mock_stream.is_open.return_value = True
        exec_mod._active_sessions["sid-1:stream"] = mock_stream

        with mock_ws_context(exec_mod, sid="sid-1"):
            with patch.object(exec_mod, "tpool") as mock_tpool:
                _exec_resize(sio, {})
                mock_tpool.execute.assert_called_once_with(
                    mock_stream.write_channel, 4, '{"Width":80,"Height":24}'
                )


# =====================================================================
#  EXEC_STOP
# =====================================================================

class TestExecStop:

    def test_sets_event(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        stop = threading.Event()
        exec_mod._active_sessions["sid-1"] = stop

        with mock_ws_context(exec_mod, sid="sid-1"):
            _exec_stop(sio)
        assert stop.is_set()

    def test_no_session_is_noop(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(exec_mod, sid="sid-1"):
            _exec_stop(sio)  # No raise


# =====================================================================
#  CLEANUP_EXEC_SESSION
# =====================================================================

class TestCleanupExecSession:

    def test_removes_session_and_stream(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        stop = threading.Event()
        exec_mod._active_sessions["sid-1"] = stop
        exec_mod._active_sessions["sid-1:stream"] = MagicMock()

        exec_mod.cleanup_exec_session("sid-1")

        assert "sid-1" not in exec_mod._active_sessions
        assert "sid-1:stream" not in exec_mod._active_sessions
        assert stop.is_set()

    def test_nonexistent_sid_is_noop(self, fake_socketio, mock_db):
        _setup(fake_socketio)
        exec_mod.cleanup_exec_session("nonexistent")
