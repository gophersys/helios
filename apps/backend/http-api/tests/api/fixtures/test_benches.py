"""Tests for the Fixtures/Benches API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(**overrides):
    defaults = dict(id="prod-1", name="Alpha", slug="alpha", metadata=None)
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_design(**overrides):
    defaults = dict(
        id="design-1",
        name="Alpha B0 Fixture v1",
        product="alpha",
        revision="b0",
        capabilities=["jlink", "button"],
        profileTemplate={"uart_app_path": "/dev/ttyUSB0"},
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_slot(**overrides):
    defaults = dict(
        id="slot-1",
        fixtureId="bench-1",
        slotIndex=0,
        active=True,
        dutDeviceId="70B3D584C01E1FCC",
        dutSnr="0964",
        dutImei="355025931735979",
        dutIccids=["8914800000"],
        jlinkAppSerial="821009543",
        jlinkCommsSerial="821009541",
        uartAppPath="/dev/ttyUSB1",
        uartCommsPath="/dev/ttyUSB0",
        nodeId="node-1",
        node=make_obj(id="node-1", ipAddress="10.4.45.33"),
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_bench(**overrides):
    defaults = dict(
        id="bench-1",
        stationId="bench-33",
        name="Alpha REV 1.2",
        productId="prod-1",
        status="AVAILABLE",
        active=True,
        lockedBy=None,
        lockedAt=None,
        lastHealthCheck=None,
        profileOverrides=None,
        metadata=None,
        product=_make_product(),
        design=_make_design(),
        slots=[_make_slot()],
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# list_benches — GET /v2/fixtures/benches
# ---------------------------------------------------------------------------

def test_list_benches_success(authed_client, mock_db):
    mock_db.fixture.count.return_value = 1
    mock_db.fixture.find_many.return_value = [_make_bench()]

    response = authed_client.get("/v2/fixtures/benches")

    assert response.status_code == 200
    data = json.loads(response.data)
    benches = data["data"]["data"]
    assert len(benches) == 1
    assert benches[0]["id"] == "bench-1"
    assert benches[0]["stationId"] == "bench-33"
    assert benches[0]["status"] == "AVAILABLE"
    assert benches[0]["mtibAddress"] == "10.4.45.33:50053"
    assert data["data"]["pagination"]["total"] == 1


def test_list_benches_empty(authed_client, mock_db):
    mock_db.fixture.count.return_value = 0
    mock_db.fixture.find_many.return_value = []

    response = authed_client.get("/v2/fixtures/benches")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["data"] == []
    assert data["data"]["pagination"]["total"] == 0


def test_list_benches_pagination(authed_client, mock_db):
    mock_db.fixture.count.return_value = 120
    mock_db.fixture.find_many.return_value = [_make_bench()]

    response = authed_client.get("/v2/fixtures/benches?page=2&limit=10")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["pagination"]["page"] == 2
    assert data["data"]["pagination"]["limit"] == 10
    assert data["data"]["pagination"]["total"] == 120
    assert data["data"]["pagination"]["pages"] == 12


def test_list_benches_status_filter(authed_client, mock_db):
    mock_db.fixture.count.return_value = 1
    mock_db.fixture.find_many.return_value = [_make_bench(status="LOCKED")]

    response = authed_client.get("/v2/fixtures/benches?status=locked")

    assert response.status_code == 200
    call_kwargs = mock_db.fixture.find_many.call_args[1]
    assert call_kwargs["where"]["status"] == "LOCKED"


def test_list_benches_requires_auth(client):
    response = client.get("/v2/fixtures/benches")
    assert response.status_code == 401


def test_list_benches_no_slot_no_mtib_address(authed_client, mock_db):
    """Bench with no slots should serialize without MTIB address."""
    mock_db.fixture.count.return_value = 1
    mock_db.fixture.find_many.return_value = [_make_bench(slots=[])]

    response = authed_client.get("/v2/fixtures/benches")

    assert response.status_code == 200
    data = json.loads(response.data)
    bench = data["data"]["data"][0]
    assert bench["mtibAddress"] is None
    assert bench["dutDeviceId"] is None


# ---------------------------------------------------------------------------
# get_bench — GET /v2/fixtures/benches/<id>
# ---------------------------------------------------------------------------

def test_get_bench_success(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench()

    response = authed_client.get("/v2/fixtures/benches/bench-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    bench = data["data"]
    assert bench["id"] == "bench-1"
    assert bench["dutDeviceId"] == "70B3D584C01E1FCC"
    assert bench["dutSnr"] == "0964"
    assert bench["jlinkAppSerial"] == "821009543"
    assert bench["capabilities"] == ["jlink", "button"]
    assert bench["dutRevision"] == "b0"


def test_get_bench_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client.get("/v2/fixtures/benches/bad-id")

    assert response.status_code == 404


def test_get_bench_requires_auth(client):
    response = client.get("/v2/fixtures/benches/bench-1")
    assert response.status_code == 401


def test_get_bench_no_design(authed_client, mock_db):
    """Bench without design should serialize capabilities as empty list."""
    mock_db.fixture.find_unique.return_value = _make_bench(design=None)

    response = authed_client.get("/v2/fixtures/benches/bench-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["capabilities"] == []
    assert data["data"]["fixtureDesign"] is None


# ---------------------------------------------------------------------------
# create_bench — POST /v2/fixtures/benches
# ---------------------------------------------------------------------------

_CREATE_PAYLOAD = {
    "stationId": "bench-99",
    "name": "New Bench",
    "mtibAddress": "10.4.45.99:50053",
    "dutProduct": "alpha",
    "dutRevision": "b0",
    "dutSnr": "09AB",
    "jlinkAppSerial": "821009999",
    "uartAppPath": "/dev/ttyUSB1",
    "uartCommsPath": "/dev/ttyUSB0",
}


def test_create_bench_success(authed_client, mock_db):
    mock_db.fixture.find_first.return_value = None  # no duplicate stationId
    mock_db.product.find_first.return_value = _make_product()
    created_fixture = _make_bench(id="bench-new", stationId="bench-99", slots=[])
    mock_db.fixture.create.return_value = created_fixture
    mock_db.fixtureslot.create.return_value = _make_slot(id="slot-new", fixtureId="bench-new")

    with patch("api.v2.fixtures.benches.log_audit") as mock_audit:
        response = authed_client.post(
            "/v2/fixtures/benches",
            data=json.dumps(_CREATE_PAYLOAD),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["stationId"] == "bench-99"
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args[0]
    assert call_args[0] == "validation.bench.create"
    assert call_args[1] == "Fixture"


def test_create_bench_missing_station_id(authed_client, mock_db):
    payload = {**_CREATE_PAYLOAD}
    del payload["stationId"]

    response = authed_client.post("/v2/fixtures/benches", data=json.dumps(payload))

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "stationId" in data["errors"][0]["message"]


def test_create_bench_missing_name(authed_client, mock_db):
    payload = {**_CREATE_PAYLOAD}
    del payload["name"]

    response = authed_client.post("/v2/fixtures/benches", data=json.dumps(payload))

    assert response.status_code == 400


def test_create_bench_missing_mtib_address(authed_client, mock_db):
    payload = {**_CREATE_PAYLOAD}
    del payload["mtibAddress"]

    response = authed_client.post("/v2/fixtures/benches", data=json.dumps(payload))

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "mtibAddress" in data["errors"][0]["message"]


def test_create_bench_duplicate_station_id(authed_client, mock_db):
    mock_db.fixture.find_first.return_value = _make_bench()

    response = authed_client.post(
        "/v2/fixtures/benches",
        data=json.dumps(_CREATE_PAYLOAD),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "bench-99" in data["errors"][0]["message"]


def test_create_bench_product_not_found(authed_client, mock_db):
    mock_db.fixture.find_first.return_value = None
    mock_db.product.find_first.return_value = None

    response = authed_client.post(
        "/v2/fixtures/benches",
        data=json.dumps(_CREATE_PAYLOAD),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "No product found" in data["errors"][0]["message"]


def test_create_bench_requires_auth(client):
    response = client.post(
        "/v2/fixtures/benches",
        data=json.dumps(_CREATE_PAYLOAD),
        content_type="application/json",
    )
    assert response.status_code == 401


def test_create_bench_no_body(authed_client, mock_db):
    response = authed_client.post("/v2/fixtures/benches", data="")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# update_bench — PATCH /v2/fixtures/benches/<id>
# ---------------------------------------------------------------------------


def test_update_bench_name(authed_client, mock_db):
    bench = _make_bench()
    updated = _make_bench(name="Updated Bench")
    mock_db.fixture.find_unique.side_effect = [bench, updated]

    with patch("api.v2.fixtures.benches.log_audit"):
        # PATCH via underlying client
        response = authed_client._client.patch(
            "/v2/fixtures/benches/bench-1",
            data=json.dumps({"name": "Updated Bench"}),
            headers=dict(authed_client._headers),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["name"] == "Updated Bench"


def test_update_bench_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client._client.patch(
        "/v2/fixtures/benches/bad-id",
        data=json.dumps({"name": "X"}),
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 404


def test_update_bench_no_valid_fields(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench()

    response = authed_client._client.patch(
        "/v2/fixtures/benches/bench-1",
        data=json.dumps({}),
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 400


def test_update_bench_slot_fields(authed_client, mock_db):
    """Updating dutSnr should update the first slot."""
    bench = _make_bench()
    updated = _make_bench()
    mock_db.fixture.find_unique.side_effect = [bench, updated]

    with patch("api.v2.fixtures.benches.log_audit"):
        response = authed_client._client.patch(
            "/v2/fixtures/benches/bench-1",
            data=json.dumps({"dutSnr": "ABCD"}),
            headers=dict(authed_client._headers),
        )

    assert response.status_code == 200
    # Slot update should have been called
    mock_db.fixtureslot.update.assert_called_once()


def test_update_bench_requires_auth(client):
    response = client.patch(
        "/v2/fixtures/benches/bench-1",
        data=json.dumps({"name": "X"}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# delete_bench — DELETE /v2/fixtures/benches/<id>
# ---------------------------------------------------------------------------

def test_delete_bench_success(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench()

    with patch("api.v2.fixtures.benches.log_audit") as mock_audit:
        response = authed_client._client.delete(
            "/v2/fixtures/benches/bench-1",
            headers=dict(authed_client._headers),
        )

    assert response.status_code == 200
    mock_db.fixture.delete.assert_called_once_with(where={"id": "bench-1"})
    mock_audit.assert_called_once()


def test_delete_bench_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client._client.delete(
        "/v2/fixtures/benches/bad-id",
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 404


def test_delete_bench_locked(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench(status="LOCKED")

    response = authed_client._client.delete(
        "/v2/fixtures/benches/bench-1",
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "locked" in data["errors"][0]["message"].lower()


def test_delete_bench_requires_auth(client):
    response = client.delete("/v2/fixtures/benches/bench-1")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# lock_bench — POST /v2/fixtures/benches/<id>/lock
# ---------------------------------------------------------------------------

def test_lock_bench_success(authed_client, mock_db):
    available_bench = _make_bench(status="AVAILABLE")
    locked_bench = _make_bench(status="LOCKED", lockedBy="pipeline-run-1")
    mock_db.fixture.find_unique.side_effect = [available_bench, locked_bench]

    with patch("api.v2.fixtures.benches.log_audit") as mock_audit:
        response = authed_client.post(
            "/v2/fixtures/benches/bench-1/lock",
            data=json.dumps({"lockedBy": "pipeline-run-1"}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "LOCKED"
    assert data["data"]["lockedBy"] == "pipeline-run-1"
    mock_db.fixture.update.assert_called_once()
    mock_audit.assert_called_once()


def test_lock_bench_already_locked(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench(status="LOCKED", lockedBy="other-run")

    response = authed_client.post(
        "/v2/fixtures/benches/bench-1/lock",
        data=json.dumps({"lockedBy": "new-run"}),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "other-run" in data["errors"][0]["message"]


def test_lock_bench_offline(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench(status="OFFLINE")

    response = authed_client.post(
        "/v2/fixtures/benches/bench-1/lock",
        data=json.dumps({"lockedBy": "run-1"}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "OFFLINE" in data["errors"][0]["message"]


def test_lock_bench_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client.post(
        "/v2/fixtures/benches/bad-id/lock",
        data=json.dumps({"lockedBy": "run-1"}),
    )

    assert response.status_code == 404


def test_lock_bench_missing_locked_by(authed_client, mock_db):
    # Send lockedBy as empty string — triggers specific validation error
    response = authed_client.post(
        "/v2/fixtures/benches/bench-1/lock",
        data=json.dumps({"lockedBy": ""}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "lockedBy" in data["errors"][0]["message"]


def test_lock_bench_requires_auth(client):
    response = client.post(
        "/v2/fixtures/benches/bench-1/lock",
        data=json.dumps({"lockedBy": "run-1"}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# unlock_bench — POST /v2/fixtures/benches/<id>/unlock
# ---------------------------------------------------------------------------

def test_unlock_bench_success(authed_client, mock_db):
    locked_bench = _make_bench(status="LOCKED", lockedBy="pipeline-run-1")
    available_bench = _make_bench(status="AVAILABLE", lockedBy=None)
    mock_db.fixture.find_unique.side_effect = [locked_bench, available_bench]

    with patch("api.v2.fixtures.benches.log_audit") as mock_audit:
        response = authed_client.post("/v2/fixtures/benches/bench-1/unlock")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "AVAILABLE"
    assert data["data"]["lockedBy"] is None
    mock_db.fixture.update.assert_called_once()
    mock_audit.assert_called_once()


def test_unlock_bench_not_locked(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = _make_bench(status="AVAILABLE")

    response = authed_client.post("/v2/fixtures/benches/bench-1/unlock")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "not locked" in data["errors"][0]["message"]


def test_unlock_bench_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client.post("/v2/fixtures/benches/bad-id/unlock")

    assert response.status_code == 404


def test_unlock_bench_requires_auth(client):
    response = client.post("/v2/fixtures/benches/bench-1/unlock")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# discover_mtibs — GET /v2/fixtures/benches/discover
# ---------------------------------------------------------------------------

def test_discover_mtibs_success(authed_client, mock_db):
    """Returns empty list when K8s unavailable (graceful fallback)."""
    mock_db.fixtureslot.find_many.return_value = []
    mock_db.node.find_many.return_value = []

    response = authed_client.get("/v2/fixtures/benches/discover")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data["data"], list)


def test_discover_mtibs_requires_auth(client):
    response = client.get("/v2/fixtures/benches/discover")
    assert response.status_code == 401


def test_discover_mtibs_filters_registered(authed_client, mock_db):
    """Fixtures with registered node IPs should not appear as unregistered."""
    mock_db.fixtureslot.find_many.return_value = [
        make_obj(node=make_obj(ipAddress="10.4.45.33")),
    ]
    mock_db.node.find_many.return_value = [
        make_obj(hostname="mtib-33", ipAddress="10.4.45.33"),
    ]

    response = authed_client.get("/v2/fixtures/benches/discover")

    assert response.status_code == 200
    data = json.loads(response.data)
    # No K8s nodes available in test env, so unregistered list is empty
    assert data["data"] == []


# ---------------------------------------------------------------------------
# get_bench_profile — GET /v2/fixtures/benches/<id>/profile
# ---------------------------------------------------------------------------

def test_get_bench_profile_success(authed_client, mock_db):
    bench = _make_bench()
    bench.design.profileTemplate = {
        "uart_app_path": "/dev/ttyUSB1",
        "dut": {"snr": "default"},
    }
    bench.profileOverrides = {"station_id": "overridden"}
    mock_db.fixture.find_unique.return_value = bench

    response = authed_client.get("/v2/fixtures/benches/bench-1/profile")

    assert response.status_code == 200
    data = json.loads(response.data)
    profile = data["data"]
    # Station ID injected from fixture
    assert profile["station_id"] == "bench-33"
    # DUT info from slot
    assert profile["dut"]["device_id"] == "70B3D584C01E1FCC"
    assert profile["dut"]["snr"] == "0964"
    assert profile["dut"]["imei"] == "355025931735979"
    # Hardware paths from slot
    assert profile["uart_app_path"] == "/dev/ttyUSB1"
    assert profile["uart_comms_path"] == "/dev/ttyUSB0"
    assert profile["jlink_app_serial"] == "821009543"
    # Capabilities from design
    assert profile["capabilities"] == ["jlink", "button"]
    # Product info
    assert profile["product"]["slug"] == "alpha"


def test_get_bench_profile_not_found(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = None

    response = authed_client.get("/v2/fixtures/benches/bad-id/profile")

    assert response.status_code == 404


def test_get_bench_profile_no_design(authed_client, mock_db):
    """Bench without design returns profile with only slot/station data."""
    bench = _make_bench(design=None)
    mock_db.fixture.find_unique.return_value = bench

    response = authed_client.get("/v2/fixtures/benches/bench-1/profile")

    assert response.status_code == 200
    data = json.loads(response.data)
    profile = data["data"]
    assert profile["station_id"] == "bench-33"
    assert "capabilities" not in profile


def test_get_bench_profile_deep_merge_overrides(authed_client, mock_db):
    """Profile overrides deep-merge into template; slot data is injected last."""
    bench = _make_bench()
    # Template has a nested object; override merges into it
    bench.design.profileTemplate = {"config": {"timeout": 30, "retries": 3}}
    bench.profileOverrides = {"config": {"timeout": 60}}
    mock_db.fixture.find_unique.return_value = bench

    response = authed_client.get("/v2/fixtures/benches/bench-1/profile")

    assert response.status_code == 200
    data = json.loads(response.data)
    profile = data["data"]
    # Override applied: timeout updated
    assert profile["config"]["timeout"] == 60
    # Template value kept: retries untouched
    assert profile["config"]["retries"] == 3


def test_get_bench_profile_requires_auth(client):
    response = client.get("/v2/fixtures/benches/bench-1/profile")
    assert response.status_code == 401
