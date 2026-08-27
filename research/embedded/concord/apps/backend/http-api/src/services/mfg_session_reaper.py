"""Sweep ``ACTIVE`` manufacturing sessions whose runner stopped heartbeating.

Production hit a 2.5-day case where a session's K8s Deployment was long
gone but the DB row never flipped to ``FAILED``. The fixture stayed
LOCKED and operators saw a stuck "session active" badge with no way to
recover short of a manual SQL update. This reaper closes the loop:
periodically scan ACTIVE sessions, kill the ones whose heartbeat is
stale, run teardown, mark them FAILED.

The reaper is intentionally conservative — it only fires on sessions
whose ``runnerLastHeartbeat`` (or fallback ``startedAt``) is older than
``staleness_minutes``. Fresh deploys cold-starting a runner pod are not
disturbed; the staleness window is the operating tolerance for "runner
silently died".
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict


logger = logging.getLogger(__name__)


# Imported lazily so test fixtures can swap it without pulling the
# heavy K8s client module on every import.
def _teardown_call(db, session):
    from src.api.v2.manufacturing.runner import teardown_manufacturing_runner
    return teardown_manufacturing_runner(db, session)


# Re-exported so tests can patch ``mfg_session_reaper.teardown_manufacturing_runner``.
from src.api.v2.manufacturing.runner import (  # noqa: E402  (placed here for the patch target)
    teardown_manufacturing_runner,
)


DEFAULT_STALENESS_MINUTES = 30


def reap_orphan_manufacturing_sessions(
    db,
    staleness_minutes: int = DEFAULT_STALENESS_MINUTES,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Mark stale ACTIVE sessions FAILED and run runner teardown.

    A session is considered stale when:

    * ``runnerLastHeartbeat`` is older than ``staleness_minutes``, OR
    * ``runnerLastHeartbeat`` is null AND ``startedAt`` is older than
      ``staleness_minutes`` (covers "deploy died before first heartbeat").

    Returns::

        {
            "reaped": int,        # sessions marked FAILED
            "healthy": int,       # active sessions left alone
            "errors": list[dict], # per-session teardown errors
            "dry_run": bool,
        }
    """
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=staleness_minutes)

    sessions = db.manufacturingsession.find_many(
        where={"status": "ACTIVE"},
    )

    reaped = 0
    healthy = 0
    errors: list = []

    for s in sessions:
        last_seen = getattr(s, "runnerLastHeartbeat", None) or getattr(s, "startedAt", None)
        if last_seen is None:
            healthy += 1
            continue
        if last_seen > threshold:
            healthy += 1
            continue

        if dry_run:
            logger.info(
                "[dry-run] Would reap mfg session %s: last_seen=%s threshold=%s",
                getattr(s, "id", "?"), last_seen, threshold,
            )
            reaped += 1
            continue

        try:
            teardown_manufacturing_runner(db, s)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Reaper teardown failed for session %s: %s — proceeding with DB flip",
                getattr(s, "id", "?"), e,
            )
            errors.append({"sessionId": getattr(s, "id", None), "error": str(e)})

        try:
            db.manufacturingsession.update(
                where={"id": s.id},
                data={
                    "status": "FAILED",
                    "endedAt": now,
                    "runnerStatus": None,
                    "runnerDeploymentName": None,
                },
            )
            reaped += 1
            logger.info(
                "Reaped orphan mfg session %s (last_seen=%s, threshold=%s)",
                s.id, last_seen, threshold,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Reaper DB flip failed for session %s: %s",
                getattr(s, "id", "?"), e,
            )
            errors.append({"sessionId": getattr(s, "id", None), "error": str(e)})

    summary = {
        "reaped": reaped,
        "healthy": healthy,
        "errors": errors,
        "dry_run": dry_run,
        "staleness_minutes": staleness_minutes,
        "threshold": threshold.isoformat(),
    }
    logger.info("Mfg-session reaper complete: %s", summary)
    logger.info(
        "concord_retention_summary scope=mfg_sessions reaped=%d healthy=%d errors=%d staleness_minutes=%d dry_run=%d",
        reaped, healthy, len(errors), staleness_minutes, int(bool(dry_run)),
    )
    return summary


RUNNER_KEY_NAME_PREFIX = "Manufacturing session "


def _extract_session_id(key_name: str) -> str | None:
    """Pull the session id from a runner-key name. Stable shape from runner.py."""
    if not key_name or not key_name.startswith(RUNNER_KEY_NAME_PREFIX):
        return None
    return key_name[len(RUNNER_KEY_NAME_PREFIX):].strip() or None


def revoke_orphan_runner_keys(db, dry_run: bool = False) -> Dict[str, Any]:
    """Defense-in-depth sweep of stale runner API keys.

    The mfg-session teardown path is the primary cleanup — but if a
    teardown failed mid-flight or an operator killed a session row
    directly in SQL, the runner key sits in ``api_keys`` with no
    ``expiresAt`` set (lifecycle was supposed to be session-bound). This
    sweep deletes any ``Manufacturing session <id>`` key whose owning
    session is no longer ``ACTIVE`` (or no longer exists at all). Keys
    whose name doesn't follow the runner pattern are ignored — this is
    not a generic API-key sweep.

    Returns::

        {
            "revoked": int,
            "kept": int,
            "errors": list[dict],
            "dry_run": bool,
        }
    """
    keys = db.apikey.find_many(
        where={"name": {"startswith": RUNNER_KEY_NAME_PREFIX}},
    )

    revoked = 0
    kept = 0
    errors: list = []

    for key in keys:
        name = getattr(key, "name", "")
        session_id = _extract_session_id(name)
        if not session_id:
            kept += 1
            continue

        session = db.manufacturingsession.find_unique(where={"id": session_id})
        if session is not None and getattr(session, "status", None) == "ACTIVE":
            kept += 1
            continue

        if dry_run:
            logger.info(
                "[dry-run] Would revoke runner key %s (session=%s, status=%s)",
                getattr(key, "id", "?"),
                session_id,
                getattr(session, "status", None) if session else "MISSING",
            )
            revoked += 1
            continue

        try:
            db.apikey.delete_many(where={"name": name})
            revoked += 1
            logger.info(
                "Revoked orphan runner key for session %s (status=%s)",
                session_id,
                getattr(session, "status", None) if session else "MISSING",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to revoke runner key for session %s: %s", session_id, e)
            errors.append({"sessionId": session_id, "error": str(e)})

    summary = {
        "revoked": revoked,
        "kept": kept,
        "errors": errors,
        "dry_run": dry_run,
    }
    logger.info("Runner-key revocation sweep complete: %s", summary)
    logger.info(
        "concord_retention_summary scope=runner_keys revoked=%d kept=%d errors=%d dry_run=%d",
        revoked, kept, len(errors), int(bool(dry_run)),
    )
    return summary


# CLI entrypoint for the retention CronJob.
#
# Usage:
#   python -m src.services.mfg_session_reaper [--minutes N] [--dry-run]
if __name__ == "__main__":
    import argparse
    import json
    import sys

    from src.services.database.prisma import init_postgres_client

    parser = argparse.ArgumentParser(description="Reap orphan manufacturing sessions")
    parser.add_argument("--minutes", type=int, default=DEFAULT_STALENESS_MINUTES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-key-sweep",
        action="store_true",
        help="Skip the runner-key revocation sweep (run the session reaper only).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = init_postgres_client()
    try:
        session_result = reap_orphan_manufacturing_sessions(
            db, staleness_minutes=args.minutes, dry_run=args.dry_run,
        )
        key_result = (
            {"skipped": True}
            if args.skip_key_sweep
            else revoke_orphan_runner_keys(db, dry_run=args.dry_run)
        )
    finally:
        db.disconnect()
    print(json.dumps({"sessions": session_result, "keys": key_result}, indent=2, default=str))
    if session_result.get("errors") or key_result.get("errors"):
        sys.exit(1)
