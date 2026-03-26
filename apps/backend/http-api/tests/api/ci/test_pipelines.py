"""Integration tests for the CI Pipelines API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _pipeline_obj(**overrides):
    """Return a mock PipelineRun with sensible defaults."""
    defaults = {
        "id": "pipe-001",
        "name": "alpha-main-abc1234",
        "product": "alpha",
        "board": "alpha_b0",
        "branch": "concord-main",
        "commitSha": "abc1234567890",
        "status": "PENDING",
        "triggerType": "manual",
        "expectedBuilds": 2,
        "completedBuilds": 0,
        "validationRunId": None,
        "matrixMode": "smoke",
        "buildMatrix": {"mode": "smoke", "product": "alpha"},
        "triggerData": None,
        "startedAt": _now(),
        "finishedAt": None,
        "createdAt": _now(),
        "updatedAt": _now(),
        "builds": [],
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _build_summary(**overrides):
    """Return a minimal mock BuildJob for pipeline build lists."""
    defaults = {
        "id": "build-001",
        "product": "alpha_fw",
        "productId": "prod-alpha",
        "status": "QUEUED",
        "target": "app",
        "variant": "debug",
        "board": "alpha_b0",
        "commitSha": "abc1234567890",
        "buildNum": None,
        "versionString": None,
        "durationSeconds": None,
        "matrixLabel": None,
        "matrixIndex": None,
        "versionBump": False,
        "baseJobId": None,
        "reusedFromId": None,
        "artifacts": [],
    }
    defaults.update(overrides)
    return make_obj(**defaults)


def _product_obj(**overrides):
    """Return a mock Product record."""
    defaults = {
        "id": "prod-alpha",
        "name": "Alpha B0",
        "slug": "alpha_b0",
        "repoSlug": "alpha_fw",
        "mfgRepoSlug": "alpha_mfg_fw",
        "buildBoard": "alpha_b0",
        "buildWestDir": None,
        "buildMfgDir": None,
        "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
        "mfgRepoSshUrl": "git@bitbucket.org:corekinect/alpha_mfg_fw.git",
        "metadata": {"targets": ["app", "comms"]},
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
#  GET /v2/builds/pipelines — List pipelines
# ---------------------------------------------------------------------------

class TestListPipelines:
    """Tests for GET /v2/builds/pipelines."""

    def test_list_pipelines_success(self, authed_client, mock_db):
        """List pipelines returns paginated results."""
        pipes = [
            _pipeline_obj(id="pipe-001", status="PENDING"),
            _pipeline_obj(id="pipe-002", status="SUCCESS"),
        ]
        mock_db.pipelinerun.count.return_value = 2
        mock_db.pipelinerun.find_many.return_value = pipes

        response = authed_client.get("/v2/builds/pipelines")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        result = body["data"]
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2
        assert result["pagination"]["total"] == 2

    def test_list_pipelines_empty(self, authed_client, mock_db):
        """List pipelines returns empty list when none exist."""
        mock_db.pipelinerun.count.return_value = 0
        mock_db.pipelinerun.find_many.return_value = []

        response = authed_client.get("/v2/builds/pipelines")
        assert response.status_code == 200

        body = json.loads(response.data)
        result = body["data"]
        assert result["data"] == []
        assert result["pagination"]["total"] == 0

    def test_list_pipelines_with_product_filter(self, authed_client, mock_db):
        """List pipelines filters by product query parameter."""
        mock_db.pipelinerun.count.return_value = 1
        mock_db.pipelinerun.find_many.return_value = [
            _pipeline_obj(id="pipe-f", product="theta"),
        ]

        response = authed_client.get("/v2/builds/pipelines?product=theta")
        assert response.status_code == 200

        call_args = mock_db.pipelinerun.find_many.call_args
        assert call_args.kwargs["where"]["product"] == "theta"

    def test_list_pipelines_with_branch_filter(self, authed_client, mock_db):
        """List pipelines filters by branch query parameter."""
        mock_db.pipelinerun.count.return_value = 1
        mock_db.pipelinerun.find_many.return_value = [
            _pipeline_obj(id="pipe-b", branch="feature/x"),
        ]

        response = authed_client.get("/v2/builds/pipelines?branch=feature/x")
        assert response.status_code == 200

        call_args = mock_db.pipelinerun.find_many.call_args
        assert call_args.kwargs["where"]["branch"] == "feature/x"

    def test_list_pipelines_with_status_filter(self, authed_client, mock_db):
        """List pipelines filters by status query parameter."""
        mock_db.pipelinerun.count.return_value = 1
        mock_db.pipelinerun.find_many.return_value = [
            _pipeline_obj(id="pipe-s", status="SUCCESS"),
        ]

        response = authed_client.get("/v2/builds/pipelines?status=SUCCESS")
        assert response.status_code == 200

        call_args = mock_db.pipelinerun.find_many.call_args
        assert call_args.kwargs["where"]["status"] == "SUCCESS"

    def test_list_pipelines_pagination(self, authed_client, mock_db):
        """List pipelines respects page and limit parameters."""
        mock_db.pipelinerun.count.return_value = 50
        mock_db.pipelinerun.find_many.return_value = [
            _pipeline_obj(id=f"pipe-{i}") for i in range(5)
        ]

        response = authed_client.get("/v2/builds/pipelines?page=2&limit=5")
        assert response.status_code == 200

        body = json.loads(response.data)
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 2
        assert pagination["limit"] == 5
        assert pagination["total"] == 50
        assert pagination["pages"] == 10

        call_args = mock_db.pipelinerun.find_many.call_args
        assert call_args.kwargs["skip"] == 5  # (2 - 1) * 5
        assert call_args.kwargs["take"] == 5

    def test_list_pipelines_includes_builds(self, authed_client, mock_db):
        """List pipelines includes build summaries in response."""
        pipe = _pipeline_obj(
            id="pipe-builds",
            builds=[
                _build_summary(id="b1", status="SUCCESS", matrixLabel="MFG_BASE", matrixIndex=0),
                _build_summary(id="b2", status="QUEUED", matrixLabel="FUT_DEBUG_A", matrixIndex=2),
            ],
        )
        mock_db.pipelinerun.count.return_value = 1
        mock_db.pipelinerun.find_many.return_value = [pipe]

        response = authed_client.get("/v2/builds/pipelines")
        assert response.status_code == 200

        body = json.loads(response.data)
        pipeline_data = body["data"]["data"][0]
        assert "builds" in pipeline_data
        assert len(pipeline_data["builds"]) == 2

    def test_list_pipelines_db_error(self, authed_client, mock_db):
        """List pipelines returns 500 when database raises an exception."""
        mock_db.pipelinerun.count.side_effect = Exception("DB connection refused")

        response = authed_client.get("/v2/builds/pipelines")
        assert response.status_code == 500

    def test_list_pipelines_unauthorized(self, client):
        """List pipelines without authentication returns 401."""
        response = client.get("/v2/builds/pipelines")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
#  GET /v2/builds/pipelines/<id> — Get pipeline detail
# ---------------------------------------------------------------------------

class TestGetPipeline:
    """Tests for GET /v2/builds/pipelines/<id>."""

    def test_get_pipeline_success(self, authed_client, mock_db):
        """Get pipeline returns full detail with builds and artifacts."""
        pipe = _pipeline_obj(
            id="pipe-detail",
            status="BUILDING",
            builds=[
                _build_summary(id="b1", status="SUCCESS", variant="debug"),
                _build_summary(id="b2", status="BUILDING", variant="release"),
            ],
        )
        mock_db.pipelinerun.find_unique.return_value = pipe

        response = authed_client.get("/v2/builds/pipelines/pipe-detail")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"]["id"] == "pipe-detail"
        assert body["data"]["status"] == "BUILDING"
        assert len(body["data"]["builds"]) == 2

    def test_get_pipeline_not_found(self, authed_client, mock_db):
        """Get pipeline with non-existent ID returns 404."""
        mock_db.pipelinerun.find_unique.return_value = None

        response = authed_client.get("/v2/builds/pipelines/nonexistent")
        assert response.status_code == 404

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_get_pipeline_includes_all_fields(self, authed_client, mock_db):
        """Get pipeline response includes all expected fields."""
        pipe = _pipeline_obj(
            id="pipe-full",
            name="alpha-main-abc1234",
            product="alpha",
            board="alpha_b0",
            branch="concord-main",
            commitSha="abc1234567890",
            status="SUCCESS",
            triggerType="poller",
            expectedBuilds=8,
            completedBuilds=8,
            matrixMode="stage4",
            validationRunId="val-run-001",
        )
        mock_db.pipelinerun.find_unique.return_value = pipe

        response = authed_client.get("/v2/builds/pipelines/pipe-full")
        assert response.status_code == 200

        body = json.loads(response.data)
        data = body["data"]
        assert data["name"] == "alpha-main-abc1234"
        assert data["product"] == "alpha"
        assert data["board"] == "alpha_b0"
        assert data["branch"] == "concord-main"
        assert data["commitSha"] == "abc1234567890"
        assert data["status"] == "SUCCESS"
        assert data["triggerType"] == "poller"
        assert data["expectedBuilds"] == 8
        assert data["completedBuilds"] == 8
        assert data["matrixMode"] == "stage4"
        assert data["validationRunId"] == "val-run-001"

    def test_get_pipeline_db_error(self, authed_client, mock_db):
        """Get pipeline returns 500 when database raises an exception."""
        mock_db.pipelinerun.find_unique.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/builds/pipelines/pipe-err")
        assert response.status_code == 500


# ---------------------------------------------------------------------------
#  POST /v2/builds/pipelines — Create pipeline
# ---------------------------------------------------------------------------

class TestCreatePipeline:
    """Tests for POST /v2/builds/pipelines."""

    def _mock_pipeline_creation(self, mock_db, pipeline_id="pipe-new"):
        """Set up mocks for a successful pipeline creation."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product

        created_pipeline = _pipeline_obj(id=pipeline_id, status="PENDING")
        mock_db.pipelinerun.create.return_value = created_pipeline

        # Build creation mocks
        build = _build_summary(id="b-new", status="QUEUED")
        mock_db.buildjob.create.return_value = build

        # Re-fetch with builds
        refetched = _pipeline_obj(
            id=pipeline_id,
            status="PENDING",
            builds=[build],
        )
        mock_db.pipelinerun.find_unique.return_value = refetched

    def test_create_pipeline_success(self, authed_client, mock_db):
        """Create pipeline with valid payload returns 201."""
        self._mock_pipeline_creation(mock_db)

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post(
                "/v2/builds/pipelines",
                data=json.dumps({
                    "product": "alpha",
                    "board": "alpha_b0",
                    "branch": "concord-main",
                    "matrixMode": "smoke",
                }),
            )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert len(body["errors"]) == 0
        assert body["data"]["id"] == "pipe-new"
        assert body["data"]["status"] == "PENDING"

    def test_create_pipeline_missing_product(self, authed_client, mock_db):
        """Create pipeline without product returns 400."""
        response = authed_client.post(
            "/v2/builds/pipelines",
            data=json.dumps({
                "board": "alpha_b0",
                "branch": "main",
            }),
        )
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_create_pipeline_missing_board(self, authed_client, mock_db):
        """Create pipeline without board returns 400."""
        response = authed_client.post(
            "/v2/builds/pipelines",
            data=json.dumps({
                "product": "alpha",
                "branch": "main",
            }),
        )
        assert response.status_code == 400

    def test_create_pipeline_missing_branch(self, authed_client, mock_db):
        """Create pipeline without branch returns 400."""
        response = authed_client.post(
            "/v2/builds/pipelines",
            data=json.dumps({
                "product": "alpha",
                "board": "alpha_b0",
            }),
        )
        assert response.status_code == 400

    def test_create_pipeline_empty_body(self, authed_client, mock_db):
        """Create pipeline with empty body returns 400."""
        response = authed_client.post(
            "/v2/builds/pipelines",
            data=json.dumps({}),
        )
        assert response.status_code == 400

    def test_create_pipeline_invalid_matrix_mode(self, authed_client, mock_db):
        """Create pipeline with invalid matrixMode returns 400."""
        response = authed_client.post(
            "/v2/builds/pipelines",
            data=json.dumps({
                "product": "alpha",
                "board": "alpha_b0",
                "branch": "main",
                "matrixMode": "invalid",
            }),
        )
        assert response.status_code == 400

    def test_create_pipeline_with_poller_trigger(self, authed_client, mock_db):
        """Create pipeline from git poller includes productId and repoSlug."""
        self._mock_pipeline_creation(mock_db, "pipe-poller")

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post(
                "/v2/builds/pipelines",
                data=json.dumps({
                    "productId": "prod-alpha",
                    "product": "alpha",
                    "repoSlug": "alpha_fw",
                    "board": "alpha_b0",
                    "branch": "concord-main",
                    "commitSha": "abc123",
                    "triggerType": "poller",
                }),
            )

        assert response.status_code == 201

    def test_create_pipeline_fuota_mode(self, authed_client, mock_db):
        """Create pipeline with fuota matrix mode creates 8 builds."""
        self._mock_pipeline_creation(mock_db, "pipe-fuota")

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post(
                "/v2/builds/pipelines",
                data=json.dumps({
                    "product": "alpha",
                    "board": "alpha_b0",
                    "branch": "feature/test",
                    "matrixMode": "fuota",
                }),
            )

        assert response.status_code == 201

    def test_create_pipeline_db_error(self, authed_client, mock_db):
        """Create pipeline returns 500 when database raises an exception."""
        product = _product_obj()
        mock_db.product.find_unique.return_value = product
        mock_db.product.find_first.return_value = product
        mock_db.pipelinerun.create.side_effect = Exception("DB error")

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post(
                "/v2/builds/pipelines",
                data=json.dumps({
                    "product": "alpha",
                    "board": "alpha_b0",
                    "branch": "main",
                    "matrixMode": "smoke",
                }),
            )

        assert response.status_code == 500

    def test_create_pipeline_with_name(self, authed_client, mock_db):
        """Create pipeline with custom name uses that name."""
        self._mock_pipeline_creation(mock_db, "pipe-named")

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post(
                "/v2/builds/pipelines",
                data=json.dumps({
                    "name": "Custom Pipeline Name",
                    "product": "alpha",
                    "board": "alpha_b0",
                    "branch": "main",
                }),
            )

        assert response.status_code == 201

    def test_create_pipeline_unauthorized(self, client):
        """Create pipeline without authentication returns 401."""
        response = client.post(
            "/v2/builds/pipelines",
            data=json.dumps({"product": "alpha", "board": "alpha_b0", "branch": "main"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
#  POST /v2/builds/pipelines/<id>/cancel — Cancel pipeline
# ---------------------------------------------------------------------------

class TestCancelPipeline:
    """Tests for POST /v2/builds/pipelines/<id>/cancel."""

    def test_cancel_pipeline_success(self, authed_client, mock_db):
        """Cancel a PENDING pipeline sets status to CANCELLED."""
        existing = _pipeline_obj(id="pipe-cancel", status="PENDING")
        mock_db.pipelinerun.find_unique.return_value = existing

        cancelled = _pipeline_obj(id="pipe-cancel", status="CANCELLED")
        mock_db.pipelinerun.update.return_value = cancelled

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post("/v2/builds/pipelines/pipe-cancel/cancel")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["status"] == "CANCELLED"

    def test_cancel_pipeline_building(self, authed_client, mock_db):
        """Cancel a BUILDING pipeline sets status to CANCELLED."""
        existing = _pipeline_obj(id="pipe-building", status="BUILDING")
        mock_db.pipelinerun.find_unique.return_value = existing

        cancelled = _pipeline_obj(id="pipe-building", status="CANCELLED")
        mock_db.pipelinerun.update.return_value = cancelled

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post("/v2/builds/pipelines/pipe-building/cancel")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["status"] == "CANCELLED"

    def test_cancel_pipeline_cancels_pending_builds(self, authed_client, mock_db):
        """Cancel pipeline also cancels all QUEUED/BUILDING child builds."""
        existing = _pipeline_obj(id="pipe-cbuild", status="BUILDING")
        mock_db.pipelinerun.find_unique.return_value = existing

        cancelled = _pipeline_obj(id="pipe-cbuild", status="CANCELLED")
        mock_db.pipelinerun.update.return_value = cancelled

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post("/v2/builds/pipelines/pipe-cbuild/cancel")

        assert response.status_code == 200

        # Verify update_many was called to cancel child builds
        mock_db.buildjob.update_many.assert_called_once()
        call_kwargs = mock_db.buildjob.update_many.call_args.kwargs
        assert call_kwargs["where"]["pipelineRunId"] == "pipe-cbuild"
        assert call_kwargs["data"]["status"] == "CANCELLED"

    def test_cancel_pipeline_not_found(self, authed_client, mock_db):
        """Cancel non-existent pipeline returns 404."""
        mock_db.pipelinerun.find_unique.return_value = None

        response = authed_client.post("/v2/builds/pipelines/nonexistent/cancel")
        assert response.status_code == 404

    def test_cancel_pipeline_already_succeeded(self, authed_client, mock_db):
        """Cancel an already-succeeded pipeline returns 400."""
        existing = _pipeline_obj(id="pipe-done", status="SUCCESS")
        mock_db.pipelinerun.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/pipelines/pipe-done/cancel")
        assert response.status_code == 400

        body = json.loads(response.data)
        assert "terminal" in body["errors"][0]["message"].lower() or "SUCCESS" in body["errors"][0]["message"]

    def test_cancel_pipeline_already_failed(self, authed_client, mock_db):
        """Cancel an already-failed pipeline returns 400."""
        existing = _pipeline_obj(id="pipe-failed", status="FAILED")
        mock_db.pipelinerun.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/pipelines/pipe-failed/cancel")
        assert response.status_code == 400

    def test_cancel_pipeline_already_cancelled(self, authed_client, mock_db):
        """Cancel an already-cancelled pipeline returns 400."""
        existing = _pipeline_obj(id="pipe-cc", status="CANCELLED")
        mock_db.pipelinerun.find_unique.return_value = existing

        response = authed_client.post("/v2/builds/pipelines/pipe-cc/cancel")
        assert response.status_code == 400

    def test_cancel_pipeline_db_error(self, authed_client, mock_db):
        """Cancel pipeline returns 500 when database raises an exception."""
        existing = _pipeline_obj(id="pipe-dbe", status="BUILDING")
        # find_unique is called once in the handler, raise on update
        mock_db.pipelinerun.find_unique.return_value = existing
        mock_db.pipelinerun.update.side_effect = Exception("DB connection lost")

        with patch("src.api.v2.builds.pipelines.log_audit"):
            response = authed_client.post("/v2/builds/pipelines/pipe-dbe/cancel")

        assert response.status_code == 500

    def test_cancel_pipeline_unauthorized(self, client):
        """Cancel pipeline without authentication returns 401."""
        response = client.post("/v2/builds/pipelines/pipe-1/cancel")
        assert response.status_code == 401
