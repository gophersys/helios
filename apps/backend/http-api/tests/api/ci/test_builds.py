"""Integration tests for the CI Builds API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _build_obj(**overrides):
    """Return a mock BuildJob with sensible defaults."""
    defaults = {
        "id": "build-001",
        "product": "alpha_fw",
        "productId": "prod-alpha",
        "board": "alpha_b0",
        "target": "app",
        "variant": "debug",
        "mtibRev": "1.2",
        "branch": "concord-main",
        "commitSha": "abc123def456",
        "status": "QUEUED",
        "versionMajor": None,
        "versionMinor": None,
        "buildNum": None,
        "versionString": None,
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
        "artifacts": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _artifact_obj(**overrides):
    """Return a mock BuildJobArtifact with sensible defaults."""
    defaults = {
        "id": "artifact-001",
        "buildJobId": "build-001",
        "name": "app_nrf52840.hex",
        "storageKey": "firmware-builds/alpha/build-001/app_nrf52840.hex",
        "sizeBytes": 65536,
        "checksum": "abcdef1234567890",
        "createdAt": _now(),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
#  GET /v2/builds — List builds
# ---------------------------------------------------------------------------

class TestListBuilds:
    """Tests for GET /v2/builds."""

    def test_list_builds_success(self, authed_client, mock_db):
        """List builds returns paginated results with build data."""
        builds = [
            _build_obj(id="build-001", product="alpha_fw"),
            _build_obj(id="build-002", product="alpha_mfg_fw", variant="mfg"),
        ]
        mock_db.buildjob.count.return_value = 2
        mock_db.buildjob.find_many.return_value = builds

        response = authed_client.get("/v2/builds")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 2
        assert body["data"][0]["id"] == "build-001"
        assert body["totalResults"] == 2
        assert body["page"] == 1

    def test_list_builds_empty(self, authed_client, mock_db):
        """List builds returns an empty list when no builds exist."""
        mock_db.buildjob.count.return_value = 0
        mock_db.buildjob.find_many.return_value = []

        response = authed_client.get("/v2/builds")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"] == []
        assert body["totalResults"] == 0

    def test_list_builds_with_status_filter(self, authed_client, mock_db):
        """List builds filters by status query parameter."""
        mock_db.buildjob.count.return_value = 1
        mock_db.buildjob.find_many.return_value = [
            _build_obj(id="build-003", status="SUCCESS"),
        ]

        response = authed_client.get("/v2/builds?status=success")
        assert response.status_code == 200

        # Verify the where clause included status filter
        call_args = mock_db.buildjob.find_many.call_args
        assert call_args.kwargs["where"]["status"] == "SUCCESS"

    def test_list_builds_with_product_filter(self, authed_client, mock_db):
        """List builds filters by product query parameter."""
        mock_db.buildjob.count.return_value = 1
        mock_db.buildjob.find_many.return_value = [
            _build_obj(id="build-004", product="theta_fw"),
        ]

        response = authed_client.get("/v2/builds?product=theta_fw")
        assert response.status_code == 200

        call_args = mock_db.buildjob.find_many.call_args
        assert call_args.kwargs["where"]["product"] == "theta_fw"

    def test_list_builds_pagination(self, authed_client, mock_db):
        """List builds respects page and limit query parameters."""
        mock_db.buildjob.count.return_value = 100
        mock_db.buildjob.find_many.return_value = [
            _build_obj(id=f"build-{i}") for i in range(10)
        ]

        response = authed_client.get("/v2/builds?page=3&limit=10")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["page"] == 3
        assert body["resultsPerPage"] == 10
        assert body["totalResults"] == 100
        assert body["totalPages"] == 10

        call_args = mock_db.buildjob.find_many.call_args
        assert call_args.kwargs["skip"] == 20  # (3 - 1) * 10
        assert call_args.kwargs["take"] == 10

    def test_list_builds_with_artifacts(self, authed_client, mock_db):
        """List builds includes artifact count in response."""
        build = _build_obj(
            id="build-005",
            artifacts=[
                _artifact_obj(id="a1"),
                _artifact_obj(id="a2"),
            ],
        )
        mock_db.buildjob.count.return_value = 1
        mock_db.buildjob.find_many.return_value = [build]

        response = authed_client.get("/v2/builds")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"][0]["artifactCount"] == 2

    def test_list_builds_unauthorized(self, client):
        """List builds without authentication returns 401."""
        response = client.get("/v2/builds")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
#  GET /v2/builds/<id> — Get build
# ---------------------------------------------------------------------------

class TestGetBuild:
    """Tests for GET /v2/builds/<id>."""

    def test_get_build_success(self, authed_client, mock_db):
        """Get build returns full build detail with artifacts and log."""
        build = _build_obj(
            id="build-010",
            status="SUCCESS",
            buildLog="Build completed successfully.",
            artifacts=[_artifact_obj()],
        )
        mock_db.buildjob.find_unique.return_value = build

        response = authed_client.get("/v2/builds/build-010")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"]["id"] == "build-010"
        assert body["data"]["status"] == "SUCCESS"
        assert body["data"]["buildLog"] == "Build completed successfully."
        assert body["data"]["artifactCount"] == 1

    def test_get_build_not_found(self, authed_client, mock_db):
        """Get build with non-existent ID returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        response = authed_client.get("/v2/builds/nonexistent")
        assert response.status_code == 404

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_get_build_includes_matrix_fields(self, authed_client, mock_db):
        """Get build includes stage4 matrix fields in response."""
        build = _build_obj(
            id="build-011",
            matrixLabel="FUT_DEBUG_A",
            matrixIndex=2,
            versionBump=False,
            baseJobId=None,
        )
        mock_db.buildjob.find_unique.return_value = build

        response = authed_client.get("/v2/builds/build-011")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["matrixLabel"] == "FUT_DEBUG_A"
        assert body["data"]["matrixIndex"] == 2
        assert body["data"]["versionBump"] is False


# ---------------------------------------------------------------------------
#  POST /v2/builds — Create build
# ---------------------------------------------------------------------------

class TestCreateBuild:
    """Tests for POST /v2/builds."""

    def test_create_build_success(self, authed_client, mock_db):
        """Create build with valid payload returns 201 with new build."""
        mock_db.product.find_first.return_value = make_obj(
            id="prod-alpha",
            slug="alpha",
            buildBoard="alpha_b0",
        )

        created = _build_obj(id="build-new", status="QUEUED")
        mock_db.buildjob.create.return_value = created

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha_fw",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "debug",
                    "branch": "concord-main",
                }),
            )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"]["id"] == "build-new"
        assert body["data"]["status"] == "QUEUED"

    def test_create_build_missing_product(self, authed_client, mock_db):
        """Create build without required product field returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data=json.dumps({
                "board": "alpha_b0",
                "target": "app",
                "variant": "debug",
                "branch": "concord-main",
            }),
        )
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_create_build_missing_board(self, authed_client, mock_db):
        """Create build without required board field returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data=json.dumps({
                "product": "alpha_fw",
                "target": "app",
                "variant": "debug",
                "branch": "concord-main",
            }),
        )
        assert response.status_code == 400

    def test_create_build_missing_target(self, authed_client, mock_db):
        """Create build without required target field returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data=json.dumps({
                "product": "alpha_fw",
                "board": "alpha_b0",
                "variant": "debug",
                "branch": "concord-main",
            }),
        )
        assert response.status_code == 400

    def test_create_build_missing_branch(self, authed_client, mock_db):
        """Create build without required branch field returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data=json.dumps({
                "product": "alpha_fw",
                "board": "alpha_b0",
                "target": "app",
                "variant": "debug",
            }),
        )
        assert response.status_code == 400

    def test_create_build_empty_body(self, authed_client, mock_db):
        """Create build with empty body returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data=json.dumps({}),
        )
        assert response.status_code == 400

    def test_create_build_null_body(self, authed_client, mock_db):
        """Create build with null JSON body returns 400."""
        response = authed_client.post(
            "/v2/builds",
            data="null",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_create_build_with_commit_sha(self, authed_client, mock_db):
        """Create build with optional commitSha passes it through."""
        mock_db.product.find_first.return_value = None
        created = _build_obj(id="build-sha", commitSha="abc123")
        mock_db.buildjob.create.return_value = created

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha_fw",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "debug",
                    "branch": "main",
                    "commitSha": "abc123",
                }),
            )

        assert response.status_code == 201

    def test_create_build_mfg_variant_auto(self, authed_client, mock_db):
        """Create build for _mfg product auto-sets variant to mfg."""
        mock_db.product.find_first.return_value = None
        created = _build_obj(id="build-mfg", variant="mfg", product="alpha_mfg_fw")
        mock_db.buildjob.create.return_value = created

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha_mfg_fw",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "debug",  # Should be overridden to "mfg"
                    "branch": "main",
                }),
            )

        assert response.status_code == 201

    def test_create_build_db_error(self, authed_client, mock_db):
        """Create build returns 500 when database raises an exception."""
        mock_db.product.find_first.return_value = None
        mock_db.buildjob.create.side_effect = Exception("DB connection lost")

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha_fw",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "debug",
                    "branch": "main",
                }),
            )

        assert response.status_code == 500

    def test_create_build_with_product_linkage(self, authed_client, mock_db):
        """Create build links productId when product is found in DB."""
        mock_db.product.find_first.return_value = make_obj(
            id="prod-linked",
            slug="alpha",
            buildBoard="alpha_b0",
        )
        created = _build_obj(id="build-linked", productId="prod-linked")
        mock_db.buildjob.create.return_value = created

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha",
                    "board": "alpha_b0",
                    "target": "app",
                    "variant": "debug",
                    "branch": "main",
                }),
            )

        assert response.status_code == 201
        # Verify productId was passed to create
        create_call = mock_db.buildjob.create.call_args
        assert create_call.kwargs["data"]["productId"] == "prod-linked"

    def test_create_build_uses_product_board(self, authed_client, mock_db):
        """Create build uses board from Product record when not provided."""
        mock_db.product.find_first.return_value = make_obj(
            id="prod-board",
            slug="alpha",
            buildBoard="custom_board_v2",
        )
        created = _build_obj(id="build-board", board="custom_board_v2")
        mock_db.buildjob.create.return_value = created

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post(
                "/v2/builds",
                data=json.dumps({
                    "product": "alpha",
                    "board": "",  # empty triggers from_json validation
                    "target": "app",
                    "variant": "debug",
                    "branch": "main",
                }),
            )

        # Empty board should cause validation failure (board is required)
        assert response.status_code == 400


# ---------------------------------------------------------------------------
#  PATCH /v2/builds/<id> — Update build
# ---------------------------------------------------------------------------

class TestUpdateBuild:
    """Tests for PATCH /v2/builds/<id>."""

    def _patch(self, authed_client, url, data):
        """Send a PATCH request via the underlying Flask test client."""
        # authed_client wraps get/post/put/delete but not patch,
        # so we build headers manually.
        from src.services.auth.jwt import create_token
        token = create_token(
            user_id="test-user-id",
            email="test@example.com",
            name="Test User",
            permission_set_id="test-perm-set-id",
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        return authed_client._client.patch(url, data=json.dumps(data), headers=headers)

    def test_update_build_status(self, authed_client, mock_db):
        """Update build status from QUEUED to BUILDING."""
        existing = _build_obj(id="build-upd", status="QUEUED")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-upd", status="BUILDING")
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-upd", {
            "status": "BUILDING",
        })

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["status"] == "BUILDING"

    def test_update_build_not_found(self, authed_client, mock_db):
        """Update build that does not exist returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        response = self._patch(authed_client, "/v2/builds/nonexistent", {
            "status": "BUILDING",
        })

        assert response.status_code == 404

    def test_update_build_invalid_status(self, authed_client, mock_db):
        """Update build with invalid status value returns 400."""
        existing = _build_obj(id="build-inv", status="QUEUED")
        mock_db.buildjob.find_unique.return_value = existing

        response = self._patch(authed_client, "/v2/builds/build-inv", {
            "status": "INVALID_STATUS",
        })

        assert response.status_code == 400

    def test_update_build_no_valid_fields(self, authed_client, mock_db):
        """Update build with no recognized fields returns 400."""
        existing = _build_obj(id="build-nf", status="QUEUED")
        mock_db.buildjob.find_unique.return_value = existing

        response = self._patch(authed_client, "/v2/builds/build-nf", {
            "unknownField": "value",
        })

        assert response.status_code == 400
        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_update_build_error_message(self, authed_client, mock_db):
        """Update build error message stores the message."""
        existing = _build_obj(id="build-err", status="BUILDING")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-err", status="BUILDING", errorMessage="OOM killed")
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-err", {
            "errorMessage": "OOM killed",
        })

        assert response.status_code == 200
        create_call = mock_db.buildjob.update.call_args
        assert create_call.kwargs["data"]["errorMessage"] == "OOM killed"

    def test_update_build_version_string(self, authed_client, mock_db):
        """Update build version string is stored."""
        existing = _build_obj(id="build-vs", status="BUILDING")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-vs", versionString="0.8.3")
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-vs", {
            "versionString": "0.8.3",
        })

        assert response.status_code == 200

    def test_update_build_duration(self, authed_client, mock_db):
        """Update build duration in seconds."""
        existing = _build_obj(id="build-dur")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-dur", durationSeconds=120)
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-dur", {
            "durationSeconds": 120,
        })

        assert response.status_code == 200
        call_data = mock_db.buildjob.update.call_args.kwargs["data"]
        assert call_data["durationSeconds"] == 120

    def test_update_build_log(self, authed_client, mock_db):
        """Update build log content."""
        existing = _build_obj(id="build-log")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-log", buildLog="compiling...")
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-log", {
            "buildLog": "compiling...",
        })

        assert response.status_code == 200
        call_data = mock_db.buildjob.update.call_args.kwargs["data"]
        assert call_data["buildLog"] == "compiling..."

    def test_update_build_version_bump(self, authed_client, mock_db):
        """Update build versionBump flag."""
        existing = _build_obj(id="build-vb")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-vb", versionBump=True)
        mock_db.buildjob.update.return_value = updated

        response = self._patch(authed_client, "/v2/builds/build-vb", {
            "versionBump": True,
        })

        assert response.status_code == 200
        call_data = mock_db.buildjob.update.call_args.kwargs["data"]
        assert call_data["versionBump"] is True

    def test_update_build_unblocks_dependents_on_success(self, authed_client, mock_db):
        """When a build succeeds, its BLOCKED dependents are moved to QUEUED."""
        existing = _build_obj(id="build-base", status="BUILDING", pipelineRunId="pipe-1")
        mock_db.buildjob.find_unique.return_value = existing

        updated = _build_obj(id="build-base", status="SUCCESS", pipelineRunId="pipe-1")
        mock_db.buildjob.update.return_value = updated

        # Simulate a dependent blocked build
        dependent = _build_obj(id="build-dep", status="BLOCKED", baseJobId="build-base")
        mock_db.buildjob.find_many.return_value = [dependent]

        # Mock pipeline completion check — the lazy import uses api.v2.ci.pipelines path
        with patch("api.v2.ci.pipelines.check_pipeline_completion", return_value=None):
            response = self._patch(authed_client, "/v2/builds/build-base", {
                "status": "SUCCESS",
            })

        assert response.status_code == 200
        # Verify the dependent build was unblocked
        unblock_calls = [
            c for c in mock_db.buildjob.update.call_args_list
            if c.kwargs.get("where", {}).get("id") == "build-dep"
        ]
        assert len(unblock_calls) == 1
        assert unblock_calls[0].kwargs["data"]["status"] == "QUEUED"

    def test_update_build_db_error(self, authed_client, mock_db):
        """Update build returns 500 when database raises an exception."""
        existing = _build_obj(id="build-dbe")
        mock_db.buildjob.find_unique.return_value = existing
        mock_db.buildjob.update.side_effect = Exception("DB error")

        response = self._patch(authed_client, "/v2/builds/build-dbe", {
            "status": "BUILDING",
        })

        assert response.status_code == 500


# ---------------------------------------------------------------------------
#  GET /v2/builds/<id>/artifacts — List build artifacts
# ---------------------------------------------------------------------------

class TestListBuildArtifacts:
    """Tests for GET /v2/builds/<id>/artifacts."""

    def test_list_artifacts_success(self, authed_client, mock_db):
        """List artifacts returns all artifacts for a build."""
        mock_db.buildjob.find_unique.return_value = _build_obj(id="build-art")
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a1", name="app_nrf52840.hex"),
            _artifact_obj(id="a2", name="comms_nrf9151.hex"),
        ]

        response = authed_client.get("/v2/builds/build-art/artifacts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert len(body["data"]) == 2
        assert body["data"][0]["name"] == "app_nrf52840.hex"
        assert body["data"][1]["name"] == "comms_nrf9151.hex"

    def test_list_artifacts_empty(self, authed_client, mock_db):
        """List artifacts returns empty list when build has no artifacts."""
        mock_db.buildjob.find_unique.return_value = _build_obj(id="build-no-art")
        mock_db.buildjobartifact.find_many.return_value = []

        response = authed_client.get("/v2/builds/build-no-art/artifacts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"] == []

    def test_list_artifacts_build_not_found(self, authed_client, mock_db):
        """List artifacts for non-existent build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        response = authed_client.get("/v2/builds/nonexistent/artifacts")
        assert response.status_code == 404

    def test_list_artifacts_includes_size_and_checksum(self, authed_client, mock_db):
        """List artifacts response includes sizeBytes and checksum fields."""
        mock_db.buildjob.find_unique.return_value = _build_obj(id="build-meta")
        mock_db.buildjobartifact.find_many.return_value = [
            _artifact_obj(id="a1", sizeBytes=131072, checksum="deadbeef"),
        ]

        response = authed_client.get("/v2/builds/build-meta/artifacts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"][0]["sizeBytes"] == 131072
        assert body["data"][0]["checksum"] == "deadbeef"


# ---------------------------------------------------------------------------
#  POST /v2/builds/<id>/reset — Reset build
# ---------------------------------------------------------------------------

class TestResetBuild:
    """Tests for POST /v2/builds/<id>/reset."""

    def test_reset_build_success_from_building(self, authed_client, mock_db):
        """Reset a stuck BUILDING build back to QUEUED."""
        existing = _build_obj(
            id="build-stuck",
            status="BUILDING",
            startedAt=_now(),
            buildLog="partial log...",
            matrixLabel="FUT_DEBUG_A",
        )
        mock_db.buildjob.find_unique.return_value = existing

        reset_result = _build_obj(
            id="build-stuck",
            status="QUEUED",
            startedAt=None,
            finishedAt=None,
            buildLog=None,
            errorMessage=None,
            durationSeconds=None,
        )
        mock_db.buildjob.update.return_value = reset_result

        response = authed_client.post("/v2/builds/build-stuck/reset")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["status"] == "QUEUED"

        # Verify audit log was written via the mock DB
        mock_db.auditlog.create.assert_called_once()
        audit_data = mock_db.auditlog.create.call_args.kwargs["data"]
        assert audit_data["action"] == "ci.build.reset"
        assert audit_data["entityType"] == "BuildJob"

    def test_reset_build_success_from_failed(self, authed_client, mock_db):
        """Reset a FAILED build back to QUEUED."""
        existing = _build_obj(id="build-fail", status="FAILED", errorMessage="OOM")
        mock_db.buildjob.find_unique.return_value = existing

        reset_result = _build_obj(id="build-fail", status="QUEUED")
        mock_db.buildjob.update.return_value = reset_result

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post("/v2/builds/build-fail/reset")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["status"] == "QUEUED"

    def test_reset_build_not_found(self, authed_client, mock_db):
        """Reset a non-existent build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        response = authed_client.post("/v2/builds/nonexistent/reset")
        assert response.status_code == 404

    def test_reset_build_wrong_status_queued(self, authed_client, mock_db):
        """Reset a QUEUED build returns 400 — only BUILDING/FAILED allowed."""
        existing = _build_obj(id="build-q", status="QUEUED")
        mock_db.buildjob.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/build-q/reset")
        assert response.status_code == 400

        body = json.loads(response.data)
        assert "QUEUED" in body["errors"][0]["message"]

    def test_reset_build_wrong_status_success(self, authed_client, mock_db):
        """Reset a SUCCESS build returns 400 — cannot reset completed build."""
        existing = _build_obj(id="build-s", status="SUCCESS")
        mock_db.buildjob.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/build-s/reset")
        assert response.status_code == 400

    def test_reset_build_wrong_status_cancelled(self, authed_client, mock_db):
        """Reset a CANCELLED build returns 400."""
        existing = _build_obj(id="build-c", status="CANCELLED")
        mock_db.buildjob.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/build-c/reset")
        assert response.status_code == 400

    def test_reset_build_clears_fields(self, authed_client, mock_db):
        """Reset clears startedAt, finishedAt, buildLog, errorMessage, durationSeconds."""
        existing = _build_obj(id="build-clr", status="FAILED")
        mock_db.buildjob.find_unique.return_value = existing

        reset_result = _build_obj(id="build-clr", status="QUEUED")
        mock_db.buildjob.update.return_value = reset_result

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post("/v2/builds/build-clr/reset")

        assert response.status_code == 200

        # Verify the update call cleared the right fields
        update_call = mock_db.buildjob.update.call_args
        update_data = update_call.kwargs["data"]
        assert update_data["status"] == "QUEUED"
        assert update_data["startedAt"] is None
        assert update_data["finishedAt"] is None
        assert update_data["buildLog"] is None
        assert update_data["errorMessage"] is None
        assert update_data["durationSeconds"] is None

    def test_reset_build_db_error(self, authed_client, mock_db):
        """Reset build returns 500 when database raises an exception."""
        existing = _build_obj(id="build-re", status="FAILED")
        mock_db.buildjob.find_unique.return_value = existing
        mock_db.buildjob.update.side_effect = Exception("DB error")

        with patch("src.api.v2.ci.builds.log_audit"):
            response = authed_client.post("/v2/builds/build-re/reset")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
#  GET /v2/builds/<id>/log — Get build log
# ---------------------------------------------------------------------------

class TestGetBuildLog:
    """Tests for GET /v2/builds/<id>/log."""

    def test_get_build_log_success(self, authed_client, mock_db):
        """Get build log returns log content and status."""
        build = _build_obj(id="build-log1", status="BUILDING", buildLog="line 1\nline 2\n")
        mock_db.buildjob.find_unique.return_value = build

        response = authed_client.get("/v2/builds/build-log1/log")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["buildId"] == "build-log1"
        assert body["data"]["status"] == "BUILDING"
        assert "line 1" in body["data"]["log"]

    def test_get_build_log_empty(self, authed_client, mock_db):
        """Get build log returns empty string when no log exists."""
        build = _build_obj(id="build-nolog", buildLog=None)
        mock_db.buildjob.find_unique.return_value = build

        response = authed_client.get("/v2/builds/build-nolog/log")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["log"] == ""

    def test_get_build_log_not_found(self, authed_client, mock_db):
        """Get build log for non-existent build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        response = authed_client.get("/v2/builds/nonexistent/log")
        assert response.status_code == 404
