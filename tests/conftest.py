"""Root conftest for integration and E2E tests.

Provides:
- test_db: separate Postgres database (concord_test)
- test_minio: separate MinIO bucket (concord-test)
- test_api: Flask test client connected to real DB
- Guaranteed cleanup via try/finally + atexit
"""

import atexit
import hashlib
import logging
import os
import subprocess
import sys
import time

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger("concord.tests")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEST_DB_NAME = "concord_test"
TEST_BUCKET = "concord-test"
PG_HOST = "localhost"
PG_PORT = 5433
PG_USER = "concord"
PG_PASS = "concord"
PG_ADMIN_DB = "postgres"

MINIO_URL = "http://localhost:8675"
MINIO_ACCESS_KEY = "concord"
MINIO_SECRET_KEY = "concordstorage!"

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRISMA_DIR = os.path.join(WORKSPACE_ROOT, "prisma")
SEED_SCRIPT = os.path.join(PRISMA_DIR, "seed.py")

CI_API_KEY = "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"

# ---------------------------------------------------------------------------
# pytest_configure — set env vars BEFORE any source module imports
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Set all required environment variables before anything loads."""
    test_db_url = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"

    env_vars = {
        "ENVIRONMENT": "test",
        "DELETE_ALL_KEY": "test-delete-key",
        "LOG_LEVEL": "30",
        "LOG_PATH": "/tmp/concord-integration-test.log",
        "SERVER_PORT": "9001",
        "CORS_ORIGINS": "http://localhost:4200",
        "JWT_SECRET_KEY": "test-jwt-secret-key-for-integration-tests",
        "CONCORD_API_HOST": "test.concord.local",
        "ASSETS_FOLDER": "/tmp/concord-test-assets",
        "STORAGE_URL": MINIO_URL,
        "STORAGE_ACCESS_KEY": MINIO_ACCESS_KEY,
        "STORAGE_SECRET_ACCESS_KEY": MINIO_SECRET_KEY,
        "STORAGE_BUCKET_NAME": TEST_BUCKET,
        "AUTH_ENABLED": "false",
        "AUTH_SERVER_URL": "",
        "AUTH_SERVER_API_KEY": "",
        "DATABASE_URL": test_db_url,
        "DIRECT_DATABASE_URL": test_db_url,
        "BITBUCKET_POLLER_ENABLED": "false",
    }
    for key, value in env_vars.items():
        os.environ[key] = value


# ---------------------------------------------------------------------------
# Database management
# ---------------------------------------------------------------------------

def _admin_conn():
    """Connect to the postgres admin database (for CREATE/DROP DATABASE)."""
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_ADMIN_DB,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _db_exists(cur, db_name):
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    return cur.fetchone() is not None


def _terminate_connections(cur, db_name):
    """Terminate all active connections to a database."""
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
    """, (db_name,))


def _create_test_db():
    """Create the test database and push the Prisma schema."""
    conn = _admin_conn()
    try:
        cur = conn.cursor()
        if _db_exists(cur, TEST_DB_NAME):
            _terminate_connections(cur, TEST_DB_NAME)
            cur.execute(f"DROP DATABASE {TEST_DB_NAME}")
        cur.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        cur.close()
    finally:
        conn.close()

    # Push schema using prisma db push
    env = os.environ.copy()
    test_url = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
    env["DATABASE_URL"] = test_url
    env["DIRECT_DATABASE_URL"] = test_url

    result = subprocess.run(
        ["prisma", "db", "push", "--skip-generate", "--accept-data-loss",
         f"--schema={os.path.join(PRISMA_DIR, 'schema.prisma')}"],
        capture_output=True, text=True, env=env, cwd=WORKSPACE_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prisma db push failed:\n{result.stderr}\n{result.stdout}")

    logger.info("Test database '%s' created and schema pushed", TEST_DB_NAME)


def _seed_test_db():
    """Run seed.py against the test database."""
    env = os.environ.copy()
    env["ENVIRONMENT"] = "development"  # so dev users get seeded
    env["SEED_ADMIN_EMAIL"] = ""

    python_path_parts = [
        os.path.join(WORKSPACE_ROOT, "libs", "python"),
        os.path.join(WORKSPACE_ROOT, "libs"),
        os.path.join(WORKSPACE_ROOT, "libs", "protocols"),
    ]
    env["PYTHONPATH"] = ":".join(python_path_parts)

    result = subprocess.run(
        [sys.executable, SEED_SCRIPT],
        capture_output=True, text=True, env=env, cwd=WORKSPACE_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"seed.py failed:\n{result.stderr}\n{result.stdout}")

    logger.info("Test database seeded")


def _drop_test_db():
    """Drop the test database."""
    try:
        conn = _admin_conn()
        cur = conn.cursor()
        if _db_exists(cur, TEST_DB_NAME):
            _terminate_connections(cur, TEST_DB_NAME)
            cur.execute(f"DROP DATABASE {TEST_DB_NAME}")
            logger.info("Test database '%s' dropped", TEST_DB_NAME)
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("Failed to drop test database: %s", e)


# ---------------------------------------------------------------------------
# MinIO management
# ---------------------------------------------------------------------------

def _create_test_bucket():
    """Create the test MinIO bucket."""
    from minio import Minio
    from urllib.parse import urlparse

    parsed = urlparse(MINIO_URL)
    client = Minio(
        endpoint=parsed.netloc,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    if not client.bucket_exists(TEST_BUCKET):
        client.make_bucket(TEST_BUCKET)
    logger.info("MinIO test bucket '%s' ready", TEST_BUCKET)
    return client


def _destroy_test_bucket(client=None):
    """Delete all objects and remove the test bucket."""
    try:
        from minio import Minio
        from urllib.parse import urlparse

        if client is None:
            parsed = urlparse(MINIO_URL)
            client = Minio(
                endpoint=parsed.netloc,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=False,
            )
        if client.bucket_exists(TEST_BUCKET):
            # Delete all objects (including versions)
            objects = client.list_objects(TEST_BUCKET, recursive=True)
            for obj in objects:
                client.remove_object(TEST_BUCKET, obj.object_name)
            client.remove_bucket(TEST_BUCKET)
            logger.info("MinIO test bucket '%s' destroyed", TEST_BUCKET)
    except Exception as e:
        logger.warning("Failed to destroy test bucket: %s", e)


# ---------------------------------------------------------------------------
# atexit cleanup — last resort
# ---------------------------------------------------------------------------
atexit.register(_drop_test_db)
atexit.register(_destroy_test_bucket)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db():
    """Create test database, push schema, seed, yield, then drop."""
    _create_test_db()
    _seed_test_db()
    yield TEST_DB_NAME
    _drop_test_db()


@pytest.fixture(scope="session")
def test_minio():
    """Create test bucket, yield the MinIO client, then destroy."""
    client = _create_test_bucket()
    yield client
    _destroy_test_bucket(client)


@pytest.fixture(scope="session")
def _prisma_client(test_db):
    """Initialize a real Prisma client pointing at the test database."""
    sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "libs", "python"))
    sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "libs"))
    sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "libs", "protocols"))

    from database import Prisma
    client = Prisma()
    client.connect()
    yield client
    try:
        client.disconnect()
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_api(test_db, test_minio):
    """Create a Flask test client connected to the real test DB and MinIO."""
    http_api_src = os.path.join(WORKSPACE_ROOT, "apps", "backend", "http-api", "src")
    http_api_root = os.path.join(WORKSPACE_ROOT, "apps", "backend", "http-api")

    # Ensure source paths are importable
    for p in [http_api_src, http_api_root]:
        if p not in sys.path:
            sys.path.insert(0, p)

    # Initialize DB client before importing routes
    from src.services.database.prisma import init_postgres_client
    init_postgres_client()

    # Initialize storage client
    from src.services.storage.client import init_storage_client
    init_storage_client()

    from flask import Flask
    from unittest.mock import MagicMock
    from importlib import reload
    import api.v2.router as router_module
    reload(router_module)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.json.sort_keys = False

    mock_logger = MagicMock()
    mock_logger.add_filter = MagicMock()
    mock_socketio = MagicMock()

    router_module.register_v2_routes(mock_logger, app, mock_socketio)

    yield app.test_client()


# ---------------------------------------------------------------------------
# Auth header fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_headers(_prisma_client):
    """JWT headers for the admin@concord.dev user."""
    user = _prisma_client.user.find_unique(where={"email": "admin@concord.dev"}, include={"permissionSet": True})
    assert user is not None, "admin@concord.dev not found. Did the seed run?"

    from src.services.auth.jwt import create_token
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role="ADMIN")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def developer_headers(_prisma_client):
    """JWT headers for the developer@concord.dev user."""
    user = _prisma_client.user.find_unique(where={"email": "developer@concord.dev"}, include={"permissionSet": True})
    assert user is not None, "developer@concord.dev not found. Did the seed run?"

    from src.services.auth.jwt import create_token
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role="DEVELOPER")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def operator_headers(_prisma_client):
    """JWT headers for the operator@concord.dev user."""
    user = _prisma_client.user.find_unique(where={"email": "operator@concord.dev"}, include={"permissionSet": True})
    assert user is not None, "operator@concord.dev not found. Did the seed run?"

    from src.services.auth.jwt import create_token
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role="OPERATOR")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def maintainer_headers(_prisma_client):
    """JWT headers for the maintainer@concord.dev user."""
    user = _prisma_client.user.find_unique(where={"email": "maintainer@concord.dev"}, include={"permissionSet": True})
    assert user is not None, "maintainer@concord.dev not found. Did the seed run?"

    from src.services.auth.jwt import create_token
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role="MAINTAINER")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def ci_api_key_headers():
    """Headers using the CI API key from seed.py."""
    return {"Authorization": f"ApiKey {CI_API_KEY}", "Content-Type": "application/json"}
