"""Tests for BuildJobArtifact role/processor/artifactType metadata.

TDD tests written before implementation — verifies:
1. Upload artifact with role/processor/artifactType metadata
2. Serializer includes new fields
3. List artifacts supports filtering by role and artifactType
"""

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 3, 26, 12, 0, 0, tzinfo=timezone.utc)


def _build_obj(**overrides):
    defaults = {
        "id": "build-001",
        "product": make_obj(
            id="prod-alpha", slug="alpha", repoSlug="alpha_fw",
            mfgRepoSlug="alpha_mfg_fw", name="Alpha B0",
        ),
        "productId": "prod-alpha",
        "board": "alpha_b0",
        "target": "app",
        "variant": "debug",
        "mtibRev": "1.2",
        "branch": "main",
        "commitSha": "abc123",
        "status": "SUCCESS",
        "versionMajor": None,
        "versionMinor": None,
        "buildNum": None,
        "versionString": "0.8.3",
        "errorMessage": None,
        "startedAt": None,
        "finishedAt": None,
        "durationSeconds": None,
        "buildLog": None,
        "pipelineRunId": None,
        "webhookData": None,
        "matrixLabel": None,
        "matrixIndex": None,
        "versionBump": False,
        "baseJobId": None,
        "configFlags": None,
        "reusedFromId": None,
        "buildFingerprint": None,
        "artifacts": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _artifact_obj(**overrides):
    defaults = {
        "id": "artifact-001",
        "buildJobId": "build-001",
        "name": "app_nrf52840.hex",
        "storageKey": "firmware-builds/alpha/build-001/app_nrf52840.hex",
        "sizeBytes": 65536,
        "checksum": "abcdef1234567890",
        "role": None,
        "processor": None,
        "artifactType": None,
        "createdAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
#  POST /v2/builds/<id>/artifacts — Upload with metadata
# ---------------------------------------------------------------------------

class TestUploadArtifactMetadata:
    """Tests for artifact upload with role/processor/artifactType fields."""

    @patch("src.services.storage.client.get_storage_client")
    @patch("api.v2.builds.builds.log_audit")
    def test_upload_artifact_with_all_metadata(self, mock_audit, mock_storage, authed_client, mock_db):
        """Upload artifact with role, processor, and artifactType in form fields."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_storage.return_value = MagicMock()

        created_artifact = _artifact_obj(
            role="app",
            processor="nrf52840",
            artifactType="plaintextHex",
        )
        mock_db.buildjobartifact.create.return_value = created_artifact

        data = {
            "file": (io.BytesIO(b"\x00" * 100), "app_nrf52840.hex"),
            "role": "app",
            "processor": "nrf52840",
            "artifactType": "plaintextHex",
        }

        response = authed_client.post(
            "/v2/builds/build-001/artifacts",
            data=data,
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert body["data"]["role"] == "app"
        assert body["data"]["processor"] == "nrf52840"
        assert body["data"]["artifactType"] == "plaintextHex"

        # Verify the create call included metadata
        create_call = mock_db.buildjobartifact.create.call_args
        create_data = create_call.kwargs["data"]
        assert create_data["role"] == "app"
        assert create_data["processor"] == "nrf52840"
        assert create_data["artifactType"] == "plaintextHex"

    @patch("src.services.storage.client.get_storage_client")
    @patch("api.v2.builds.builds.log_audit")
    def test_upload_artifact_with_partial_metadata(self, mock_audit, mock_storage, authed_client, mock_db):
        """Upload artifact with only role specified — other metadata fields are null."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_storage.return_value = MagicMock()

        created_artifact = _artifact_obj(role="comms")
        mock_db.buildjobartifact.create.return_value = created_artifact

        data = {
            "file": (io.BytesIO(b"\x00" * 50), "comms_nrf9151.hex"),
            "role": "comms",
        }

        response = authed_client.post(
            "/v2/builds/build-001/artifacts",
            data=data,
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        create_data = mock_db.buildjobartifact.create.call_args.kwargs["data"]
        assert create_data["role"] == "comms"
        assert create_data.get("processor") is None
        assert create_data.get("artifactType") is None

    @patch("src.services.storage.client.get_storage_client")
    @patch("api.v2.builds.builds.log_audit")
    def test_upload_artifact_without_metadata(self, mock_audit, mock_storage, authed_client, mock_db):
        """Upload artifact without metadata fields — backwards compatible."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_storage.return_value = MagicMock()

        created_artifact = _artifact_obj()
        mock_db.buildjobartifact.create.return_value = created_artifact

        data = {
            "file": (io.BytesIO(b"\x00" * 50), "build.json"),
        }

        response = authed_client.post(
            "/v2/builds/build-001/artifacts",
            data=data,
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        create_data = mock_db.buildjobartifact.create.call_args.kwargs["data"]
        assert create_data.get("role") is None
        assert create_data.get("processor") is None
        assert create_data.get("artifactType") is None


# ---------------------------------------------------------------------------
#  GET /v2/builds/<id>/artifacts — Serializer includes metadata
# ---------------------------------------------------------------------------

class TestArtifactSerializerMetadata:
    """Tests that artifact serializer includes role/processor/artifactType."""

    def test_list_artifacts_includes_metadata_fields(self, authed_client, mock_db):
        """List artifacts response includes role, processor, artifactType."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(
                id="a1",
                name="app_nrf52840.hex",
                role="app",
                processor="nrf52840",
                artifactType="plaintextHex",
            ),
            _artifact_obj(
                id="a2",
                name="108.0.8.3-BM.cfw",
                role="comms",
                processor="nrf9151",
                artifactType="encryptedCfw",
            ),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]) == 2

        a1 = body["data"][0]
        assert a1["role"] == "app"
        assert a1["processor"] == "nrf52840"
        assert a1["artifactType"] == "plaintextHex"

        a2 = body["data"][1]
        assert a2["role"] == "comms"
        assert a2["processor"] == "nrf9151"
        assert a2["artifactType"] == "encryptedCfw"

    def test_list_artifacts_null_metadata(self, authed_client, mock_db):
        """Artifacts without metadata have null for role/processor/artifactType."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a3", role=None, processor=None, artifactType=None),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts")
        assert response.status_code == 200

        body = json.loads(response.data)
        a = body["data"][0]
        assert a["role"] is None
        assert a["processor"] is None
        assert a["artifactType"] is None

    def test_build_detail_includes_artifact_metadata(self, authed_client, mock_db):
        """GET /v2/builds/<id> includes metadata in nested artifacts."""
        build = _build_obj(
            artifacts=[
                _artifact_obj(role="app", processor="nrf52840", artifactType="plaintextHex"),
            ],
        )
        mock_db.buildjob.find_unique.return_value = build

        response = authed_client.get("/v2/builds/build-001")
        assert response.status_code == 200

        body = json.loads(response.data)
        artifact = body["data"]["artifacts"][0]
        assert artifact["role"] == "app"
        assert artifact["processor"] == "nrf52840"
        assert artifact["artifactType"] == "plaintextHex"


# ---------------------------------------------------------------------------
#  GET /v2/builds/<id>/artifacts?role=app&type=plaintextHex — Filtering
# ---------------------------------------------------------------------------

class TestArtifactFiltering:
    """Tests for artifact list filtering by role and artifactType."""

    def test_filter_by_role(self, authed_client, mock_db):
        """Filter artifacts by role query parameter."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a1", role="app"),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts?role=app")
        assert response.status_code == 200

        # Verify the where clause included role filter
        call_args = mock_db.buildjobartifact.find_many.call_args
        assert call_args.kwargs["where"]["role"] == "app"

    def test_filter_by_artifact_type(self, authed_client, mock_db):
        """Filter artifacts by type query parameter."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a2", artifactType="encryptedCfw"),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts?type=encryptedCfw")
        assert response.status_code == 200

        call_args = mock_db.buildjobartifact.find_many.call_args
        assert call_args.kwargs["where"]["artifactType"] == "encryptedCfw"

    def test_filter_by_role_and_type(self, authed_client, mock_db):
        """Filter artifacts by both role and type."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a3", role="app", artifactType="plaintextHex"),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts?role=app&type=plaintextHex")
        assert response.status_code == 200

        call_args = mock_db.buildjobartifact.find_many.call_args
        where = call_args.kwargs["where"]
        assert where["role"] == "app"
        assert where["artifactType"] == "plaintextHex"

    def test_filter_by_processor(self, authed_client, mock_db):
        """Filter artifacts by processor query parameter."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a4", processor="nrf52840"),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts?processor=nrf52840")
        assert response.status_code == 200

        call_args = mock_db.buildjobartifact.find_many.call_args
        assert call_args.kwargs["where"]["processor"] == "nrf52840"

    def test_no_filters_returns_all(self, authed_client, mock_db):
        """No filter parameters returns all artifacts for the build."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a1"),
            _artifact_obj(id="a2"),
        ]

        response = authed_client.get("/v2/builds/build-001/artifacts")
        assert response.status_code == 200

        call_args = mock_db.buildjobartifact.find_many.call_args
        where = call_args.kwargs["where"]
        # Only buildJobId should be in where, no metadata filters
        assert where == {"buildJobId": "build-001"}
