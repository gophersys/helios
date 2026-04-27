"""Manufacturing session orphan reaper.

Production hit a 2.5-day case where a mfg session sat in ``ACTIVE`` with
its K8s Deployment long gone — operators never got the "session ended"
toast and the fixture stayed locked. The reaper sweeps sessions whose
runner stopped heartbeating but the DB row never got a clean teardown.

Sweep policy:

* Session is ``ACTIVE`` AND ``runnerLastHeartbeat`` is older than the
  staleness window (default 30 minutes) → mark FAILED, run teardown.
* Sessions with no heartbeat at all but a ``startedAt`` older than the
  window also count — covers the "deploy died before its first
  heartbeat" case.
* Newly-created sessions inside the staleness window are left alone so
  a slow runner cold-start doesn't trip the reaper.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


def _now():
    return datetime(2026, 4, 27, 18, 0, tzinfo=timezone.utc)


def _session(**overrides):
    defaults = dict(
        id="s-1",
        productId="p-1",
        fixtureId="f-1",
        status="ACTIVE",
        runnerStatus="RUNNING",
        runnerDeploymentName="mfg-runner-s-1",
        runnerLastHeartbeat=_now(),
        startedAt=_now() - timedelta(hours=2),
        testPackageId=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# reap_orphan_manufacturing_sessions
# ---------------------------------------------------------------------------


class TestOrphanReaper:
    """Tests for ``reap_orphan_manufacturing_sessions``."""

    @patch("src.services.mfg_session_reaper.datetime")
    def test_marks_stale_session_failed(self, mock_dt):
        """Heartbeat older than the window → session marked FAILED."""
        from src.services.mfg_session_reaper import reap_orphan_manufacturing_sessions

        mock_dt.now.return_value = _now()
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        db = MagicMock()
        stale = _session(runnerLastHeartbeat=_now() - timedelta(hours=2))
        db.manufacturingsession.find_many.return_value = [stale]

        with patch(
            "src.services.mfg_session_reaper.teardown_manufacturing_runner"
        ) as mock_teardown:
            result = reap_orphan_manufacturing_sessions(
                db, staleness_minutes=30,
            )

        assert result["reaped"] == 1
        assert result["healthy"] == 0

        # Session row should be flagged FAILED with endedAt set.
        update_calls = [
            c for c in db.manufacturingsession.update.call_args_list
            if c.kwargs.get("where", {}).get("id") == "s-1"
        ]
        assert update_calls
        data = update_calls[0].kwargs["data"]
        assert data["status"] == "FAILED"
        assert data["endedAt"] is not None
        # Teardown was attempted.
        mock_teardown.assert_called_once()

    @patch("src.services.mfg_session_reaper.datetime")
    def test_leaves_fresh_session_alone(self, mock_dt):
        """Heartbeat within the window → not reaped."""
        from src.services.mfg_session_reaper import reap_orphan_manufacturing_sessions

        mock_dt.now.return_value = _now()

        db = MagicMock()
        fresh = _session(runnerLastHeartbeat=_now() - timedelta(minutes=5))
        db.manufacturingsession.find_many.return_value = [fresh]

        with patch(
            "src.services.mfg_session_reaper.teardown_manufacturing_runner"
        ) as mock_teardown:
            result = reap_orphan_manufacturing_sessions(
                db, staleness_minutes=30,
            )

        assert result["reaped"] == 0
        assert result["healthy"] == 1
        mock_teardown.assert_not_called()

    @patch("src.services.mfg_session_reaper.datetime")
    def test_no_heartbeat_uses_started_at(self, mock_dt):
        """Session with no heartbeat but ``startedAt`` past the window is reaped."""
        from src.services.mfg_session_reaper import reap_orphan_manufacturing_sessions

        mock_dt.now.return_value = _now()

        db = MagicMock()
        ancient = _session(
            runnerLastHeartbeat=None,
            startedAt=_now() - timedelta(hours=5),
        )
        db.manufacturingsession.find_many.return_value = [ancient]

        with patch(
            "src.services.mfg_session_reaper.teardown_manufacturing_runner"
        ):
            result = reap_orphan_manufacturing_sessions(
                db, staleness_minutes=30,
            )

        assert result["reaped"] == 1

    @patch("src.services.mfg_session_reaper.datetime")
    def test_dry_run_does_not_mutate(self, mock_dt):
        """``dry_run=True`` only logs — no updates, no teardown."""
        from src.services.mfg_session_reaper import reap_orphan_manufacturing_sessions

        mock_dt.now.return_value = _now()

        db = MagicMock()
        stale = _session(runnerLastHeartbeat=_now() - timedelta(hours=2))
        db.manufacturingsession.find_many.return_value = [stale]

        with patch(
            "src.services.mfg_session_reaper.teardown_manufacturing_runner"
        ) as mock_teardown:
            result = reap_orphan_manufacturing_sessions(
                db, staleness_minutes=30, dry_run=True,
            )

        assert result["reaped"] == 1
        assert result["dry_run"] is True
        db.manufacturingsession.update.assert_not_called()
        mock_teardown.assert_not_called()

    @patch("src.services.mfg_session_reaper.datetime")
    def test_only_active_sessions_are_considered(self, mock_dt):
        """The DB query only matches ``status=ACTIVE`` sessions."""
        from src.services.mfg_session_reaper import reap_orphan_manufacturing_sessions

        mock_dt.now.return_value = _now()

        db = MagicMock()
        db.manufacturingsession.find_many.return_value = []

        reap_orphan_manufacturing_sessions(db, staleness_minutes=30)

        find_call = db.manufacturingsession.find_many.call_args
        where = find_call.kwargs.get("where") or {}
        assert where.get("status") == "ACTIVE", (
            f"reaper must scope to ACTIVE sessions, got: {where!r}"
        )


# ---------------------------------------------------------------------------
# revoke_orphan_runner_keys — defense in depth
# ---------------------------------------------------------------------------


class TestOrphanRunnerKeyRevocation:
    """Stale ``Manufacturing session ...`` API keys must not outlive their session.

    The mfg session teardown path normally deletes the key. This sweeper
    is the safety net: when a teardown silently failed mid-flight (or
    when an ops shortcut killed a session row directly), the key stays
    in the DB indefinitely because there's no ``expiresAt`` on it. The
    reaper drops keys whose owning session is no longer ACTIVE *or*
    whose session row is gone entirely.
    """

    def test_deletes_keys_for_ended_session(self):
        from src.services.mfg_session_reaper import revoke_orphan_runner_keys

        db = MagicMock()
        # Two runner keys — one for an ENDED session, one for an ACTIVE one.
        db.apikey.find_many.return_value = [
            make_obj(id="k1", name="Manufacturing session sess-old"),
            make_obj(id="k2", name="Manufacturing session sess-live"),
        ]

        def _find_session(where):
            sid = where.get("id")
            if sid == "sess-old":
                return make_obj(id=sid, status="ENDED")
            if sid == "sess-live":
                return make_obj(id=sid, status="ACTIVE")
            return None

        db.manufacturingsession.find_unique.side_effect = lambda where: _find_session(where)

        result = revoke_orphan_runner_keys(db)

        # Only the ENDED session's key was revoked.
        assert result["revoked"] == 1
        assert result["kept"] == 1
        deleted_names = [
            c.kwargs.get("where", {}).get("name") or c.args[0].get("name")
            for c in db.apikey.delete_many.call_args_list
        ]
        assert any("sess-old" in str(n) for n in deleted_names), (
            f"expected delete_many to target sess-old, got: {deleted_names!r}"
        )

    def test_deletes_keys_for_missing_session(self):
        """Key whose session row no longer exists → revoke."""
        from src.services.mfg_session_reaper import revoke_orphan_runner_keys

        db = MagicMock()
        db.apikey.find_many.return_value = [
            make_obj(id="k1", name="Manufacturing session sess-gone"),
        ]
        db.manufacturingsession.find_unique.return_value = None

        result = revoke_orphan_runner_keys(db)
        assert result["revoked"] == 1

    def test_skips_keys_with_unrecognized_name(self):
        """Non-runner keys (no ``Manufacturing session`` prefix) are untouched."""
        from src.services.mfg_session_reaper import revoke_orphan_runner_keys

        db = MagicMock()
        db.apikey.find_many.return_value = [
            make_obj(id="k1", name="Some user's personal key"),
        ]

        result = revoke_orphan_runner_keys(db)
        assert result["revoked"] == 0
        assert result["kept"] == 1

    def test_dry_run_does_not_mutate(self):
        from src.services.mfg_session_reaper import revoke_orphan_runner_keys

        db = MagicMock()
        db.apikey.find_many.return_value = [
            make_obj(id="k1", name="Manufacturing session sess-old"),
        ]
        db.manufacturingsession.find_unique.return_value = make_obj(
            id="sess-old", status="ENDED",
        )

        result = revoke_orphan_runner_keys(db, dry_run=True)
        assert result["revoked"] == 1
        assert result["dry_run"] is True
        db.apikey.delete_many.assert_not_called()
