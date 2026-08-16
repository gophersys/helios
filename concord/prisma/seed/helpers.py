"""Shared seed helpers.

Kept intentionally small — each helper exists because Prisma's client
surface doesn't quite cover an idiom we need. If a helper is bigger than
one screen, the data model probably wants a ``@@unique`` instead.
"""

from typing import Any


def upsert_by_non_unique(db_model: Any, *, where: dict, create: dict, update: dict) -> Any:
    """Idempotent upsert keyed on a non-``@unique`` column.

    Prisma's ``.upsert(where=...)`` only accepts fields that are
    ``@id`` / ``@unique`` / ``@@unique``. Some seed records (e.g.
    ``FixtureDesign`` keyed by ``name``) don't have a unique constraint
    because the model predates any deliberate uniqueness decision.
    Rather than rush a schema migration in every affected model, this
    helper does the same thing with two round-trips:

        existing = db.model.find_first(where=natural_key)
        if existing: db.model.update(where={id}, data=update)
        else:        db.model.create(data=create)

    Safe to call multiple times — same behaviour as a real upsert.
    Not concurrent-safe, but neither is the seed itself.

    Args:
        db_model: the Prisma model client (e.g. ``db.fixturedesign``).
        where:    the natural-key filter (any fields, not just unique).
        create:   data to pass if no row matched.
        update:   data to apply if a row matched.
    """
    existing = db_model.find_first(where=where)
    if existing:
        return db_model.update(where={"id": existing.id}, data=update)
    return db_model.create(data=create)
