"""Database client for build-service local schema (optional)."""

from typing import Any, Optional

_client: Optional[Any] = None


def get_db():
    if _client is None:
        raise RuntimeError("Database client not initialized")
    return _client


def init_db():
    global _client
    try:
        from prisma import Prisma
        _client = Prisma()
        _client.connect()
    except (ImportError, RuntimeError) as e:
        # Prisma not generated or not installed — local DB disabled
        _client = None
        raise RuntimeError(f"Local DB unavailable: {e}") from e


def close_db():
    global _client
    if _client is not None:
        try:
            _client.disconnect()
        except Exception:
            pass
        _client = None
