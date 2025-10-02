from typing import Optional

from corekinect.db import Prisma

# Global database client instance
appPostgresClient: Optional[Prisma] = None


def init_postgres_client() -> Prisma:
    """Initialize the global PostgreSQL client"""
    global appPostgresClient

    client = Prisma()
    client.connect(timeout=1)

    appPostgresClient = client
    return client


def get_db_client() -> Prisma:
    """Get the global database client instance"""
    global appPostgresClient

    if appPostgresClient is None:
        raise RuntimeError("Database client not initialized. Call init_postgres_client() first.")

    return appPostgresClient
