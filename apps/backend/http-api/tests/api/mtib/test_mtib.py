"""Integration tests for the MTIB API.

Endpoints under test:
    GET  /v2/devices/mtib/list       — list_mtibs (paginated)
    GET  /v2/devices/mtib/get        — get_mtib (by hostname query param)
    POST /v2/devices/mtib/register   — register_mtib
    POST /v2/devices/mtib/unregister — unregister_mtib
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mtib_defaults(**overrides):
    """Build a mock MTIB row with sensible defaults."""
    defaults = {
        "id": "verdin-imx8mm-12345",
        "name": "verdin-bench-01",
        "type": "VALIDATION",
        "features": ["JOULESCOPE"],
        "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "appIdMappings": [],
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _app_id_mapping(jlink=821009537, appId=108, app_name="comms", chipset="nRF9151",
                    target="NRF9151", notes=None):
    """Build a mock appId mapping row."""
    return make_obj(
        jlink=jlink,
        appId=appId,
        app=make_obj(
            name=app_name,
            chipset=chipset,
            target=target,
            notes=notes,
        ),
    )


# ---------------------------------------------------------------------------
# GET /v2/devices/mtib/list — list_mtibs
# ---------------------------------------------------------------------------

class TestListMtibs:
    """Tests for the list_mtibs endpoint."""

    @patch("api.v2.mtib.list.get_logger")
    def test_list_mtibs_success(self, mock_get_logger, authed_client, mock_db):
        """Should return paginated MTIB list."""
        mock_get_logger.return_value = MagicMock()

        mappings = [_app_id_mapping(), _app_id_mapping(jlink=821009546, appId=109, app_name="app")]
        mtib1 = _mtib_defaults(appIdMappings=mappings)
        mtib2 = _mtib_defaults(
            id="verdin-imx8mm-67890",
            name="verdin-bench-02",
            type="MANUFACTURING",
            features=["JOULESCOPE", "MOTION"],
            appIdMappings=[],
        )

        mock_db.mtib.count.return_value = 2
        mock_db.mtib.find_many.return_value = [mtib1, mtib2]

        response = authed_client.get("/v2/devices/mtib/list")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        payload = body["data"]
        assert payload["pagination"]["total"] == 2
        assert payload["pagination"]["page"] == 1
        assert len(payload["data"]) == 2

        first = payload["data"][0]
        assert first["hostname"] == "verdin-imx8mm-12345"
        assert first["name"] == "verdin-bench-01"
        assert first["type"] == "validation"
        assert first["features"] == ["joulescope"]
        assert first["appIdCount"] == 2
        assert "createdAt" in first
        assert "updatedAt" in first

        second = payload["data"][1]
        assert second["type"] == "manufacturing"
        assert second["features"] == ["joulescope", "motion"]
        assert second["appIdCount"] == 0

    @patch("api.v2.mtib.list.get_logger")
    def test_list_mtibs_empty(self, mock_get_logger, authed_client, mock_db):
        """Should return empty list when no MTIBs exist."""
        mock_get_logger.return_value = MagicMock()

        mock_db.mtib.count.return_value = 0
        mock_db.mtib.find_many.return_value = []

        response = authed_client.get("/v2/devices/mtib/list")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0

    @patch("api.v2.mtib.list.get_logger")
    def test_list_mtibs_pagination(self, mock_get_logger, authed_client, mock_db):
        """Should respect page and limit query params."""
        mock_get_logger.return_value = MagicMock()

        mock_db.mtib.count.return_value = 75
        mock_db.mtib.find_many.return_value = [_mtib_defaults()]

        response = authed_client.get("/v2/devices/mtib/list?page=2&limit=25")
        assert response.status_code == 200

        body = json.loads(response.data)
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 2
        assert pagination["limit"] == 25
        assert pagination["total"] == 75
        assert pagination["pages"] == 3  # ceil(75/25)

        call_kwargs = mock_db.mtib.find_many.call_args
        assert call_kwargs.kwargs["skip"] == 25  # (2-1)*25
        assert call_kwargs.kwargs["take"] == 25

    def test_list_mtibs_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/devices/mtib/list")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/devices/mtib/get — get_mtib
# ---------------------------------------------------------------------------

class TestGetMtib:
    """Tests for the get_mtib endpoint."""

    @patch("api.v2.mtib.get.get_logger")
    def test_get_mtib_success(self, mock_get_logger, authed_client, mock_db):
        """Should return full MTIB details including appId mappings."""
        mock_get_logger.return_value = MagicMock()

        mappings = [
            _app_id_mapping(jlink=821009537, appId=108, app_name="comms", chipset="nRF9151"),
            _app_id_mapping(jlink=821009546, appId=109, app_name="app", chipset="nRF52840"),
        ]
        mtib = _mtib_defaults(appIdMappings=mappings)
        mock_db.mtib.find_unique.return_value = mtib

        response = authed_client.get("/v2/devices/mtib/get?hostname=verdin-imx8mm-12345")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []

        data = body["data"]
        assert data["hostname"] == "verdin-imx8mm-12345"
        assert data["name"] == "verdin-bench-01"
        assert data["type"] == "validation"
        assert data["features"] == ["joulescope"]
        assert len(data["appIds"]) == 2

        first_mapping = data["appIds"][0]
        assert first_mapping["jlink"] == 821009537
        assert first_mapping["appId"] == 108
        assert first_mapping["appName"] == "comms"
        assert first_mapping["chipset"] == "nRF9151"

    @patch("api.v2.mtib.get.get_logger")
    def test_get_mtib_not_found(self, mock_get_logger, authed_client, mock_db):
        """Should return 404 for a non-existent MTIB."""
        mock_get_logger.return_value = MagicMock()
        mock_db.mtib.find_unique.return_value = None

        response = authed_client.get("/v2/devices/mtib/get?hostname=nonexistent-host")
        assert response.status_code == 404

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    @patch("api.v2.mtib.get.get_logger")
    def test_get_mtib_missing_hostname(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when hostname query param is missing."""
        mock_get_logger.return_value = MagicMock()

        response = authed_client.get("/v2/devices/mtib/get")
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "hostname" in body["errors"][0]["message"].lower()

    def test_get_mtib_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/devices/mtib/get?hostname=verdin-imx8mm-12345")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/devices/mtib/register — register_mtib
# ---------------------------------------------------------------------------

class TestRegisterMtib:
    """Tests for the register_mtib endpoint."""

    @patch("api.v2.mtib.register.log_audit")
    @patch("api.v2.mtib.register.get_core_v1_api")
    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_success(self, mock_get_logger, mock_k8s_api, mock_audit,
                                   authed_client, mock_db):
        """Should register a new MTIB and return 201."""
        mock_get_logger.return_value = MagicMock()
        mock_k8s_api.return_value.read_node.return_value = MagicMock()

        # No existing MTIB
        mock_db.mtib.find_unique.return_value = None

        # AppIds exist in DB
        mock_db.appid.find_many.return_value = [
            make_obj(appId=108),
            make_obj(appId=109),
        ]

        # Mock transaction
        mock_tx = MagicMock()
        created_mtib = make_obj(id="verdin-imx8mm-12345", name="verdin-bench-01")
        mock_tx.mtib.create.return_value = created_mtib
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        mock_db.tx = MagicMock(return_value=mock_tx)

        payload = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": ["joulescope"],
            "appIds": [
                {"jlink": 821009537, "appId": 108},
                {"jlink": 821009546, "appId": 109},
            ],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 201

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["status"] == "registered"
        assert body["data"]["hostname"] == "verdin-imx8mm-12345"
        assert body["data"]["name"] == "verdin-bench-01"

        mock_audit.assert_called_once()

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_missing_name(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when name is missing."""
        mock_get_logger.return_value = MagicMock()

        payload = {
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": [],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "name" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_missing_hostname(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when hostname is missing."""
        mock_get_logger.return_value = MagicMock()

        payload = {
            "name": "verdin-bench-01",
            "mtibType": "validation",
            "features": [],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "hostname" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_invalid_type(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when mtibType is not valid."""
        mock_get_logger.return_value = MagicMock()

        payload = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "invalid",
            "features": [],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "mtibtype" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_name_must_start_with_verdin(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when name does not start with 'verdin-'."""
        mock_get_logger.return_value = MagicMock()

        payload = {
            "name": "my-mtib-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": [],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert "verdin-" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.register.get_core_v1_api")
    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_already_exists(self, mock_get_logger, mock_k8s_api,
                                          authed_client, mock_db):
        """Should return 409 when MTIB with hostname already exists."""
        mock_get_logger.return_value = MagicMock()

        mock_db.mtib.find_unique.return_value = _mtib_defaults()

        payload = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": [],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 409

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_invalid_feature(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 with invalid feature name."""
        mock_get_logger.return_value = MagicMock()

        payload = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": ["invalid_feature"],
            "appIds": [],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert "invalid_feature" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.register.get_core_v1_api")
    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_missing_app_ids(self, mock_get_logger, mock_k8s_api,
                                           authed_client, mock_db):
        """Should return 400 when referenced appIds do not exist."""
        mock_get_logger.return_value = MagicMock()
        mock_k8s_api.return_value.read_node.return_value = MagicMock()

        mock_db.mtib.find_unique.return_value = None
        # Only appId 108 exists in DB, 999 does not
        mock_db.appid.find_many.return_value = [make_obj(appId=108)]

        payload = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": [],
            "appIds": [
                {"jlink": 821009537, "appId": 108},
                {"jlink": 821009546, "appId": 999},
            ],
        }

        response = authed_client.post("/v2/devices/mtib/register", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert "999" in body["errors"][0]["message"]

    @patch("api.v2.mtib.register.get_logger")
    def test_register_mtib_empty_body(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 with empty/null JSON body."""
        mock_get_logger.return_value = MagicMock()

        response = authed_client.post(
            "/v2/devices/mtib/register",
            data=json.dumps(None),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_register_mtib_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/v2/devices/mtib/register", data=json.dumps({}))
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/devices/mtib/unregister — unregister_mtib
# ---------------------------------------------------------------------------

class TestUnregisterMtib:
    """Tests for the unregister_mtib endpoint."""

    @patch("api.v2.mtib.unregister.log_audit")
    @patch("api.v2.mtib.unregister.get_logger")
    def test_unregister_mtib_success(self, mock_get_logger, mock_audit,
                                     authed_client, mock_db):
        """Should unregister an existing MTIB and return 200."""
        mock_get_logger.return_value = MagicMock()

        mock_db.mtib.find_unique.return_value = _mtib_defaults()

        payload = {"hostname": "verdin-imx8mm-12345"}
        response = authed_client.post("/v2/devices/mtib/unregister", data=json.dumps(payload))
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["status"] == "unregistered"
        assert body["data"]["hostname"] == "verdin-imx8mm-12345"

        mock_db.mtib.delete.assert_called_once_with(where={"id": "verdin-imx8mm-12345"})
        mock_audit.assert_called_once()

    @patch("api.v2.mtib.unregister.get_logger")
    def test_unregister_mtib_not_found(self, mock_get_logger, authed_client, mock_db):
        """Should return 404 when MTIB does not exist."""
        mock_get_logger.return_value = MagicMock()

        mock_db.mtib.find_unique.return_value = None

        payload = {"hostname": "nonexistent-host"}
        response = authed_client.post("/v2/devices/mtib/unregister", data=json.dumps(payload))
        assert response.status_code == 404

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    @patch("api.v2.mtib.unregister.get_logger")
    def test_unregister_mtib_missing_hostname(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 when hostname field is missing from a valid body."""
        mock_get_logger.return_value = MagicMock()

        payload = {"hostname": ""}
        response = authed_client.post("/v2/devices/mtib/unregister", data=json.dumps(payload))
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "hostname" in body["errors"][0]["message"].lower()

    @patch("api.v2.mtib.unregister.get_logger")
    def test_unregister_mtib_empty_body(self, mock_get_logger, authed_client, mock_db):
        """Should return 400 with empty/null JSON body."""
        mock_get_logger.return_value = MagicMock()

        response = authed_client.post(
            "/v2/devices/mtib/unregister",
            data=json.dumps(None),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_unregister_mtib_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/v2/devices/mtib/unregister", data=json.dumps({}))
        assert response.status_code == 401
