"""Tests for the zip-based asset upload and file analysis endpoints."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from api.v2.assets.zip_upload import (
    _build_match_reason,
    _detect_file_type,
    _detect_processor,
    _detect_variant,
    _match_file_to_label,
    _try_parse_version,
)
from api.v2.assets.zip_validator import ZipValidationResult
from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2025, 6, 1, tzinfo=timezone.utc)


def _make_zip(files: dict[str, bytes]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def _stage_config(**overrides):
    defaults = dict(
        id="sc-1",
        productId="prod-1",
        stage=4,
        type="VALIDATION",
        name="Stage 4",
        boardRevisionId="rev-1",
        buildMatrixEntries=[
            make_obj(
                label="app",
                processor="nrf52840",
                variant="debug",
                producesHex=True,
                producesCfw=False,
                fwType=None,
            ),
        ],
        boardRevision=make_obj(id="rev-1", version="B0", ckBoardsName="alpha_b0"),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _product(**overrides):
    defaults = dict(id="prod-1", slug="alpha")
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Unit tests — _detect_processor
# ---------------------------------------------------------------------------

def test_detect_processor_nrf52840():
    assert _detect_processor("alpha_nrf52840_debug.hex") == "nrf52840"


def test_detect_processor_nrf9151():
    assert _detect_processor("comms_nrf9151_release.cfw") == "nrf9151"


def test_detect_processor_nrf9160():
    assert _detect_processor("comms_nrf9160.hex") == "nrf9160"


def test_detect_processor_none():
    assert _detect_processor("firmware.hex") is None


# ---------------------------------------------------------------------------
# Unit tests — _detect_variant
# ---------------------------------------------------------------------------

def test_detect_variant_debug():
    assert _detect_variant("alpha_debug.hex") == "debug"


def test_detect_variant_release():
    assert _detect_variant("alpha_release.hex") == "release"


def test_detect_variant_none():
    assert _detect_variant("alpha.hex") is None


# ---------------------------------------------------------------------------
# Unit tests — _detect_file_type
# ---------------------------------------------------------------------------

def test_detect_file_type_hex():
    assert _detect_file_type("firmware.hex") == "plaintextHex"


def test_detect_file_type_cfw():
    assert _detect_file_type("firmware.cfw") == "encryptedCfw"


def test_detect_file_type_json():
    assert _detect_file_type("build.json") == "manifest"


def test_detect_file_type_bin():
    assert _detect_file_type("firmware.bin") == "other"


def test_detect_file_type_unknown():
    assert _detect_file_type("noext") == "unknown"


# ---------------------------------------------------------------------------
# Unit tests — _match_file_to_label
# ---------------------------------------------------------------------------

def test_match_high_confidence():
    entries = [
        make_obj(
            label="app",
            processor="nrf52840",
            variant="debug",
            producesHex=True,
            producesCfw=False,
            fwType=None,
        ),
    ]
    match, confidence = _match_file_to_label(
        "alpha_nrf52840_debug.hex", "nrf52840", "debug", "plaintextHex", entries, set()
    )
    assert match is not None
    assert match.label == "app"
    assert confidence == "high"


def test_match_medium_confidence():
    entries = [
        make_obj(
            label="app",
            processor="nrf52840",
            variant="debug",
            producesHex=True,
            producesCfw=False,
            fwType=None,
        ),
    ]
    match, confidence = _match_file_to_label(
        "alpha_nrf52840.hex", "nrf52840", None, "plaintextHex", entries, set()
    )
    assert match is not None
    assert match.label == "app"
    assert confidence == "medium"


def test_match_no_match():
    entries = [
        make_obj(
            label="app",
            processor="nrf52840",
            variant="debug",
            producesHex=True,
            producesCfw=False,
            fwType=None,
        ),
    ]
    match, confidence = _match_file_to_label(
        "readme.txt", None, None, "unknown", entries, set()
    )
    assert match is None
    assert confidence is None


def test_match_skip_labels_excluded():
    entries = [
        make_obj(
            label="app",
            processor="nrf52840",
            variant="debug",
            producesHex=True,
            producesCfw=False,
            fwType=None,
        ),
    ]
    match, confidence = _match_file_to_label(
        "alpha_nrf52840_debug.hex", "nrf52840", "debug", "plaintextHex", entries, {"app"}
    )
    assert match is None
    assert confidence is None


# ---------------------------------------------------------------------------
# Unit tests — _build_match_reason
# ---------------------------------------------------------------------------

def test_build_match_reason_full():
    reason = _build_match_reason("nrf52840", "debug", "plaintextHex", "app")
    assert "nrf52840" in reason
    assert "debug" in reason
    assert "hex" in reason
    assert "app" in reason


def test_build_match_reason_cfw():
    reason = _build_match_reason(None, None, "encryptedCfw", "comms")
    assert "cfw" in reason
    assert "comms" in reason


def test_build_match_reason_no_signals():
    reason = _build_match_reason(None, None, "other", "app")
    assert "app" in reason


# ---------------------------------------------------------------------------
# Unit tests — _try_parse_version
# ---------------------------------------------------------------------------

def test_try_parse_version_from_build_json():
    buf = _make_zip({"app/build.json": json.dumps({"version": "1.2.3"}).encode()})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version == "1.2.3"
    assert source == "build.json"
    zf.close()


def test_try_parse_version_from_filename():
    buf = _make_zip({"app/alpha_v1.2.3_debug.hex": b""})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version == "1.2.3"
    assert source == "filename"
    zf.close()


def test_try_parse_version_not_found():
    buf = _make_zip({"app/firmware.bin": b"data"})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version is None
    assert source is None
    zf.close()


def test_try_parse_version_skips_unknown():
    buf = _make_zip({"app/build.json": json.dumps({"version": "unknown"}).encode()})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version is None or source != "build.json"
    zf.close()


def test_try_parse_version_invalid_json():
    buf = _make_zip({"app/build.json": b"not json"})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version is None
    assert source is None
    zf.close()


def test_try_parse_version_four_part():
    buf = _make_zip({"app/alpha_v1.2.3.4_debug.hex": b""})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version == "1.2.3.4"
    assert source == "filename"
    zf.close()


def test_try_parse_version_from_hex_content():
    hex_content = b"some binary APP_VERSION 2.5.0 stuff"
    buf = _make_zip({"app/firmware.hex": hex_content})
    zf = zipfile.ZipFile(buf)
    version, source = _try_parse_version(zf)
    assert version == "2.5.0"
    assert source == "hex_content"
    zf.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_storage():
    mock_client = MagicMock()
    with patch("api.v2.assets.zip_upload.get_storage_client", return_value=mock_client):
        with patch("api.v2.assets.zip_upload.get_bucket_name", return_value="test-bucket"):
            yield mock_client


@pytest.fixture(autouse=True)
def _mock_audit():
    with patch("api.v2.assets.zip_upload.log_audit"):
        yield


@pytest.fixture(autouse=True)
def _mock_canonical_names():
    with patch("api.v2.assets.zip_upload.product_asset_key", return_value="mock/key"):
        with patch("api.v2.assets.zip_upload.canonical_asset_filename", return_value="canonical.hex"):
            yield


# ---------------------------------------------------------------------------
# Endpoint tests — validate-zip
# ---------------------------------------------------------------------------

class TestValidateZip:

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_missing_stage_config_id(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_stage_config_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_stage_config_wrong_product(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config(productId="other")

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_no_file(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_non_zip_file(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={
                "stageConfigId": "sc-1",
                "file": (io.BytesIO(b"not a zip"), "firmware.txt"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_no_build_matrix_entries(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config(buildMatrixEntries=[])

        buf = _make_zip({"app/firmware.hex": b"\xff" * 100})
        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/validate-zip",
            data={
                "stageConfigId": "sc-1",
                "file": (buf, "firmware.zip"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        buf = _make_zip({"app/firmware.hex": b"\xff" * 100})
        with patch("api.v2.assets.zip_upload.validate_zip") as mock_validate:
            mock_validate.return_value = ZipValidationResult(
                valid=True,
                errors=[],
                warnings=[],
                labels_found=["app"],
                file_count=1,
                parsed_version="1.0.0",
                version_source="build.json",
            )
            resp = authed_client.post(
                "/v2/products/prod-1/asset-sets/validate-zip",
                data={
                    "stageConfigId": "sc-1",
                    "file": (buf, "firmware.zip"),
                },
                content_type="multipart/form-data",
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["valid"] is True
        assert body["data"]["parsedVersion"] == "1.0.0"


# ---------------------------------------------------------------------------
# Endpoint tests — analyze-files
# ---------------------------------------------------------------------------

class TestAnalyzeFiles:

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/analyze-files",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_missing_stage_config_id(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/analyze-files",
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_stage_config_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/analyze-files",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_no_files(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/analyze-files",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_success(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/analyze-files",
            data={
                "stageConfigId": "sc-1",
                "files": (io.BytesIO(b"\xff" * 100), "alpha_nrf52840_debug.hex"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "files" in body["data"]
        assert len(body["data"]["files"]) == 1
        assert body["data"]["files"][0]["detectedProcessor"] == "nrf52840"
        assert body["data"]["files"][0]["suggestedLabel"] == "app"


# ---------------------------------------------------------------------------
# Endpoint tests — upload-files
# ---------------------------------------------------------------------------

class TestUploadFiles:

    def test_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={"stageConfigId": "sc-1", "version": "1.0.0"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_missing_stage_config_id(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={"version": "1.0.0"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_missing_version(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={"stageConfigId": "sc-1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_no_files(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={"stageConfigId": "sc-1", "version": "1.0.0"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_files_labels_count_mismatch(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        from werkzeug.datastructures import FileStorage, MultiDict

        data = MultiDict()
        data.add("stageConfigId", "sc-1")
        data.add("version", "1.0.0")
        data.add("files", FileStorage(stream=io.BytesIO(b"\xff" * 10), filename="fw1.hex"))
        data.add("files", FileStorage(stream=io.BytesIO(b"\xff" * 10), filename="fw2.hex"))
        data.add("labels", "app")

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_invalid_label(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()

        from werkzeug.datastructures import MultiDict, FileStorage

        data = MultiDict()
        data.add("stageConfigId", "sc-1")
        data.add("version", "1.0.0")
        data.add("labels", "nonexistent")

        files = MultiDict()
        files.add("files", FileStorage(
            stream=io.BytesIO(b"\xff" * 10),
            filename="firmware.hex",
            content_type="application/octet-stream",
        ))

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={**data, **files},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_duplicate_version(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config()
        mock_db.assetset.find_first.return_value = make_obj(id="existing-as")

        from werkzeug.datastructures import MultiDict, FileStorage

        data = MultiDict()
        data.add("stageConfigId", "sc-1")
        data.add("version", "1.0.0")
        data.add("labels", "app")

        files = MultiDict()
        files.add("files", FileStorage(
            stream=io.BytesIO(b"\xff" * 10),
            filename="alpha_nrf52840_debug.hex",
            content_type="application/octet-stream",
        ))

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={**data, **files},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 409

    def test_stage_config_wrong_product(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = _product()
        mock_db.productstageconfig.find_unique.return_value = _stage_config(productId="other")

        resp = authed_client.post(
            "/v2/products/prod-1/asset-sets/upload-files",
            data={"stageConfigId": "sc-1", "version": "1.0.0"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
