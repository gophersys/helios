"""Tests for /v2/fixture-claims — DEV_HOLD lifecycle.

The repo's HTTP-API tests run against a ``MockPrismaClient`` rather than
a live Postgres instance (see ``tests/conftest.py``). The mocks here
follow the existing v2 convention.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(**overrides):
    defaults = dict(
        id="node-1",
        name="verdin-node-1",
        hostname="verdin-node-1",
        type="VALIDATION",
        disabled=False,
        ipAddress="10.4.45.38",
        hardwareRevision="REV1.2",
        metadata=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _slot(**overrides):
    defaults = dict(
        id="slot-1",
        fixtureId="fix-1",
        slotIndex=0,
        label="slot1",
        nodeId="node-1",
        active=True,
        node=_node(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _fixture(**overrides):
    defaults = dict(
        id="fix-1",
        name="Sigma5 Bench 1",
        productId="prod-1",
        type="VALIDATION",
        boardRevisionId=None,
        purpose="DEV",
        disabled=False,
        active=True,
        slots=[_slot()],
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _claim(**overrides):
    defaults = dict(
        id="clm-1",
        userId="test-user-id",
        fixtureId="fix-1",
        status="ACTIVE",
        description=None,
        acquiredAt=NOW,
        lastHeartbeatAt=NOW,
        expiresAt=NOW + timedelta(seconds=300),
        hardCeilingAt=NOW + timedelta(hours=8),
        releasedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
        fixture=_fixture(),
        claimedNodes=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _node_claim(node_id="node-1", **overrides):
    """A node-mode claim — fixture=None, claimedNodes populated."""
    defaults = dict(
        id="clm-n-1",
        userId="test-user-id",
        fixtureId=None,
        fixture=None,
        status="ACTIVE",
        description=None,
        acquiredAt=NOW,
        lastHeartbeatAt=NOW,
        expiresAt=NOW + timedelta(seconds=300),
        hardCeilingAt=NOW + timedelta(hours=8),
        releasedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
        claimedNodes=[
            make_obj(
                id="cn-1", claimId="clm-n-1", nodeId=node_id, label="slot1",
                node=_node(id=node_id, hostname=node_id),
            ),
        ],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_audit():
    with patch("src.api.v2.fixture_claims.routes.log_audit"):
        yield


@pytest.fixture(autouse=True)
def _mock_address_resolver():
    """The serializer calls resolve_node_addresses → K8s. Stub it to a fixed map."""
    with patch(
        "src.api.v2.fixture_claims.service.resolve_node_addresses",
        return_value={"node-1": "10.4.45.38:50053"},
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_mtib_provisioning():
    """Stub K8s deployment calls so claim tests don't talk to a real cluster.

    Default: create_mtib_deployment returns a name (success), teardown
    returns []. Individual tests can override these via the returned
    MagicMocks (see ``test_create_aborts_when_provisioning_fails``).
    """
    with patch("src.api.v2.fixture_claims.service.create_mtib_deployment") as create_m, \
         patch("src.api.v2.fixture_claims.service.delete_mtib_deployments_for_claim") as delete_m:
        create_m.return_value = "mtib-test-deploy"
        delete_m.return_value = []
        yield create_m, delete_m


@pytest.fixture
def _busy_helpers_clean(mock_db):
    """Default the reservation gate to "free" — counts all zero, find_first None."""
    mock_db.testrun.count.return_value = 0
    mock_db.manufacturingsession.count.return_value = 0
    mock_db.fixtureclaim.count.return_value = 0
    mock_db.claimednode.find_first.return_value = None
    mock_db.fixtureslot.find_many.return_value = []
    mock_db.testrun.find_first.return_value = None
    mock_db.manufacturingsession.find_first.return_value = None


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims — create
# ---------------------------------------------------------------------------


class TestCreateClaim:
    def test_create_fixture_mode_happy_path(self, authed_client, mock_db, _busy_helpers_clean):
        mock_db.fixture.find_unique.return_value = _fixture()
        mock_db.fixtureclaim.create.return_value = _claim()

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"fixtureId": "fix-1", "ttlSeconds": 3600, "description": "scratch"}),
        )
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()["data"]
        assert body["fixtureId"] == "fix-1"
        assert body["status"] == "ACTIVE"
        assert body["slotBindings"][0]["mtibHost"] == "10.4.45.38:50053"

    def test_create_node_mode_happy_path(self, authed_client, mock_db, _busy_helpers_clean):
        mock_db.node.find_many.return_value = [_node()]
        mock_db.fixtureslot.find_many.return_value = []  # nodes not wired to any fixture
        mock_db.fixtureclaim.create.return_value = _node_claim()

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"nodes": [{"nodeId": "node-1", "label": "slot1"}]}),
        )
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()["data"]
        assert body["fixtureId"] is None
        assert body["slotBindings"][0]["nodeId"] == "node-1"

    def test_create_refuses_busy_fixture(self, authed_client, mock_db, _busy_helpers_clean):
        # Active TestRun on the fixture → reservation gate fires.
        mock_db.fixture.find_unique.return_value = _fixture()
        mock_db.testrun.count.return_value = 1

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"fixtureId": "fix-1"}),
        )
        assert resp.status_code == 409
        # Reservation gate should NOT have created a row.
        mock_db.fixtureclaim.create.assert_not_called()

    def test_create_refuses_busy_node(self, authed_client, mock_db, _busy_helpers_clean):
        mock_db.node.find_many.return_value = [_node()]
        # Another active claim already holds this node.
        held = make_obj(id="cn-other", claimId="clm-other", nodeId="node-1")
        mock_db.claimednode.find_first.return_value = held

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"nodes": [{"nodeId": "node-1"}]}),
        )
        assert resp.status_code == 409
        mock_db.fixtureclaim.create.assert_not_called()

    def test_create_node_mode_refuses_when_fixture_claim_holds_slot(
        self, authed_client, mock_db, _busy_helpers_clean
    ):
        """Cross-mode collision: an active fixture-mode claim on F implicitly
        holds every node wired to F's slots. A node-mode claim that names
        any of those nodes must be refused, mirroring the inverse direction
        already handled in is_fixture_busy().
        """
        mock_db.node.find_many.return_value = [_node()]
        # node-1 is wired into slot-0 of fixture fix-1.
        slot = make_obj(id="slot-0", nodeId="node-1", fixtureId="fix-1")
        mock_db.fixtureslot.find_many.return_value = [slot]
        # No active TestRun / MfgSession, but an active fixture-mode claim
        # on fix-1 — the case the original implementation missed.
        mock_db.fixtureclaim.find_first.return_value = make_obj(
            id="clm-already", fixtureId="fix-1", status="ACTIVE",
        )

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"nodes": [{"nodeId": "node-1"}]}),
        )
        assert resp.status_code == 409
        mock_db.fixtureclaim.create.assert_not_called()

    def test_create_xor_violation(self, authed_client, mock_db):
        # Both fixtureId AND nodes provided → 400
        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({
                "fixtureId": "fix-1",
                "nodes": [{"nodeId": "node-1"}],
            }),
        )
        assert resp.status_code == 400

    def test_create_404_missing_fixture(self, authed_client, mock_db, _busy_helpers_clean):
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"fixtureId": "fix-missing"}),
        )
        assert resp.status_code == 404

    def test_create_ttl_clamped_to_8h(self, authed_client, mock_db, _busy_helpers_clean):
        """ttlSeconds > 8h should clamp the expiresAt to the hard ceiling."""
        mock_db.fixture.find_unique.return_value = _fixture()
        captured: dict[str, Any] = {}

        def _capture(data, **_):
            captured.update(data)
            return _claim()
        mock_db.fixtureclaim.create.side_effect = _capture

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"fixtureId": "fix-1", "ttlSeconds": 99999}),
        )
        assert resp.status_code == 201
        # The hard ceiling is 8h; expiresAt should == hardCeilingAt when ttl > 8h.
        assert captured["expiresAt"] == captured["hardCeilingAt"]


# ---------------------------------------------------------------------------
# MTIB auto-provisioning on claim
# ---------------------------------------------------------------------------


class TestProvisioning:
    def test_create_provisions_mtib_on_each_held_node_fixture_mode(
        self, authed_client, mock_db, _busy_helpers_clean, _mock_mtib_provisioning,
    ):
        create_m, _ = _mock_mtib_provisioning
        mock_db.fixture.find_unique.return_value = _fixture()
        mock_db.fixtureclaim.create.return_value = _claim()

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"fixtureId": "fix-1", "ttlSeconds": 3600}),
        )
        assert resp.status_code == 201, resp.get_json()
        # Provisioning should have been invoked for the slot's node.
        create_m.assert_called_once()
        call = create_m.call_args
        assert call.kwargs["node_hostname"] == "verdin-node-1"
        assert call.kwargs["claim_id"] == "clm-1"
        # VALIDATION-type node → motion enabled.
        assert call.kwargs["config"]["env"]["MOTION_ENABLED"] == "true"

    def test_create_provisions_mtib_on_each_held_node_node_mode(
        self, authed_client, mock_db, _busy_helpers_clean, _mock_mtib_provisioning,
    ):
        create_m, _ = _mock_mtib_provisioning
        mock_db.node.find_many.return_value = [_node()]
        mock_db.fixtureslot.find_many.return_value = []
        mock_db.fixtureclaim.create.return_value = _node_claim()

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"nodes": [{"nodeId": "node-1", "label": "slot1"}]}),
        )
        assert resp.status_code == 201, resp.get_json()
        create_m.assert_called_once()
        call = create_m.call_args
        assert call.kwargs["node_hostname"] == "node-1"
        assert call.kwargs["claim_id"] == "clm-n-1"
        # Node-mode → deployment_id is claim-scoped.
        assert call.kwargs["deployment_id"].startswith("claim-")

    def test_create_aborts_when_provisioning_fails(
        self, authed_client, mock_db, _busy_helpers_clean, _mock_mtib_provisioning,
    ):
        """Provisioning failure should release the claim and return 502.

        The dev shouldn't end up holding a lease with no working mtib.
        """
        create_m, delete_m = _mock_mtib_provisioning
        create_m.return_value = None  # simulate k8s failure
        mock_db.node.find_many.return_value = [_node()]
        mock_db.fixtureslot.find_many.return_value = []
        mock_db.fixtureclaim.create.return_value = _node_claim()

        resp = authed_client.post(
            "/v2/fixture-claims",
            data=json.dumps({"nodes": [{"nodeId": "node-1"}]}),
        )
        assert resp.status_code == 502, resp.get_json()
        # Should have attempted teardown of whatever we managed to create.
        delete_m.assert_called_once()
        # And released the claim row.
        mock_db.fixtureclaim.update.assert_called()
        update_args = mock_db.fixtureclaim.update.call_args
        assert update_args.kwargs["data"]["status"] == "RELEASED"

    def test_release_tears_down_claim_mtibs(
        self, authed_client, mock_db, _mock_mtib_provisioning,
    ):
        _, delete_m = _mock_mtib_provisioning
        delete_m.return_value = ["mtib-verdin-node-1-s0"]
        active = _claim(status="ACTIVE")
        # find_unique on release does an `include={...}` lookup — return active.
        mock_db.fixtureclaim.find_unique.return_value = active
        mock_db.fixtureclaim.update.return_value = _claim(
            status="RELEASED", releasedAt=NOW,
        )

        resp = authed_client.post(f"/v2/fixture-claims/{active.id}/release")
        assert resp.status_code == 200, resp.get_json()
        delete_m.assert_called_once()

    def test_release_skips_teardown_when_already_released(
        self, authed_client, mock_db, _mock_mtib_provisioning,
    ):
        """Idempotency: re-releasing an already-RELEASED claim is a no-op
        — including the K8s teardown. A second release MUST NOT try to
        delete deployments a second time (they may have been re-created
        on a follow-up claim by now)."""
        _, delete_m = _mock_mtib_provisioning
        released = _claim(status="RELEASED", releasedAt=NOW)
        mock_db.fixtureclaim.find_unique.return_value = released

        resp = authed_client.post(f"/v2/fixture-claims/{released.id}/release")
        assert resp.status_code == 200
        delete_m.assert_not_called()


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims/<id>/heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_extends_expiry(self, authed_client, mock_db):
        old = _claim(expiresAt=NOW + timedelta(seconds=10))
        mock_db.fixtureclaim.find_unique.return_value = old
        # The update returns a row with a new expiresAt
        updated = _claim(expiresAt=NOW + timedelta(seconds=300), lastHeartbeatAt=NOW)
        mock_db.fixtureclaim.update.return_value = updated

        resp = authed_client.post("/v2/fixture-claims/clm-1/heartbeat")
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()["data"]
        assert "expiresAt" in body
        assert "lastHeartbeatAt" in body

    def test_heartbeat_on_expired_returns_410(self, authed_client, mock_db):
        expired = _claim(status="EXPIRED")
        mock_db.fixtureclaim.find_unique.return_value = expired

        resp = authed_client.post("/v2/fixture-claims/clm-1/heartbeat")
        assert resp.status_code == 410

    def test_heartbeat_on_released_returns_410(self, authed_client, mock_db):
        released = _claim(status="RELEASED")
        mock_db.fixtureclaim.find_unique.return_value = released

        resp = authed_client.post("/v2/fixture-claims/clm-1/heartbeat")
        assert resp.status_code == 410

    def test_heartbeat_missing_returns_404(self, authed_client, mock_db):
        mock_db.fixtureclaim.find_unique.return_value = None

        resp = authed_client.post("/v2/fixture-claims/missing/heartbeat")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims/<id>/release
# ---------------------------------------------------------------------------


class TestRelease:
    def test_release_active_claim(self, authed_client, mock_db):
        active = _claim(status="ACTIVE")
        mock_db.fixtureclaim.find_unique.return_value = active
        released = _claim(status="RELEASED", releasedAt=NOW)
        mock_db.fixtureclaim.update.return_value = released

        resp = authed_client.post("/v2/fixture-claims/clm-1/release")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["status"] == "RELEASED"

    def test_release_idempotent(self, authed_client, mock_db):
        """Releasing a claim that's already RELEASED returns 200, doesn't write."""
        already = _claim(status="RELEASED", releasedAt=NOW)
        mock_db.fixtureclaim.find_unique.return_value = already

        resp = authed_client.post("/v2/fixture-claims/clm-1/release")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["status"] == "RELEASED"
        mock_db.fixtureclaim.update.assert_not_called()


# ---------------------------------------------------------------------------
# GET /v2/fixture-claims — list
# ---------------------------------------------------------------------------


class TestListClaims:
    def test_list_defaults_to_caller_and_active(self, authed_client, mock_db):
        mock_db.fixtureclaim.find_many.return_value = [_claim()]

        resp = authed_client.get("/v2/fixture-claims")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert len(body["claims"]) == 1
        # The query should default userId=caller, status=ACTIVE.
        call_kwargs = mock_db.fixtureclaim.find_many.call_args.kwargs
        where = call_kwargs.get("where") or {}
        assert where.get("status") == "ACTIVE"
        assert where.get("userId") == "test-user-id"

    def test_list_filters_by_query_params(self, authed_client, mock_db):
        mock_db.fixtureclaim.find_many.return_value = []
        resp = authed_client.get(
            "/v2/fixture-claims?userId=other&status=RELEASED&fixtureId=fix-1",
        )
        assert resp.status_code == 200
        where = mock_db.fixtureclaim.find_many.call_args.kwargs.get("where") or {}
        assert where["userId"] == "other"
        assert where["status"] == "RELEASED"
        assert where["fixtureId"] == "fix-1"


# ---------------------------------------------------------------------------
# GET /v2/fixture-claims/<id>
# ---------------------------------------------------------------------------


class TestGetClaim:
    def test_get_returns_claim(self, authed_client, mock_db):
        mock_db.fixtureclaim.find_unique.return_value = _claim()
        resp = authed_client.get("/v2/fixture-claims/clm-1")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["id"] == "clm-1"
        assert "slotBindings" in body

    def test_get_missing_returns_404(self, authed_client, mock_db):
        mock_db.fixtureclaim.find_unique.return_value = None
        resp = authed_client.get("/v2/fixture-claims/clm-missing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Background sweeper
# ---------------------------------------------------------------------------


class TestExpirySweeper:
    def test_expiry_sweeper_transitions_state(self, mock_db):
        """The sweeper should flip ACTIVE → EXPIRED past expiresAt, and
        ACTIVE → ABANDONED past hardCeilingAt.
        """
        from src.api.v2.fixture_claims.service import sweep_expired_claims

        expired_claim = _claim(
            id="clm-exp",
            expiresAt=NOW - timedelta(seconds=10),
            hardCeilingAt=NOW + timedelta(hours=1),
        )
        abandoned_claim = _claim(
            id="clm-abnd",
            expiresAt=NOW + timedelta(seconds=10),
            hardCeilingAt=NOW - timedelta(seconds=1),
        )

        # The sweeper calls find_many twice — once for abandoned (hard-
        # ceiling lapse), once for expired (sliding lapse). Return the
        # appropriate row for each.
        def _find_many(*args, **kwargs):
            where = kwargs.get("where") or {}
            if "hardCeilingAt" in where:
                return [abandoned_claim]
            if "expiresAt" in where:
                return [expired_claim]
            return []
        mock_db.fixtureclaim.find_many.side_effect = _find_many

        result = sweep_expired_claims(mock_db)
        assert "clm-abnd" in result["abandoned"]
        assert "clm-exp" in result["expired"]
        # Two update calls — one per claim flipped.
        assert mock_db.fixtureclaim.update.call_count == 2

    def test_expiry_sweeper_no_op_when_nothing_pending(self, mock_db):
        from src.api.v2.fixture_claims.service import sweep_expired_claims
        mock_db.fixtureclaim.find_many.return_value = []
        result = sweep_expired_claims(mock_db)
        assert result == {"expired": [], "abandoned": []}
        mock_db.fixtureclaim.update.assert_not_called()
