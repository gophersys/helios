"""Integration tests for the Assets upload endpoint."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2025, 6, 1, tzinfo=timezone.utc)


def _asset_set_obj(**overrides):
    defaults = dict(
        id="as-1",
        productId="prod-1",
        status="PENDING",
        version="0.8.3",
        variant="debug",
        stage=1,
        stageType="VALIDATION",
        product=make_obj(id="prod-1", slug="alpha"),
        boardRevision=make_obj(id="rev-1", version="b0"),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _asset_obj(**overrides):
    defaults = dict(
        id="asset-1",
        assetSetId="as-1",
        label="MFG_APP_DEBUG",
        role="app",
        processor="nrf52840",
        artifactType="plaintextHex",
        storageKey="products/alpha/b0/validation/1/0.8.3-debug/MFG_APP_DEBUG/app_nrf52840.hex",
        filename="app_nrf52840.hex",
        sizeBytes=102400,
        checksum="abc123",
        contentType="application/octet-stream",
        createdAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_storage():
    """Prevent real MinIO calls in all tests."""
    mock_client = MagicMock()
    with patch("api.v2.assets.assets.get_storage_client", return_value=mock_client):
        with patch("api.v2.assets.assets.get_bucket_name", return_value="test-bucket"):
            yield mock_client


# ---------------------------------------------------------------------------
# TestUploadAsset
# ---------------------------------------------------------------------------

class TestUploadAsset:
    """Tests for POST /v2/asset-sets/<id>/assets."""

    def test_upload_success(self, authed_client, mock_db):
        """Upload valid asset to PENDING asset set returns 201."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")
        mock_db.asset.create.return_value = _asset_obj()

        with patch("api.v2.assets.assets.log_audit"):
            resp = authed_client.post(
                "/v2/asset-sets/as-1/assets",
                data={
                    "file": (io.BytesIO(b"\xff\xfe" + b"\x00" * 200), "app_nrf52840.hex"),
                    "label": "MFG_APP_DEBUG",
                    "role": "app",
                    "artifactType": "plaintextHex",
                    "processor": "nrf52840",
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["label"] == "MFG_APP_DEBUG"
        assert body["data"]["role"] == "app"
        assert body["data"]["artifactType"] == "plaintextHex"

    def test_upload_cfw_artifact(self, authed_client, mock_db):
        """Upload CFW artifact with encryptedCfw type returns 201."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")
        mock_db.asset.create.return_value = _asset_obj(
            artifactType="encryptedCfw",
            filename="108.0.8.3-BM.cfw",
        )

        with patch("api.v2.assets.assets.log_audit"):
            resp = authed_client.post(
                "/v2/asset-sets/as-1/assets",
                data={
                    "file": (io.BytesIO(b"\x00" * 100), "108.0.8.3-BM.cfw"),
                    "label": "MFG_APP_DEBUG",
                    "role": "comms",
                    "artifactType": "encryptedCfw",
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201

    def test_upload_to_nonexistent_asset_set_returns_404(self, authed_client, mock_db):
        """Upload to nonexistent asset set returns 404."""
        mock_db.assetset.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/asset-sets/nope/assets",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "test.hex"),
                "label": "X",
                "role": "app",
                "artifactType": "plaintextHex",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_upload_to_non_pending_set_returns_400(self, authed_client, mock_db):
        """Upload to asset set that is not PENDING returns 400."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="COMPLETE")

        resp = authed_client.post(
            "/v2/asset-sets/as-1/assets",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "test.hex"),
                "label": "X",
                "role": "app",
                "artifactType": "plaintextHex",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_file_returns_400(self, authed_client, mock_db):
        """Upload without file field returns 400."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")

        resp = authed_client.post(
            "/v2/asset-sets/as-1/assets",
            data={
                "label": "MFG_APP_DEBUG",
                "role": "app",
                "artifactType": "plaintextHex",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_label_returns_400(self, authed_client, mock_db):
        """Upload without label field returns 400."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")

        resp = authed_client.post(
            "/v2/asset-sets/as-1/assets",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "test.hex"),
                "role": "app",
                "artifactType": "plaintextHex",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_role_returns_400(self, authed_client, mock_db):
        """Upload without role field returns 400."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")

        resp = authed_client.post(
            "/v2/asset-sets/as-1/assets",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "test.hex"),
                "label": "MFG_APP_DEBUG",
                "artifactType": "plaintextHex",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_invalid_artifact_type_returns_400(self, authed_client, mock_db):
        """Upload with unknown artifactType returns 400."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")

        resp = authed_client.post(
            "/v2/asset-sets/as-1/assets",
            data={
                "file": (io.BytesIO(b"\x00" * 10), "test.hex"),
                "label": "MFG_APP_DEBUG",
                "role": "app",
                "artifactType": "binaryBlob",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("artifact_type", [
        "plaintextHex", "encryptedCfw", "manifest", "log", "metadata", "other"
    ])
    def test_upload_all_valid_artifact_types(self, authed_client, mock_db, artifact_type):
        """All valid artifactType values are accepted."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")
        mock_db.asset.create.return_value = _asset_obj(artifactType=artifact_type)

        with patch("api.v2.assets.assets.log_audit"):
            resp = authed_client.post(
                "/v2/asset-sets/as-1/assets",
                data={
                    "file": (io.BytesIO(b"\x00" * 10), "test.bin"),
                    "label": "X",
                    "role": "app",
                    "artifactType": artifact_type,
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201

    def test_upload_response_contains_checksum(self, authed_client, mock_db):
        """Upload response includes computed checksum."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")
        mock_db.asset.create.return_value = _asset_obj(checksum="deadbeef1234")

        with patch("api.v2.assets.assets.log_audit"):
            resp = authed_client.post(
                "/v2/asset-sets/as-1/assets",
                data={
                    "file": (io.BytesIO(b"file content"), "test.hex"),
                    "label": "X",
                    "role": "app",
                    "artifactType": "plaintextHex",
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 201
        body = resp.get_json()
        assert "checksum" in body["data"]

    def test_upload_storage_writes_to_minio(self, authed_client, mock_db, _mock_storage):
        """Upload calls MinIO put_object with correct bucket."""
        mock_db.assetset.find_unique.return_value = _asset_set_obj(status="PENDING")
        mock_db.asset.create.return_value = _asset_obj()

        with patch("api.v2.assets.assets.log_audit"):
            authed_client.post(
                "/v2/asset-sets/as-1/assets",
                data={
                    "file": (io.BytesIO(b"\x00" * 50), "app.hex"),
                    "label": "BASE",
                    "role": "app",
                    "artifactType": "plaintextHex",
                },
                content_type="multipart/form-data",
            )

        _mock_storage.put_object.assert_called_once()
        call_args = _mock_storage.put_object.call_args
        assert call_args[0][0] == "test-bucket"

    # TODO: test_upload_missing_artifact_type_returns_400
    # TODO: test_upload_missing_filename_returns_400
