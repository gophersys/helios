"""Detect drift between the running Prisma client and the live DB schema.

The v0.5.0 deploy hit a transitional state where one ``http-api`` pod was
running with a freshly-bundled Prisma client whose generated types
matched the new schema, while the database still ran the previous
migration set. The ``releases`` endpoint started 500ing on every write
(``createdById: Field does not exist in enclosing type``). Same pattern
will recur on any schema-changing release.

This module probes a small set of ``(table, column)`` pairs that the
v0.5.x test-package refactor relies on. Each probe runs a light
``SELECT "<column>" FROM "<table>" LIMIT 1`` against the live DB; a
``column does not exist`` failure means the migration didn't land on
this pod's DB but the client expects it.

The probe is intentionally narrow:

* It catches the expensive failure modes (post-migration deploys with
  partial rollouts, mismatched client/db pairings) without trying to be
  a generic schema validator.
* It runs once at startup and on ``/ready`` polls.
* It does not block startup — it logs a loud error and surfaces the
  drift via ``/ready`` so K8s yanks the pod from rotation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple


logger = logging.getLogger("schema_drift")


# ``(table, column)`` pairs added by the v0.5.x refactor. Add new
# load-bearing columns here as the schema evolves so future deploys
# don't suffer the same transitional-pod failure mode.
PROBES: List[Tuple[str, str]] = [
    ("fixture_designs", "testPackageId"),
    ("fixtures", "purpose"),
    ("product_stage_configs", "releasedTestPackageId"),
    ("manufacturing_sessions", "testPackageId"),
    ("test_packages", "manifestVersion"),
]


def _column_missing(error_message: str, column: str) -> bool:
    """Heuristic match for "column X does not exist" Postgres errors.

    Both the raw ``UndefinedColumn`` from psycopg and Prisma's wrapped
    error string include the column name and the literal ``does not
    exist``. We match on both so we can tell drift apart from generic
    DB-not-reachable failures.
    """
    msg = error_message.lower()
    return column.lower() in msg and "does not exist" in msg


def check_schema_drift(db) -> Dict[str, Any]:
    """Return a drift report for the live DB.

    Shape::

        {
            "healthy": bool,
            "drift": [{"table": str, "column": str, "error": str}, ...],
        }

    A non-drift error (DB unreachable, perms) is treated as "drift
    unknown — assume healthy" so a flaky DB connection doesn't take
    the pod out of rotation. The readiness probe already covers basic
    DB connectivity.
    """
    drift: List[Dict[str, str]] = []
    for table, column in PROBES:
        sql = f'SELECT "{column}" FROM "{table}" LIMIT 1'
        try:
            db.query_raw(sql)
        except Exception as exc:  # noqa: BLE001 — Prisma wraps everything
            err = str(exc)
            if _column_missing(err, column):
                drift.append(
                    {"table": table, "column": column, "error": err}
                )
                logger.error(
                    "Schema drift detected: %s.%s missing in live DB. "
                    "This pod was built against a schema the DB hasn't "
                    "received yet — fail readiness so K8s yanks it.",
                    table, column,
                )
            else:
                # Generic DB error — log but don't flag as drift.
                logger.debug(
                    "Schema drift probe %s.%s skipped (non-drift error): %s",
                    table, column, err,
                )
    return {"healthy": not drift, "drift": drift}
