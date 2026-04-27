"""Schema-drift guard at startup.

Tests for ``services.database.schema_drift.check_schema_drift``. The guard
catches the v0.5.0 prod incident where a transitional pod was running with
a stale Prisma client whose generated types didn't match the live DB
schema — the ``releases`` endpoint started 500ing on every write because
``createdById: Field does not exist in enclosing type``.

The guard probes a small set of ``(table, column)`` pairs that the v0.5.x
refactor relies on. Missing column → drift.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _ok_db():
    """Return a mock client whose query_raw never raises (no drift)."""
    db = MagicMock()
    db.query_raw.return_value = []
    return db


def _missing_column_db(missing: set[tuple[str, str]]):
    """Return a mock client that raises on the listed (table, column) pairs."""
    db = MagicMock()

    def _query(sql, *args):
        for table, column in missing:
            if table in sql and column in sql:
                raise Exception(
                    f'column "{column}" of relation "{table}" does not exist'
                )
        return []

    db.query_raw.side_effect = _query
    return db


# ---------------------------------------------------------------------------
# check_schema_drift — happy path
# ---------------------------------------------------------------------------


class TestCheckSchemaDrift:
    """Tests for the schema-drift guard."""

    def test_returns_empty_drift_when_schema_matches(self):
        """All probed columns present → no drift, no errors."""
        from src.services.database.schema_drift import check_schema_drift

        result = check_schema_drift(_ok_db())

        assert result["drift"] == []
        assert result["healthy"] is True

    def test_detects_missing_fixture_design_test_package_id(self):
        """Missing ``fixture_designs.testPackageId`` → drift entry."""
        from src.services.database.schema_drift import check_schema_drift

        db = _missing_column_db({("fixture_designs", "testPackageId")})
        result = check_schema_drift(db)

        assert result["healthy"] is False
        names = [d["table"] + "." + d["column"] for d in result["drift"]]
        assert "fixture_designs.testPackageId" in names

    def test_detects_missing_fixture_purpose(self):
        """Missing ``fixtures.purpose`` → drift entry."""
        from src.services.database.schema_drift import check_schema_drift

        db = _missing_column_db({("fixtures", "purpose")})
        result = check_schema_drift(db)

        assert result["healthy"] is False
        names = [d["table"] + "." + d["column"] for d in result["drift"]]
        assert "fixtures.purpose" in names

    def test_detects_missing_released_test_package_id(self):
        """Missing ``product_stage_configs.releasedTestPackageId`` → drift entry."""
        from src.services.database.schema_drift import check_schema_drift

        db = _missing_column_db(
            {("product_stage_configs", "releasedTestPackageId")},
        )
        result = check_schema_drift(db)

        assert result["healthy"] is False
        names = [d["table"] + "." + d["column"] for d in result["drift"]]
        assert "product_stage_configs.releasedTestPackageId" in names

    def test_detects_missing_manufacturing_session_test_package_id(self):
        """Missing ``manufacturing_sessions.testPackageId`` → drift entry."""
        from src.services.database.schema_drift import check_schema_drift

        db = _missing_column_db(
            {("manufacturing_sessions", "testPackageId")},
        )
        result = check_schema_drift(db)

        assert result["healthy"] is False
        names = [d["table"] + "." + d["column"] for d in result["drift"]]
        assert "manufacturing_sessions.testPackageId" in names

    def test_detects_multiple_drifts_at_once(self):
        """Multiple missing columns → all reported."""
        from src.services.database.schema_drift import check_schema_drift

        db = _missing_column_db(
            {
                ("fixtures", "purpose"),
                ("manufacturing_sessions", "testPackageId"),
            },
        )
        result = check_schema_drift(db)

        assert result["healthy"] is False
        assert len(result["drift"]) >= 2
