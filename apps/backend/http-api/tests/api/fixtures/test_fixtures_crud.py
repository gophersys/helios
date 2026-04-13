"""Integration tests for Fixtures CRUD API — deploy, undeploy, slots, update, dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2025, 1, 1, tzinfo=timezone.utc)


def _fixture_obj(**overrides):
    defaults = dict(
        id="fix-1",
        name="Test Fixture",
        productId="prod-1",
        type="VALIDATION",
        description="A test fixture",
        active=True,
        metadata=None,
        stationId=None,
        designId=None,
        status="AVAILABLE",
        lockedBy=None,
        lockedAt=None,
        profileOverrides=None,
        lastHealthCheck=None,
        product=make_obj(id="prod-1", name="Alpha"),
        slots=[],
        manufacturingSessions=[],
        deployments=[],
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _slot_obj(**overrides):
    defaults = dict(
        id="slot-1",
        fixtureId="fix-1",
        slotIndex=0,
        label="Slot A",
        nodeId=None,
        active=True,
        jlinkAppSerial=None,
        jlinkCommsSerial=None,
        uartAppPath=None,
        uartCommsPath=None,
        dutDeviceId=None,
        dutSnr=None,
        dutImei=None,
        dutIccids=[],
        testExecutions=[],
        node=None,
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _node_obj(**overrides):
    defaults = dict(
        id="node-1",
        name="MTIB-01",
        hostname="192.168.1.100",
        type="VALIDATION",
        status="ONLINE",
        metadata={},
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# TestListFixtures
# ---------------------------------------------------------------------------

class TestListFixtures:
    """Tests for GET /v2/fixtures."""

    def test_list_returns_paginated_results(self, authed_client, mock_db):
        """List fixtures returns pagination metadata and fixture list."""
        mock_db.fixture.count.return_value = 2
        mock_db.fixture.find_many.return_value = [
            _fixture_obj(id="fix-1", name="A"),
            _fixture_obj(id="fix-2", name="B"),
        ]

        resp = authed_client.get("/v2/fixtures")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    def test_list_with_type_filter(self, authed_client, mock_db):
        """List fixtures filters by ?type= query param."""
        mock_db.fixture.count.return_value = 1
        mock_db.fixture.find_many.return_value = [_fixture_obj(type="MANUFACTURING")]

        resp = authed_client.get("/v2/fixtures?type=manufacturing")
        assert resp.status_code == 200
        # Verify the where clause used uppercase
        call_args = mock_db.fixture.count.call_args[1]
        assert call_args["where"]["type"] == "MANUFACTURING"

    def test_list_with_product_id_filter(self, authed_client, mock_db):
        """List fixtures filters by ?productId= query param."""
        mock_db.fixture.count.return_value = 1
        mock_db.fixture.find_many.return_value = [_fixture_obj(productId="prod-42")]

        resp = authed_client.get("/v2/fixtures?productId=prod-42")
        assert resp.status_code == 200
        call_args = mock_db.fixture.count.call_args[1]
        assert call_args["where"]["productId"] == "prod-42"

    def test_list_empty(self, authed_client, mock_db):
        """List returns empty data with zero total when no fixtures exist."""
        mock_db.fixture.count.return_value = 0
        mock_db.fixture.find_many.return_value = []

        resp = authed_client.get("/v2/fixtures")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    def test_list_includes_slot_count(self, authed_client, mock_db):
        """Serialized fixture includes slotCount from slot list."""
        slot = _slot_obj()
        fix = _fixture_obj(slots=[slot])
        mock_db.fixture.count.return_value = 1
        mock_db.fixture.find_many.return_value = [fix]

        resp = authed_client.get("/v2/fixtures")
        body = resp.get_json()
        assert body["data"]["data"][0]["slotCount"] == 1


# ---------------------------------------------------------------------------
# TestGetFixture
# ---------------------------------------------------------------------------

class TestGetFixture:
    """Tests for GET /v2/fixtures/<id>."""

    def test_get_existing_fixture(self, authed_client, mock_db):
        """Get fixture by ID returns full fixture with slots."""
        slot = _slot_obj(nodeId=None)
        fix = _fixture_obj(slots=[slot])
        mock_db.fixture.find_unique.return_value = fix

        resp = authed_client.get("/v2/fixtures/fix-1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["id"] == "fix-1"
        assert "slots" in body["data"]

    def test_get_nonexistent_fixture_returns_404(self, authed_client, mock_db):
        """Get fixture with unknown ID returns 404."""
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.get("/v2/fixtures/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestCreateFixture
# ---------------------------------------------------------------------------

class TestCreateFixture:
    """Tests for POST /v2/fixtures."""

    def test_create_success(self, authed_client, mock_db):
        """Create fixture with valid payload returns 201 and fixture data."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.fixture.find_first.return_value = None  # no name collision
        mock_db.fixture.create.return_value = _fixture_obj(name="New Fixture")

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.post("/v2/fixtures", data=json.dumps({
                "name": "New Fixture",
                "productId": "prod-1",
                "type": "validation",
            }))

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["name"] == "New Fixture"

    def test_create_missing_name_returns_400(self, authed_client, mock_db):
        """Create fixture with empty name returns 400."""
        resp = authed_client.post("/v2/fixtures", data=json.dumps({
            "name": "",
            "productId": "prod-1",
            "type": "validation",
        }))
        assert resp.status_code == 400

    def test_create_product_not_found_returns_404(self, authed_client, mock_db):
        """Create fixture for nonexistent product returns 404."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post("/v2/fixtures", data=json.dumps({
            "name": "Fix",
            "productId": "unknown-prod",
            "type": "validation",
        }))
        assert resp.status_code == 404

    def test_create_duplicate_name_returns_409(self, authed_client, mock_db):
        """Create fixture with already-used name returns 409."""
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.fixture.find_first.return_value = _fixture_obj()  # name already in use

        resp = authed_client.post("/v2/fixtures", data=json.dumps({
            "name": "Test Fixture",
            "productId": "prod-1",
            "type": "validation",
        }))
        assert resp.status_code == 409

    def test_create_invalid_type_returns_400(self, authed_client, mock_db):
        """Create fixture with invalid type returns 400."""
        resp = authed_client.post("/v2/fixtures", data=json.dumps({
            "name": "Fix",
            "productId": "prod-1",
            "type": "ROBOTICS",
        }))
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# TestUpdateFixture
# ---------------------------------------------------------------------------

class TestUpdateFixture:
    """Tests for PUT /v2/fixtures/<id>."""

    def test_update_name_success(self, authed_client, mock_db):
        """Update fixture name returns 200 with updated data."""
        existing = _fixture_obj(name="Old Name")
        updated = _fixture_obj(name="New Name")
        mock_db.fixture.find_unique.side_effect = [existing, updated]
        mock_db.fixture.find_first.return_value = None
        mock_db.fixture.update.return_value = updated

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.put("/v2/fixtures/fix-1", data=json.dumps({"name": "New Name"}))

        assert resp.status_code == 200

    def test_update_nonexistent_returns_404(self, authed_client, mock_db):
        """Update a nonexistent fixture returns 404."""
        mock_db.fixture.find_unique.return_value = None

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.put("/v2/fixtures/nope", data=json.dumps({"name": "X"}))

        assert resp.status_code == 404

    def test_update_duplicate_name_returns_409(self, authed_client, mock_db):
        """Update to name used by another fixture returns 409."""
        existing = _fixture_obj(name="Old Name")
        duplicate = _fixture_obj(id="fix-2", name="Taken Name")
        mock_db.fixture.find_unique.return_value = existing
        mock_db.fixture.find_first.return_value = duplicate

        resp = authed_client.put("/v2/fixtures/fix-1", data=json.dumps({"name": "Taken Name"}))
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# TestDeleteFixture
# ---------------------------------------------------------------------------

class TestDeleteFixture:
    """Tests for DELETE /v2/fixtures/<id>."""

    def test_delete_success(self, authed_client, mock_db):
        """Delete a fixture with no sessions or deployments returns 200."""
        mock_db.fixture.find_unique.return_value = _fixture_obj(sessions=[], deployments=[])

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.delete("/v2/fixtures/fix-1")

        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_delete_with_sessions_returns_409(self, authed_client, mock_db):
        """Delete fixture with linked sessions returns 409."""
        session = make_obj(id="sess-1")
        mock_db.fixture.find_unique.return_value = _fixture_obj(manufacturingSessions=[session], deployments=[])

        resp = authed_client.delete("/v2/fixtures/fix-1")
        assert resp.status_code == 409

    def test_delete_nonexistent_returns_404(self, authed_client, mock_db):
        """Delete nonexistent fixture returns 404."""
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.delete("/v2/fixtures/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestSlots
# ---------------------------------------------------------------------------

class TestCreateSlot:
    """Tests for POST /v2/fixtures/<id>/slots."""

    def test_create_slot_success(self, authed_client, mock_db):
        """Create slot returns 201 with slot data."""
        mock_db.fixture.find_unique.return_value = _fixture_obj()
        mock_db.fixtureslot.find_first.return_value = None  # no index collision
        mock_db.fixtureslot.create.return_value = _slot_obj(id="slot-new")

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.post("/v2/fixtures/fix-1/slots", data=json.dumps({
                "slotIndex": 0,
                "label": "Slot A",
            }))

        assert resp.status_code == 201

    def test_create_slot_duplicate_index_returns_409(self, authed_client, mock_db):
        """Create slot with duplicate slotIndex returns 409."""
        mock_db.fixture.find_unique.return_value = _fixture_obj()
        mock_db.fixtureslot.find_first.return_value = _slot_obj()  # already exists

        resp = authed_client.post("/v2/fixtures/fix-1/slots", data=json.dumps({
            "slotIndex": 0,
            "label": "Slot A",
        }))
        assert resp.status_code == 409

    def test_create_slot_fixture_not_found_returns_404(self, authed_client, mock_db):
        """Create slot for nonexistent fixture returns 404."""
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post("/v2/fixtures/nope/slots", data=json.dumps({
            "slotIndex": 0,
            "label": "A",
        }))
        assert resp.status_code == 404


class TestDeleteSlot:
    """Tests for DELETE /v2/fixtures/<id>/slots/<sid>."""

    def test_delete_slot_success(self, authed_client, mock_db):
        """Delete slot with no test executions returns 200."""
        slot = _slot_obj(testExecutions=[])
        mock_db.fixtureslot.find_first.return_value = slot

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.delete("/v2/fixtures/fix-1/slots/slot-1")

        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_delete_slot_with_executions_returns_409(self, authed_client, mock_db):
        """Delete slot with test executions returns 409."""
        slot = _slot_obj(testExecutions=[make_obj(id="exec-1")])
        mock_db.fixtureslot.find_first.return_value = slot

        resp = authed_client.delete("/v2/fixtures/fix-1/slots/slot-1")
        assert resp.status_code == 409

    def test_delete_slot_not_found_returns_404(self, authed_client, mock_db):
        """Delete nonexistent slot returns 404."""
        mock_db.fixtureslot.find_first.return_value = None

        resp = authed_client.delete("/v2/fixtures/fix-1/slots/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestAssignSlotNode
# ---------------------------------------------------------------------------

class TestAssignSlotNode:
    """Tests for POST /v2/fixtures/<id>/slots/<sid>/assign."""

    def test_assign_node_success(self, authed_client, mock_db):
        """Assign a node to a slot returns 200 with updated slot."""
        mock_db.fixture.find_unique.return_value = _fixture_obj(type="VALIDATION")
        slot = _slot_obj(nodeId=None, slotIndex=0)
        mock_db.fixtureslot.find_first.side_effect = [slot, None]
        mock_db.node.find_unique.return_value = _node_obj(type="VALIDATION")
        updated_slot = _slot_obj(
            nodeId="node-1",
            node=_node_obj(),
        )
        mock_db.fixtureslot.update.return_value = updated_slot

        with patch("api.v2.fixtures.fixtures.log_audit"):
            with patch("api.v2.fixtures.fixtures._deploy_mtib_for_slot", return_value="mtib-deploy-1"):
                resp = authed_client.post(
                    "/v2/fixtures/fix-1/slots/slot-1/assign",
                    data=json.dumps({"nodeId": "node-1"}),
                )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["nodeId"] == "node-1"

    def test_assign_node_type_mismatch_returns_400(self, authed_client, mock_db):
        """Assign node with type mismatch returns 400."""
        mock_db.fixture.find_unique.return_value = _fixture_obj(type="VALIDATION")
        slot = _slot_obj(nodeId=None)
        mock_db.fixtureslot.find_first.return_value = slot
        mock_db.node.find_unique.return_value = _node_obj(type="MANUFACTURING")

        resp = authed_client.post(
            "/v2/fixtures/fix-1/slots/slot-1/assign",
            data=json.dumps({"nodeId": "node-1"}),
        )
        assert resp.status_code == 400

    def test_assign_node_already_assigned_returns_409(self, authed_client, mock_db):
        """Assign node already assigned elsewhere returns 409."""
        mock_db.fixture.find_unique.return_value = _fixture_obj(type="VALIDATION")
        slot = _slot_obj(id="slot-1", nodeId=None)
        other_slot = _slot_obj(id="slot-other")
        # First find_first = current slot, second = existing assignment on different slot
        mock_db.fixtureslot.find_first.side_effect = [slot, other_slot]
        mock_db.node.find_unique.return_value = _node_obj(type="VALIDATION")

        resp = authed_client.post(
            "/v2/fixtures/fix-1/slots/slot-1/assign",
            data=json.dumps({"nodeId": "node-1"}),
        )
        assert resp.status_code == 409

    def test_unassign_node_sets_node_to_null(self, authed_client, mock_db):
        """Assign with nodeId=null unassigns the current node."""
        mock_db.fixture.find_unique.return_value = _fixture_obj(type="VALIDATION")
        slot = _slot_obj(nodeId="node-1")
        mock_db.fixtureslot.find_first.return_value = slot
        mock_db.fixtureslot.update.return_value = _slot_obj(nodeId=None)

        with patch("api.v2.fixtures.fixtures.log_audit"):
            with patch("api.v2.fixtures.fixtures._undeploy_mtib_for_slot"):
                resp = authed_client.post(
                    "/v2/fixtures/fix-1/slots/slot-1/assign",
                    data=json.dumps({"nodeId": None}),
                )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestDeployFixture / TestUndeployFixture
# ---------------------------------------------------------------------------

class TestDeployFixture:
    """Tests for POST /v2/fixtures/<id>/deploy."""

    def test_deploy_no_assigned_nodes_returns_400(self, authed_client, mock_db):
        """Deploy with no assigned slots returns 400."""
        fix = _fixture_obj(slots=[_slot_obj(nodeId=None, node=None)])
        mock_db.fixture.find_unique.return_value = fix

        with patch("api.v2.fixtures.fixtures.log_audit"):
            resp = authed_client.post("/v2/fixtures/fix-1/deploy")

        assert resp.status_code == 400

    def test_deploy_fixture_not_found_returns_404(self, authed_client, mock_db):
        """Deploy nonexistent fixture returns 404."""
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post("/v2/fixtures/nope/deploy")
        assert resp.status_code == 404

    def test_deploy_with_assigned_slot_deploys(self, authed_client, mock_db):
        """Deploy with assigned slots calls deploy for each and returns results."""
        node = _node_obj()
        slot = _slot_obj(nodeId="node-1", node=node, slotIndex=0)
        fix = _fixture_obj(slots=[slot])
        mock_db.fixture.find_unique.return_value = fix

        with patch("api.v2.fixtures.fixtures.log_audit"):
            with patch("api.v2.fixtures.fixtures._deploy_mtib_for_slot", return_value="dep-1"):
                resp = authed_client.post("/v2/fixtures/fix-1/deploy")

        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["deployed"]) == 1
        assert body["data"]["deployed"][0]["deploymentName"] == "dep-1"


class TestUndeployFixture:
    """Tests for POST /v2/fixtures/<id>/undeploy."""

    def test_undeploy_fixture_not_found_returns_404(self, authed_client, mock_db):
        """Undeploy nonexistent fixture returns 404."""
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post("/v2/fixtures/nope/undeploy")
        assert resp.status_code == 404

    def test_undeploy_locked_fixture_returns_409(self, authed_client, mock_db):
        """Undeploy locked fixture (session running) returns 409."""
        fix = _fixture_obj(status="LOCKED", slots=[])
        mock_db.fixture.find_unique.return_value = fix

        resp = authed_client.post("/v2/fixtures/fix-1/undeploy")
        assert resp.status_code == 409

    def test_undeploy_success(self, authed_client, mock_db):
        """Undeploy fixture with no active session returns 200."""
        slot = _slot_obj(nodeId="node-1")
        fix = _fixture_obj(status="AVAILABLE", slots=[slot])
        mock_db.fixture.find_unique.return_value = fix

        with patch("api.v2.fixtures.fixtures.log_audit"):
            with patch("api.v2.fixtures.fixtures._undeploy_mtib_for_slot", return_value=True):
                resp = authed_client.post("/v2/fixtures/fix-1/undeploy")

        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["undeployed"]) == 1


# ---------------------------------------------------------------------------
# TestDashboardOverview
# ---------------------------------------------------------------------------

class TestDashboardOverview:
    """Tests for GET /v2/dashboard/overview — fixture health summary."""

    def test_dashboard_returns_fixture_summary(self, authed_client, mock_db):
        """Dashboard overview returns health and slot counts per fixture."""
        node = _node_obj(status="ONLINE")
        slot = _slot_obj(nodeId="node-1", node=node)
        fix = _fixture_obj(
            slots=[slot],
            deployments=[],
        )
        mock_db.fixture.find_many.return_value = [fix]

        resp = authed_client.get("/v2/dashboard/overview")
        assert resp.status_code == 200
        body = resp.get_json()
        fixtures = body["data"]["fixtures"]
        assert len(fixtures) == 1
        item = fixtures[0]
        assert item["slotCount"] == 1
        assert item["assignedCount"] == 1
        assert item["nodesOnline"] == 1
        assert item["health"] == "HEALTHY"

    def test_dashboard_empty_fixture_health(self, authed_client, mock_db):
        """Dashboard reports EMPTY health for fixture with no slots."""
        fix = _fixture_obj(slots=[], deployments=[])
        mock_db.fixture.find_many.return_value = [fix]

        resp = authed_client.get("/v2/dashboard/overview")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["fixtures"][0]["health"] == "EMPTY"

    def test_dashboard_unassigned_health(self, authed_client, mock_db):
        """Dashboard reports UNASSIGNED when slots exist but no node is assigned."""
        slot = _slot_obj(nodeId=None, node=None)
        fix = _fixture_obj(slots=[slot], deployments=[])
        mock_db.fixture.find_many.return_value = [fix]

        resp = authed_client.get("/v2/dashboard/overview")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["fixtures"][0]["health"] == "UNASSIGNED"

    # TODO: test_dashboard_error_health_when_node_error
    # TODO: test_dashboard_degraded_health_when_some_nodes_offline
