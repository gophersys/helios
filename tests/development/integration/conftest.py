"""Integration test fixtures.

Uses session-scoped fixtures from the root conftest.
Adds function-scoped helpers for test isolation.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_permission_cache():
    """Clear the permission set cache before and after each test."""
    from src.lib.decorators import invalidate_permission_set_cache
    invalidate_permission_set_cache()
    yield
    invalidate_permission_set_cache()
