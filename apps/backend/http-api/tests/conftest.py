"""
Core test fixtures for the Concord HTTP API test suite.

Provides mock DB, auth helpers, Flask test client, and permission cache clearing.
"""

import os
import types as stdlib_types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# pytest_configure — set env vars BEFORE any source module imports
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Set all required environment variables before config/env.py loads."""
    env_vars = {
        "ENVIRONMENT": "test",
        "DELETE_ALL_KEY": "test-delete-key",
        "LOG_LEVEL": "10",
        "LOG_PATH": "/tmp/concord-test.log",
        "SERVER_PORT": "9001",
        "CORS_ORIGINS": "http://localhost:4200",
        "JWT_SECRET_KEY": "test-jwt-secret-key-for-testing",
        "CONCORD_API_HOST": "test.concord.local",
        "ASSETS_FOLDER": "/tmp/concord-test-assets",
        "STORAGE_URL": "http://localhost:9000",
        "STORAGE_ACCESS_KEY": "minioadmin",
        "STORAGE_SECRET_ACCESS_KEY": "minioadmin",
        "STORAGE_BUCKET_NAME": "test-bucket",
        "AUTH_SERVER_URL": "",
        "AUTH_SERVER_API_KEY": "",
    }
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# MockPrismaClient — lazy model mock creation
# ---------------------------------------------------------------------------

class MockModelClient:
    """Mock for a single Prisma model (e.g., db.product)."""

    def __init__(self):
        self.find_many = MagicMock(return_value=[])
        self.find_unique = MagicMock(return_value=None)
        self.find_first = MagicMock(return_value=None)
        self.create = MagicMock(return_value=None)
        self.update = MagicMock(return_value=None)
        self.delete = MagicMock(return_value=None)
        self.count = MagicMock(return_value=0)
        self.delete_many = MagicMock(return_value=None)
        self.create_many = MagicMock(return_value=None)
        self.update_many = MagicMock(return_value=None)


class MockPrismaClient:
    """Mock Prisma client that lazily creates model mocks via __getattr__."""

    def __init__(self):
        self._models = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._models:
            self._models[name] = MockModelClient()
        return self._models[name]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Provide a fresh MockPrismaClient and patch the module-level global."""
    client = MockPrismaClient()
    import src.services.database.prisma as prisma_module
    original = prisma_module.appPostgresClient
    prisma_module.appPostgresClient = client
    yield client
    prisma_module.appPostgresClient = original


@pytest.fixture
def auth_headers():
    """Generate real JWT auth headers using the test secret key."""
    from src.services.auth.jwt import create_token
    token = create_token(
        user_id="test-user-id",
        email="test@example.com",
        name="Test User",
        permission_set_id="test-perm-set-id",
    )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="function")
def app(mock_db):
    """Create a fresh Flask app with all v2 routes registered (no eventlet)."""
    from flask import Flask
    from importlib import reload
    import api.v2.router as router_module

    # Force reload the router module to get a fresh blueprint
    reload(router_module)

    test_app = Flask(__name__)
    test_app.config["TESTING"] = True

    mock_logger = MagicMock()
    mock_logger.add_filter = MagicMock()
    mock_socketio = MagicMock()

    router_module.register_v2_routes(mock_logger, test_app, mock_socketio)
    return test_app


@pytest.fixture
def client(app):
    """Flask test client for raw requests."""
    return app.test_client()


@pytest.fixture
def authed_client(client, auth_headers, mock_db):
    """
    Wrapper around the Flask test client that auto-injects auth headers
    and mocks permission checking to allow all permissions (superadmin).
    """
    # Mock the permission set lookup to return all permissions
    from src.lib.permissions import Permissions
    all_perms = list(Permissions.all())

    perm_set = stdlib_types.SimpleNamespace(
        id="test-perm-set-id",
        name="Test Admin",
        permissions=all_perms,
    )
    mock_db.permissionset.find_unique.return_value = perm_set

    class AuthedTestClient:
        """Wraps Flask test client to auto-inject auth headers."""

        def __init__(self, test_client, headers):
            self._client = test_client
            self._headers = headers

        def get(self, *args, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.get(*args, **kwargs)

        def post(self, *args, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.post(*args, **kwargs)

        def put(self, *args, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.put(*args, **kwargs)

        def delete(self, *args, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.delete(*args, **kwargs)

    return AuthedTestClient(client, auth_headers)


@pytest.fixture(autouse=True)
def clear_permission_cache():
    """Clear the permission set cache before and after each test."""
    from src.lib.decorators import invalidate_permission_set_cache
    invalidate_permission_set_cache()
    yield
    invalidate_permission_set_cache()


def make_obj(**kwargs):
    """Helper to create a SimpleNamespace object for mock DB returns."""
    return stdlib_types.SimpleNamespace(**kwargs)
