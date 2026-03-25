"""Tests for the /validation WebSocket namespace.

Source: src/api/v2/sessions/validation_ws.py
"""

import types as stdlib_types
from unittest.mock import MagicMock

import pytest

import src.api.v2.sessions.validation_ws as ws_mod
from src.lib.permissions import Permissions
from src.services.auth.jwt import create_token

from .conftest import _FakeSocketIO, make_perm_set, mock_ws_context


# ---------------------------------------------------------------------------
#  Helpers — register handlers & invoke
# ---------------------------------------------------------------------------

def _setup(fake_socketio: _FakeSocketIO):
    """Register handlers and return the socketio fixture."""
    ws_mod.register_validation_ws_handlers(fake_socketio)
    return fake_socketio


def _connect(sio: _FakeSocketIO, auth):
    return sio.handlers[("connect", "/validation")](auth)


def _subscribe(sio: _FakeSocketIO, data):
    return sio.handlers[("subscribe_run", "/validation")](data)


def _unsubscribe(sio: _FakeSocketIO, data):
    return sio.handlers[("unsubscribe_run", "/validation")](data)


def _disconnect(sio: _FakeSocketIO):
    return sio.handlers[("disconnect", "/validation")]()


# =====================================================================
#  CONNECT — authentication & authorisation
# =====================================================================

class TestValidationConnect:

    def test_connect_no_auth_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, None) is False

    def test_connect_empty_auth_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {}) is False

    def test_connect_missing_token_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"other": "field"}) is False

    def test_connect_invalid_token_returns_false(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": "this.is.not.valid"}) is False

    def test_connect_expired_token_returns_false(self, fake_socketio, mock_db):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from config import env_config

        payload = {
            "sub": "u1", "email": "e@e.com", "name": "N",
            "permissionSetId": "ps1",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired = pyjwt.encode(payload, env_config.JWT_SECRET_KEY, algorithm="HS256")
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": expired}) is False

    def test_connect_token_no_permission_set_id_returns_false(self, fake_socketio, mock_db, token_no_perm_set):
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": token_no_perm_set}) is False

    def test_connect_permission_set_not_found_returns_false(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = None
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is False

    def test_connect_insufficient_permissions_returns_false(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set("products:view")
        sio = _setup(fake_socketio)
        assert _connect(sio, {"token": valid_token}) is False

    def test_connect_with_validation_view_succeeds(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.VALIDATION_VIEW)
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod, sid="sid-1"):
            assert _connect(sio, {"token": valid_token}) is None

    def test_connect_with_validation_manage_succeeds(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(Permissions.VALIDATION_MANAGE)
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod, sid="sid-1"):
            assert _connect(sio, {"token": valid_token}) is None

    def test_connect_with_both_permissions_succeeds(self, fake_socketio, mock_db, valid_token):
        mock_db.permissionset.find_unique.return_value = make_perm_set(
            Permissions.VALIDATION_VIEW, Permissions.VALIDATION_MANAGE,
        )
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod, sid="sid-1"):
            assert _connect(sio, {"token": valid_token}) is None


# =====================================================================
#  SUBSCRIBE_RUN
# =====================================================================

class TestSubscribeRun:

    def test_subscribe_valid_run(self, fake_socketio, mock_db):
        mock_db.session.find_unique.return_value = stdlib_types.SimpleNamespace(id="run-1")
        sio = _setup(fake_socketio)

        with mock_ws_context(ws_mod, sid="sid-1") as ctx:
            _subscribe(sio, {"runId": "run-1"})
            ctx.join_room.assert_called_once_with("run:run-1")
            ctx.emit.assert_called_once_with("subscribed", {"runId": "run-1"})

    def test_subscribe_missing_run_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _subscribe(sio, {})
            ctx.emit.assert_called_once_with("error", {"message": "Missing or invalid runId"})

    def test_subscribe_non_string_run_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _subscribe(sio, {"runId": 12345})
            ctx.emit.assert_called_once_with("error", {"message": "Missing or invalid runId"})

    def test_subscribe_empty_run_id(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _subscribe(sio, {"runId": ""})
            ctx.emit.assert_called_once_with("error", {"message": "Missing or invalid runId"})

    def test_subscribe_run_id_too_long(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _subscribe(sio, {"runId": "x" * 256})
            ctx.emit.assert_called_once_with("error", {"message": "runId too long"})

    def test_subscribe_run_not_found(self, fake_socketio, mock_db):
        mock_db.session.find_unique.return_value = None
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _subscribe(sio, {"runId": "nonexistent"})
            ctx.emit.assert_called_once_with("error", {"message": "Validation run not found"})


# =====================================================================
#  UNSUBSCRIBE_RUN
# =====================================================================

class TestUnsubscribeRun:

    def test_unsubscribe_valid(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod, sid="sid-1") as ctx:
            _unsubscribe(sio, {"runId": "run-1"})
            ctx.leave_room.assert_called_once_with("run:run-1")

    def test_unsubscribe_missing_run_id_does_nothing(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _unsubscribe(sio, {})
            ctx.leave_room.assert_not_called()

    def test_unsubscribe_non_string_run_id_does_nothing(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod) as ctx:
            _unsubscribe(sio, {"runId": 42})
            ctx.leave_room.assert_not_called()


# =====================================================================
#  DISCONNECT
# =====================================================================

class TestValidationDisconnect:

    def test_disconnect_completes(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        with mock_ws_context(ws_mod, sid="sid-1"):
            _disconnect(sio)  # No assertion beyond "doesn't raise"


# =====================================================================
#  EMIT_TO_RUN (helper called by reporter.py)
# =====================================================================

class TestEmitToRun:

    def test_emit_to_run_sends_to_correct_room(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        ws_mod.emit_to_run("validation_test_result", {"testId": "t1"}, "run-42")

        assert len(sio.emitted) == 1
        event, data, kwargs = sio.emitted[0]
        assert event == "validation_test_result"
        assert data == {"testId": "t1"}
        assert kwargs["namespace"] == "/validation"
        assert kwargs["room"] == "run:run-42"

    def test_emit_to_run_no_socketio_does_not_raise(self, mock_db):
        old = ws_mod._validation_socketio
        ws_mod._validation_socketio = None
        try:
            ws_mod.emit_to_run("event", {}, "run-1")
        finally:
            ws_mod._validation_socketio = old

    def test_get_validation_socketio_returns_instance(self, fake_socketio, mock_db):
        sio = _setup(fake_socketio)
        assert ws_mod.get_validation_socketio() is sio
