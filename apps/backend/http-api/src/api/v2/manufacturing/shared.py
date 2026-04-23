"""Shared helpers for the manufacturing module."""

from src.lib.errors import not_found


def resolve_test_package(db, product_id: str, explicit_version: str | None = None):
    """Resolve the manufacturing test package.

    Priority:
    1. Explicit version (if provided)
    2. Latest RELEASED MANUFACTURING package
    3. Latest MANUFACTURING package (dev fallback)

    Returns (test_package, error_response) — error_response is a Flask tuple
    when the explicit version is not found.
    """
    if explicit_version:
        tp = db.testpackage.find_first(
            where={
                "productId": product_id,
                "type": "MANUFACTURING",
                "version": explicit_version,
            },
        )
        if not tp:
            return None, not_found(
                f"Manufacturing test package version '{explicit_version}' not found"
            )
        return tp, None

    tp = db.testpackage.find_first(
        where={"productId": product_id, "type": "MANUFACTURING", "status": "RELEASED"},
        order={"createdAt": "desc"},
    )
    if tp:
        return tp, None

    tp = db.testpackage.find_first(
        where={"productId": product_id, "type": "MANUFACTURING"},
        order={"createdAt": "desc"},
    )
    return tp, None
