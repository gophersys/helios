"""Tests for the manufacturing runner module — API key lifecycle + teardown.

The runner pod uses a database-backed API key for the duration of a
manufacturing session. The key's lifetime should track the session, not
a wall-clock TTL: a session can run for days while operators scan
panels in waves, and a 24h timer caused crashloops in production where
the runner pod kept respawning with a stale env after the key
expired.

Two contracts under test:

* The key created at session deploy has no fixed ``expiresAt`` —
  lifecycle is "alive while the session is ACTIVE."
* When the session ends and the runner is torn down, the key is
  revoked (deleted from ``api_keys``) so it can't outlive its
  purpose.
"""

from __future__ import annotations

import types
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import MockPrismaClient, make_obj


@pytest.fixture
def svc_mock_db():
    return MockPrismaClient()


def _session(**overrides):
    defaults = dict(
        id="r-sess-1",
        productId="r-prod-1",
        fixtureId="r-fix-1",
        runnerStatus="DEPLOYING",
        runnerDeploymentName="mfg-alpha-r-sess-1",
        assetSetId="r-as-1",
        config=None,
        testPackageId=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# _create_runner_api_key — key has no fixed TTL
# ---------------------------------------------------------------------------


class TestCreateRunnerApiKey:
    def test_key_has_no_expiry(self, svc_mock_db):
        """Runner keys should not expire on a wall-clock timer.

        The teardown path (called when a session ends) is the one that
        revokes the key. A 24h TTL stranded long-running mfg sessions
        when the pod re-spawned after midnight on day 2.
        """
        from src.api.v2.manufacturing.runner import _create_runner_api_key

        svc_mock_db.user.find_first.return_value = make_obj(id="u-system")

        _create_runner_api_key(svc_mock_db, "r-sess-1")

        svc_mock_db.apikey.create.assert_called_once()
        kwargs = svc_mock_db.apikey.create.call_args.kwargs["data"]
        assert kwargs["expiresAt"] is None, (
            f"Runner key should be created without an expiresAt. Got: {kwargs.get('expiresAt')!r}"
        )

    def test_key_name_tags_with_session_id(self, svc_mock_db):
        """Teardown matches on key name to revoke — must include session id."""
        from src.api.v2.manufacturing.runner import _create_runner_api_key

        svc_mock_db.user.find_first.return_value = make_obj(id="u-system")

        _create_runner_api_key(svc_mock_db, "r-sess-1")

        kwargs = svc_mock_db.apikey.create.call_args.kwargs["data"]
        assert "r-sess-1" in kwargs["name"]


# ---------------------------------------------------------------------------
# teardown_manufacturing_runner — revokes the API key
# ---------------------------------------------------------------------------


class TestTeardownRevokesKey:
    def test_teardown_deletes_runner_api_key(self, svc_mock_db):
        """Ending a session revokes its runner API key.

        Without this, the orphaned key sits in the DB with no way to be
        cleaned up except a TTL — and we just removed the TTL. The
        revocation is the lifecycle hook.
        """
        from src.api.v2.manufacturing import runner as runner_mod

        session = _session(runnerDeploymentName="mfg-alpha-r-sess-1")

        with patch.object(runner_mod, "_teardown_k8s", return_value=True):
            with patch.object(runner_mod.env_config, "ENVIRONMENT", "staging"):
                with patch.object(runner_mod, "log_audit"):
                    runner_mod.teardown_manufacturing_runner(svc_mock_db, session)

        # Either delete_many (preferred — match on name pattern) or a
        # find_first + delete pair is acceptable; the test asserts on
        # the "key got deleted" outcome.
        called = svc_mock_db.apikey.delete_many.called or svc_mock_db.apikey.delete.called
        assert called, "teardown should revoke the runner API key for the session"

        if svc_mock_db.apikey.delete_many.called:
            where = svc_mock_db.apikey.delete_many.call_args.kwargs["where"]
            # Match on name which carries the session id.
            assert "r-sess-1" in str(where), (
                f"delete_many filter should target the session's runner key. Got: {where!r}"
            )

    def test_teardown_clears_runner_deployment_fields(self, svc_mock_db):
        """The session's runner status/deployment should clear regardless."""
        from src.api.v2.manufacturing import runner as runner_mod

        session = _session(runnerDeploymentName="mfg-alpha-r-sess-1")

        with patch.object(runner_mod, "_teardown_k8s", return_value=True):
            with patch.object(runner_mod.env_config, "ENVIRONMENT", "staging"):
                with patch.object(runner_mod, "log_audit"):
                    runner_mod.teardown_manufacturing_runner(svc_mock_db, session)

        update_calls = [
            call for call in svc_mock_db.manufacturingsession.update.call_args_list
            if call.kwargs.get("where", {}).get("id") == "r-sess-1"
        ]
        assert update_calls, "session should be updated"
        data = update_calls[0].kwargs["data"]
        assert data["runnerStatus"] is None
        assert data["runnerDeploymentName"] is None
