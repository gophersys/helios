"""Extended tests for board_revisions.py — deprecation cascade and modem firmware."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


def _board():
    return make_obj(id="board-1", productId="prod-1", name="Main Board")


def _revision(**overrides):
    defaults = dict(
        id="rev-1", boardId="board-1", version="1.0",
        ckBoardsName="alpha_b0", socs=[], status="ACTIVE",
        notes=None, modemStorageKey=None, modemVersion=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestDeprecationCascade:
    """Tests for deprecation cascade when updating board revision status."""

    def test_update_to_deprecated_disables_active_stage_configs(self, authed_client, mock_db):
        """Setting status=DEPRECATED disables all linked enabled stage configs."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()

        active_configs = [
            make_obj(id="sc-1", stage=1, name="Smoke"),
            make_obj(id="sc-2", stage=2, name="Driver"),
        ]
        mock_db.productstageconfig.find_many.return_value = active_configs
        mock_db.boardrevision.find_unique.return_value = _revision(status="DEPRECATED")

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.put(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1",
                data=json.dumps({"status": "DEPRECATED"}),
            )

        assert response.status_code == 200
        mock_db.productstageconfig.update_many.assert_called_once()
        body = json.loads(response.data)
        assert "disabledStages" in body["data"]
        assert len(body["data"]["disabledStages"]) == 2

    def test_update_to_eol_disables_active_stage_configs(self, authed_client, mock_db):
        """Setting status=EOL also disables linked enabled stage configs."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()

        active_configs = [make_obj(id="sc-1", stage=1, name="Smoke")]
        mock_db.productstageconfig.find_many.return_value = active_configs
        mock_db.boardrevision.find_unique.return_value = _revision(status="EOL")

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.put(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1",
                data=json.dumps({"status": "EOL"}),
            )

        assert response.status_code == 200
        mock_db.productstageconfig.update_many.assert_called_once()

    def test_update_to_active_does_not_cascade(self, authed_client, mock_db):
        """Setting status=ACTIVE does not touch stage configs."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision(status="DEPRECATED")
        mock_db.boardrevision.find_unique.return_value = _revision(status="ACTIVE")

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.put(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1",
                data=json.dumps({"status": "ACTIVE"}),
            )

        assert response.status_code == 200
        mock_db.productstageconfig.update_many.assert_not_called()
        body = json.loads(response.data)
        assert "disabledStages" not in body["data"]

    def test_update_deprecated_with_no_active_configs_no_cascade(self, authed_client, mock_db):
        """Setting DEPRECATED when no enabled stage configs exist — no update_many call."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()
        mock_db.productstageconfig.find_many.return_value = []  # no active configs
        mock_db.boardrevision.find_unique.return_value = _revision(status="DEPRECATED")

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.put(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1",
                data=json.dumps({"status": "DEPRECATED"}),
            )

        assert response.status_code == 200
        mock_db.productstageconfig.update_many.assert_not_called()


class TestGetBoardRevision:
    """Tests for GET /v2/products/<pid>/boards/<bid>/revisions/<rid>."""

    def test_get_board_revision_success(self, authed_client, mock_db):
        """GET returns revision when it belongs to the product."""
        board = _board()
        rev = _revision()
        rev.board = board
        mock_db.boardrevision.find_first.return_value = rev

        response = authed_client.get("/v2/products/prod-1/boards/board-1/revisions/rev-1")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["version"] == "1.0"

    def test_get_board_revision_wrong_product_returns_404(self, authed_client, mock_db):
        """GET returns 404 when revision's board belongs to different product."""
        wrong_board = make_obj(id="board-1", productId="other-product", name="Other")
        rev = _revision()
        rev.board = wrong_board
        mock_db.boardrevision.find_first.return_value = rev

        response = authed_client.get("/v2/products/prod-1/boards/board-1/revisions/rev-1")

        assert response.status_code == 404

    def test_get_board_revision_not_found(self, authed_client, mock_db):
        """GET returns 404 when revision does not exist."""
        mock_db.boardrevision.find_first.return_value = None

        response = authed_client.get("/v2/products/prod-1/boards/board-1/revisions/nonexistent")

        assert response.status_code == 404


class TestModemFirmware:
    """Tests for modem firmware upload/download/delete endpoints."""

    @pytest.fixture(autouse=True)
    def _mock_storage(self):
        mock_client = MagicMock()
        mock_client.put_object = MagicMock()
        mock_client.remove_object = MagicMock()
        with patch("api.v2.products.board_revisions.get_storage_client", return_value=mock_client):
            with patch("api.v2.products.board_revisions.get_bucket_name", return_value="test-bucket"):
                with patch("api.v2.products.board_revisions.storage_key", return_value="firmware/modem/rev-1/1.0/modem.zip"):
                    self.mock_storage = mock_client
                    yield

    def test_upload_modem_firmware_success(self, authed_client, mock_db):
        """POST uploads modem firmware and creates ModemFirmware record."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()
        mock_db.modemfirmware.find_first.return_value = None  # no duplicate
        mock_db.modemfirmware.create.return_value = make_obj(
            id="mfw-1", boardRevisionId="rev-1", version="1.0.0",
            filename="modem.zip", storageKey="firmware/modem/rev-1/1.0.0/modem.zip",
            sizeBytes=26, checksum="abc123", notes=None,
            createdById=None, createdAt="2026-01-01T00:00:00Z",
        )

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.post(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware",
                data={
                    "file": (BytesIO(b"fake modem firmware content"), "modem.zip"),
                    "version": "1.0.0",
                },
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert body["data"]["version"] == "1.0.0"
        mock_db.modemfirmware.create.assert_called_once()

    def test_upload_modem_firmware_no_file_returns_400(self, authed_client, mock_db):
        """POST without file field returns 400."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()

        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware",
            data={"version": "1.0.0"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400

    def test_upload_modem_firmware_no_version_returns_400(self, authed_client, mock_db):
        """POST without version field returns 400."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision()

        response = authed_client.post(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware",
            data={"file": (BytesIO(b"content"), "modem.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400

    def test_upload_modem_firmware_board_not_found(self, authed_client, mock_db):
        """POST returns 404 when board does not exist."""
        mock_db.board.find_first.return_value = None

        response = authed_client.post(
            "/v2/products/prod-1/boards/bad-board/revisions/rev-1/modem-firmware",
            data={"file": (BytesIO(b"content"), "modem.zip"), "version": "1.0"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 404

    def test_download_modem_firmware_no_firmware_returns_404(self, authed_client, mock_db):
        """GET returns 404 when no modem firmware is configured."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision(modemStorageKey=None)

        response = authed_client.get(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware"
        )

        assert response.status_code == 404

    def test_download_modem_firmware_success(self, authed_client, mock_db):
        """GET returns file content with attachment disposition."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision(
            modemStorageKey="firmware/modem/rev-1/1.0/modem.zip"
        )
        fake_response = MagicMock()
        fake_response.read.return_value = b"modem firmware bytes"
        fake_response.close = MagicMock()
        fake_response.release_conn = MagicMock()
        self.mock_storage.get_object.return_value = fake_response

        response = authed_client.get(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware"
        )

        assert response.status_code == 200
        assert "attachment" in response.headers.get("Content-Disposition", "")

    def test_delete_modem_firmware_success(self, authed_client, mock_db):
        """DELETE removes modem firmware key from board revision."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision(
            modemStorageKey="firmware/modem/rev-1/1.0/modem.zip",
            modemVersion="1.0",
        )

        with patch("api.v2.products.board_revisions.log_audit"):
            response = authed_client.delete(
                "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware"
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["deleted"] is True
        mock_db.boardrevision.update.assert_called_once()

    def test_delete_modem_firmware_none_configured_returns_404(self, authed_client, mock_db):
        """DELETE returns 404 when no modem firmware is configured."""
        mock_db.board.find_first.return_value = _board()
        mock_db.boardrevision.find_first.return_value = _revision(modemStorageKey=None)

        response = authed_client.delete(
            "/v2/products/prod-1/boards/board-1/revisions/rev-1/modem-firmware"
        )

        assert response.status_code == 404

    # TODO: test_upload_modem_firmware_replaces_old_key_removes_from_storage
    # TODO: test_upload_modem_firmware_empty_file_returns_400
