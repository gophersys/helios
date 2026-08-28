"""Unit tests for _compute_fixture_health and the related helpers.

Covers the four canonical states (ONLINE, OFFLINE, ERROR, UNASSIGNED) plus
the empty-fixture and partial-MTIB cases.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


def _make_node(disabled=False, deploy_name="mtib-node-s0", ip="10.0.0.10"):
    return SimpleNamespace(
        id="node-x",
        name="MTIB",
        hostname="mtib-host",
        type="MANUFACTURING",
        disabled=disabled,
        ipAddress=ip,
        metadata={"deployment_name": deploy_name},
    )


def _make_slot(slot_index=0, node=None, slot_id=None):
    return SimpleNamespace(
        id=slot_id or f"slot-{slot_index}",
        fixtureId="fix-1",
        slotIndex=slot_index,
        label=f"Slot {slot_index}",
        nodeId=getattr(node, "id", None) if node else None,
        active=True,
        node=node,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_fixture(slots):
    return SimpleNamespace(
        id="fix-1",
        name="Test Fixture",
        productId="prod-1",
        type="MANUFACTURING",
        slots=slots,
        active=True,
        metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _ready_deploy(name, ip="10.0.0.10"):
    return {
        "name": name,
        "replicas": 1,
        "readyReplicas": 1,
        "availableReplicas": 1,
        "pods": [{"name": f"{name}-pod", "ready": True, "status": "Running"}],
    }


def test_unassigned_when_no_slots():
    from api.v2.fixtures.fixtures import _compute_fixture_health

    fixture = _make_fixture(slots=[])
    result = _compute_fixture_health(fixture, {})

    assert result["health"] == "UNASSIGNED"
    assert result["healthDetails"] == {
        "nodesReady": 0,
        "nodesTotal": 0,
        "mtibsReady": 0,
        "mtibsTotal": 0,
    }


def test_unassigned_when_slots_have_no_nodes():
    from api.v2.fixtures.fixtures import _compute_fixture_health

    fixture = _make_fixture(slots=[_make_slot(0, node=None), _make_slot(1, node=None)])
    result = _compute_fixture_health(fixture, {})

    assert result["health"] == "UNASSIGNED"
    assert result["healthDetails"]["nodesTotal"] == 0


def test_offline_when_every_node_lacks_deployment():
    """Every assigned slot has no MTIB deployment — fixture is OFFLINE,
    not ERROR. Powered-down hardware shows up as missing deployments,
    which is a clean shut state, not a partial failure."""
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n0 = _make_node(deploy_name=None)
    n0.id = "node-0"
    n0.metadata = {}
    n1 = _make_node(deploy_name=None)
    n1.id = "node-1"
    n1.metadata = {}
    fixture = _make_fixture(slots=[
        _make_slot(0, node=n0, slot_id="slot-0"),
        _make_slot(1, node=n1, slot_id="slot-1"),
    ])

    result = _compute_fixture_health(fixture, {})

    assert result["health"] == "OFFLINE"
    assert result["healthDetails"]["nodesTotal"] == 2
    assert result["healthDetails"]["nodesReady"] == 0


def test_offline_when_every_node_disabled():
    """Admin-disabled nodes also count as OFFLINE (clean shut)."""
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n0 = _make_node(disabled=True)
    n0.id = "node-0"
    n1 = _make_node(disabled=True)
    n1.id = "node-1"
    fixture = _make_fixture(slots=[
        _make_slot(0, node=n0, slot_id="slot-0"),
        _make_slot(1, node=n1, slot_id="slot-1"),
    ])

    result = _compute_fixture_health(fixture, {})

    assert result["health"] == "OFFLINE"
    assert result["healthDetails"]["nodesReady"] == 0


def test_online_when_all_nodes_online_and_grpc_ok():
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n0 = _make_node(deploy_name="mtib-a", ip="10.0.0.10")
    n0.id = "node-0"
    n1 = _make_node(deploy_name="mtib-b", ip="10.0.0.11")
    n1.id = "node-1"
    fixture = _make_fixture(slots=[
        _make_slot(0, node=n0, slot_id="slot-0"),
        _make_slot(1, node=n1, slot_id="slot-1"),
    ])
    status_map = {
        "mtib-a": _ready_deploy("mtib-a"),
        "mtib-b": _ready_deploy("mtib-b"),
    }

    with patch(
        "api.v2.fixtures.fixtures._probe_slots_concurrent",
        return_value={"slot-0": True, "slot-1": True},
    ):
        result = _compute_fixture_health(fixture, status_map)

    assert result["health"] == "ONLINE"
    assert result["healthDetails"]["nodesReady"] == 2
    assert result["healthDetails"]["nodesTotal"] == 2
    assert result["healthDetails"]["mtibsReady"] == 2
    assert result["healthDetails"]["mtibsTotal"] == 2


def test_error_when_node_online_but_mtib_pods_not_ready():
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n0 = _make_node(deploy_name="mtib-a")
    n0.id = "node-0"
    fixture = _make_fixture(slots=[_make_slot(0, node=n0, slot_id="slot-0")])
    status_map = {
        "mtib-a": {
            "name": "mtib-a",
            "replicas": 1,
            "readyReplicas": 0,
            "availableReplicas": 0,
            "pods": [{"name": "p", "ready": False, "status": "Pending"}],
        }
    }

    with patch(
        "api.v2.fixtures.fixtures._probe_slots_concurrent",
        return_value={},
    ):
        result = _compute_fixture_health(fixture, status_map)

    assert result["health"] == "ERROR"
    assert result["healthDetails"]["mtibsReady"] == 0
    assert result["healthDetails"]["mtibsTotal"] == 1


def test_error_on_partial_state_one_online_one_offline():
    """Mixed state — neither all OFFLINE nor all ONLINE-and-ready."""
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n_online = _make_node(deploy_name="mtib-a")
    n_online.id = "node-0"
    n_offline = _make_node(deploy_name="mtib-b")
    
    n_offline.id = "node-1"
    fixture = _make_fixture(slots=[
        _make_slot(0, node=n_online, slot_id="slot-0"),
        _make_slot(1, node=n_offline, slot_id="slot-1"),
    ])
    status_map = {
        "mtib-a": _ready_deploy("mtib-a"),
        "mtib-b": _ready_deploy("mtib-b"),
    }

    with patch(
        "api.v2.fixtures.fixtures._probe_slots_concurrent",
        return_value={"slot-0": True},
    ):
        result = _compute_fixture_health(fixture, status_map)

    assert result["health"] == "ERROR"
    assert result["healthDetails"]["nodesReady"] == 1
    assert result["healthDetails"]["nodesTotal"] == 2


def test_error_when_grpc_probe_fails_for_otherwise_ready_slot():
    from api.v2.fixtures.fixtures import _compute_fixture_health

    n0 = _make_node(deploy_name="mtib-a")
    n0.id = "node-0"
    fixture = _make_fixture(slots=[_make_slot(0, node=n0, slot_id="slot-0")])
    status_map = {"mtib-a": _ready_deploy("mtib-a")}

    with patch(
        "api.v2.fixtures.fixtures._probe_slots_concurrent",
        return_value={"slot-0": False},
    ):
        result = _compute_fixture_health(fixture, status_map)

    assert result["health"] == "ERROR"
    assert result["healthDetails"]["nodesReady"] == 0
    assert result["healthDetails"]["mtibsReady"] == 1


def test_get_mtib_status_map_returns_empty_when_k8s_unreachable():
    from api.v2.fixtures.fixtures import _get_mtib_status_map

    with patch(
        "api.v2.fixtures.fixtures.list_mtib_deployments",
        side_effect=RuntimeError("k8s down"),
    ):
        result = _get_mtib_status_map(None)
    assert result == {}


def test_get_mtib_status_map_indexes_by_name():
    from api.v2.fixtures.fixtures import _get_mtib_status_map

    fake = [
        {"name": "mtib-a", "replicas": 1, "readyReplicas": 1, "pods": []},
        {"name": "mtib-b", "replicas": 1, "readyReplicas": 0, "pods": []},
    ]
    with patch(
        "api.v2.fixtures.fixtures.list_mtib_deployments",
        return_value=fake,
    ):
        result = _get_mtib_status_map(None)

    assert set(result.keys()) == {"mtib-a", "mtib-b"}
    assert result["mtib-a"]["readyReplicas"] == 1
    assert result["mtib-b"]["readyReplicas"] == 0
