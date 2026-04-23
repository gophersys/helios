"""Shared fixtures for WebSocket handler tests.

All WS handlers are tested by calling the inner handler functions directly
with mocked flask_socketio primitives (emit, join_room, leave_room, disconnect)
and mocked flask.request.  This avoids needing a live SocketIO server or eventlet.
"""

import types as stdlib_types
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.lib.permissions import Permissions
from src.services.auth.jwt import create_token


# ---------------------------------------------------------------------------
#  Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_token():
    """A valid JWT token with a known permissionSetId."""
    return create_token(
        user_id="ws-test-user",
        email="ws@example.com",
        name="WS Tester",
        permission_set_id="ws-perm-set-id",
    )


@pytest.fixture
def token_no_perm_set():
    """A valid JWT with permissionSetId=None."""
    return create_token(
        user_id="ws-test-user",
        email="ws@example.com",
        name="WS Tester",
        permission_set_id=None,
    )


# ---------------------------------------------------------------------------
#  Permission-set factory
# ---------------------------------------------------------------------------

def make_perm_set(*permissions: str):
    """Create a SimpleNamespace that looks like a Prisma PermissionSet row."""
    return stdlib_types.SimpleNamespace(
        id="ws-perm-set-id",
        name="Test Role",
        permissions=list(permissions),
    )


# ---------------------------------------------------------------------------
#  Mock SocketIO — used as the `socketio` argument when registering handlers
# ---------------------------------------------------------------------------

class _FakeSocketIO:
    """Minimal stand-in for flask_socketio.SocketIO.

    Captures the handler functions registered via ``@socketio.on(event, namespace=ns)``
    so tests can invoke them directly.
    """

    def __init__(self):
        self.handlers: dict[tuple[str, str], callable] = {}
        self.emitted: list[tuple] = []
        self._background_tasks: list[callable] = []

    # Decorator used by handler registration ---------------------------------
    def on(self, event: str, namespace: str = "/"):
        def decorator(fn):
            self.handlers[(event, namespace)] = fn
            return fn
        return decorator

    # Called by handlers that spawn background work --------------------------
    def start_background_task(self, fn, *args, **kwargs):
        # Store but don't run — background threads aren't needed for unit tests
        self._background_tasks.append((fn, args, kwargs))

    # Server-side emit used inside background tasks --------------------------
    def emit(self, event, data, **kwargs):
        self.emitted.append((event, data, kwargs))


@pytest.fixture
def fake_socketio():
    """Provide a fresh _FakeSocketIO for each test."""
    return _FakeSocketIO()


# ---------------------------------------------------------------------------
#  Module-level mock helpers
# ---------------------------------------------------------------------------

@contextmanager
def mock_ws_context(module, sid="sid-1"):
    """Context manager that patches request, emit, join_room, leave_room on a WS module.

    Usage:
        with mock_ws_context(my_module, sid="sid-1") as ctx:
            # call handler ...
            assert ctx.emit.called
            assert ctx.join_room.called

    The ``request`` proxy from Flask cannot be patched via ``@patch()`` because
    the mock introspection triggers proxy resolution outside request context.
    ``patch.object(mod, 'request', new=...)`` avoids this by skipping introspection.
    """
    mock_req = MagicMock()
    mock_req.sid = sid
    mock_emit = MagicMock()
    mock_join = MagicMock()
    mock_leave = MagicMock()

    import unittest.mock as _m

    patches = [
        _m.patch.object(module, "request", new=mock_req),
    ]
    # Only patch if the module imports them at the top level
    if hasattr(module, "emit"):
        patches.append(_m.patch.object(module, "emit", new=mock_emit))
    if hasattr(module, "join_room"):
        patches.append(_m.patch.object(module, "join_room", new=mock_join))
    if hasattr(module, "leave_room"):
        patches.append(_m.patch.object(module, "leave_room", new=mock_leave))

    class _Ctx:
        request = mock_req
        emit = mock_emit
        join_room = mock_join
        leave_room = mock_leave

    for p in patches:
        p.start()
    try:
        yield _Ctx()
    finally:
        for p in patches:
            p.stop()
