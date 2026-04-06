"""Tests for FirmwareSet endpoints (GET/POST/DELETE /v2/products/<id>/firmware)."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace


def make_obj(**kwargs):
    return SimpleNamespace(**kwargs)


def _set_defaults(**overrides):
    defaults = {
        "id": "set-1",
        "productId": "prod-1",
        "boardRevisionId": None,
        "version": "0.5.2",
        "releaseTrack": "bench",
        "isManufacturing": False,
        "isDebug": False,
        "source": "upload",
        "modemVersion": None,
        "modemStorageKey": None,
        "buildFingerprint": None,
        "status": "active",
        "notes": None,
        "createdAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "builds": [],
        "boardRevision": None,
    }
    defaults.update(overrides)
    return defaults


class TestListFirmwareSets:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.firmwareset.count.return_value = 1
        mock_db.firmwareset.find_many.return_value = [
            make_obj(**_set_defaults()),
        ]

        response = authed_client.get("/v2/products/prod-1/firmware")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]["data"]) == 1
        assert data["data"]["data"][0]["version"] == "0.5.2"
        assert data["data"]["pagination"]["total"] == 1

    def test_empty(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.firmwareset.count.return_value = 0
        mock_db.firmwareset.find_many.return_value = []

        response = authed_client.get("/v2/products/prod-1/firmware")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["data"] == []

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None
        response = authed_client.get("/v2/products/nope/firmware")
        assert response.status_code == 404


class TestCreateFirmwareSet:
    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.firmwareset.create.return_value = make_obj(**_set_defaults())

        response = authed_client.post(
            "/v2/products/prod-1/firmware",
            data=json.dumps({"version": "0.5.2", "releaseTrack": "bench"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["data"]["version"] == "0.5.2"

    def test_missing_version(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        response = authed_client.post(
            "/v2/products/prod-1/firmware",
            data=json.dumps({"releaseTrack": "bench"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_invalid_track(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        response = authed_client.post(
            "/v2/products/prod-1/firmware",
            data=json.dumps({"version": "1.0.0", "releaseTrack": "invalid"}),
            content_type="application/json",
        )
        assert response.status_code == 400


class TestDeleteFirmwareSet:
    def test_success(self, authed_client, mock_db):
        mock_db.firmwareset.find_first.return_value = make_obj(**_set_defaults())
        mock_db.firmwareset.delete.return_value = None

        response = authed_client.delete("/v2/products/prod-1/firmware/set-1")
        assert response.status_code == 200

    def test_not_found(self, authed_client, mock_db):
        mock_db.firmwareset.find_first.return_value = None
        response = authed_client.delete("/v2/products/prod-1/firmware/set-999")
        assert response.status_code == 404
