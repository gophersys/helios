"""Integration tests for the /v2/test/nodes discovery endpoint.

`corectl test list-nodes` calls this route to enumerate which physical
test nodes (MTIBs) are visible, what they're labelled with, and whether
they're currently free. The endpoint mirrors `/v2/devices/mtibs` in
shape but adds three discovery-oriented query filters: ``available``,
``purpose``, ``product``.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def _node(**overrides):
    """Build a Node-shaped Prisma mock with sensible defaults."""
    defaults = dict(
        id="node-1",
        name="MTIB-01",
        hostname="verdin-imx8mm-001",
        type="VALIDATION",
        disabled=False,
        ipAddress="192.168.1.1",
        hardwareRevision="REV1.2",
        metadata=None,
        fixtureSlot=None,
        claimedBy=[],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def test_list_test_nodes_returns_nodes(authed_client, mock_db):
    """Smoke: endpoint returns the full node set when no filters set."""
    mock_db.node.find_many.return_value = [
        _node(id="n1", name="MFG-01", type="MANUFACTURING"),
        _node(id="n2", name="VAL-01", type="VALIDATION"),
    ]
    mock_db.node.count.return_value = 2

    response = authed_client.get("/v2/test/nodes")
    assert response.status_code == 200, response.data
    body = json.loads(response.data)
    data = body["data"]
    assert isinstance(data["data"], list)
    assert {n["id"] for n in data["data"]} == {"n1", "n2"}


def test_list_test_nodes_filters_by_purpose(authed_client, mock_db):
    """``purpose=manufacturing`` translates to ``where.type=MANUFACTURING``."""
    mock_db.node.find_many.return_value = [
        _node(id="m1", name="MFG-01", type="MANUFACTURING"),
    ]
    mock_db.node.count.return_value = 1

    response = authed_client.get("/v2/test/nodes?purpose=manufacturing")
    assert response.status_code == 200, response.data
    call_kwargs = mock_db.node.find_many.call_args.kwargs
    assert call_kwargs["where"]["type"] == "MANUFACTURING"


def test_list_test_nodes_filters_by_availability(authed_client, mock_db):
    """``available=true`` excludes nodes with an ACTIVE claim."""
    # A free node + a claimed node. The endpoint should hand both to
    # the DB but apply an in-memory filter on `claimedBy` containing
    # an ACTIVE entry — anything with an active claim is dropped from
    # the result set.
    free_node = _node(id="free", claimedBy=[])
    claimed_node = _node(
        id="claimed",
        claimedBy=[
            make_obj(
                id="cn1",
                claimId="claim-1",
                nodeId="claimed",
                claim=make_obj(id="claim-1", status="ACTIVE"),
            )
        ],
    )
    mock_db.node.find_many.return_value = [free_node, claimed_node]
    mock_db.node.count.return_value = 2

    response = authed_client.get("/v2/test/nodes?available=true")
    assert response.status_code == 200, response.data
    data = json.loads(response.data)["data"]["data"]
    assert {n["id"] for n in data} == {"free"}


def test_list_test_nodes_filters_by_product(authed_client, mock_db):
    """``product=<id>`` narrows to nodes whose fixtureSlot.fixture.productId matches."""
    matching = _node(
        id="match",
        fixtureSlot=make_obj(
            id="slot-1",
            fixtureId="fix-1",
            slotIndex=0,
            label="Slot 1",
            fixture=make_obj(id="fix-1", name="Alpha Bench 1", productId="prod-alpha"),
        ),
    )
    mock_db.node.find_many.return_value = [matching]
    mock_db.node.count.return_value = 1

    response = authed_client.get("/v2/test/nodes?product=prod-alpha")
    assert response.status_code == 200, response.data
    where = mock_db.node.find_many.call_args.kwargs["where"]
    # The `where` should descend into fixtureSlot.fixture.productId.
    assert where.get("fixtureSlot", {}).get("fixture", {}).get("productId") == "prod-alpha"
