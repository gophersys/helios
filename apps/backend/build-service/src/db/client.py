"""Database client for build-service schema."""

from prisma import Prisma
from typing import Optional

_client: Optional[Prisma] = None


def get_db() -> Prisma:
    global _client
    if _client is None:
        raise RuntimeError("Database client not initialized. Call init_db() first.")
    return _client


def init_db():
    global _client
    _client = Prisma()
    _client.connect()


def close_db():
    global _client
    if _client is not None:
        _client.disconnect()
        _client = None
