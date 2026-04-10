"""Extended tests for build_runs.py — validate, filter, and pipeline-specific paths."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _pipeline_obj(**overrides):
    defaults = dict(
        id="pipe-001",
        name="alpha-main-abc1234",
        product="alpha",
        board="alpha_b0",
        branch="concord-main",
        commitSha="abc1234567890",
        status="SUCCESS",
        triggerType="manual",
        expectedBuilds=2,
        completedBuilds=2,
        validationRunId=None,
        stageConfigId=None,
        prNumber=None,
        prTitle=None,
        prAuthor=None,
        sourceBranch=None,
        targetBranch=None,
        prUrl=None,
        productId="prod-alpha",
        matrixMode="smoke",
        buildMatrix=None,
        triggerData=None,
        startedAt=_now(),
        finishedAt=_now(),
        createdAt=_now(),
        updatedAt=_now(),
        builds=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _build_summary(**overrides):
    defaults = dict(
        id="build-001",
        product="alpha_fw",
        productId="prod-alpha",
        status="SUCCESS",
        target="app",
        variant="debug",
        board="alpha_b0",
        commitSha="abc1234567890",
        buildNum=None,
        versionString=None,
        durationSeconds=None,
        matrixLabel=None,
        matrixIndex=None,
        versionBump=False,
        baseJobId=None,
        reusedFromId=None,
        artifacts=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# GET /v2/builds/runs — Additional filter paths
# ---------------------------------------------------------------------------

class TestListBuildRunsFilters:
    """Tests for additional filter parameters in list_build_runs."""

    def test_list_with_product_id_filter(self, authed_client, mock_db):
        """productId filter is passed directly to the where clause."""
        mock_db.buildrun.count.return_value = 1
        mock_db.buildrun.find_many.return_value = [_pipeline_obj()]

        response = authed_client.get("/v2/builds/runs?productId=prod-alpha")

        assert response.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["productId"] == "prod-alpha"

    def test_list_with_stage_filter(self, authed_client, mock_db):
        """stage filter is passed to where clause."""
        mock_db.buildrun.count.return_value = 1
        mock_db.buildrun.find_many.return_value = [_pipeline_obj()]

        response = authed_client.get("/v2/builds/runs?stage=4")

        assert response.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["stage"] == 4

    def test_list_with_pr_number_filter(self, authed_client, mock_db):
        """prNumber filter is passed to where clause."""
        mock_db.buildrun.count.return_value = 1
        mock_db.buildrun.find_many.return_value = [_pipeline_obj()]

        response = authed_client.get("/v2/builds/runs?prNumber=42")

        assert response.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["prNumber"] == 42

    def test_list_with_trigger_type_filter(self, authed_client, mock_db):
        """triggerType filter is applied to where clause."""
        mock_db.buildrun.count.return_value = 1
        mock_db.buildrun.find_many.return_value = [_pipeline_obj()]

        response = authed_client.get("/v2/builds/runs?triggerType=poller")

        assert response.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        assert call_args.kwargs["where"]["triggerType"] == "poller"

    def test_list_with_created_after_filter(self, authed_client, mock_db):
        """createdAfter filter creates gte date constraint."""
        mock_db.buildrun.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        response = authed_client.get("/v2/builds/runs?createdAfter=2026-01-01T00:00:00Z")

        assert response.status_code == 200
        call_args = mock_db.buildrun.find_many.call_args
        where = call_args.kwargs["where"]
        assert "createdAt" in where
        assert "gte" in where["createdAt"]

    def test_list_with_created_before_and_after_filters(self, authed_client, mock_db):
        """createdAfter + createdBefore creates gte+lte date range filter."""
        mock_db.buildrun.count.return_value = 0
        mock_db.buildrun.find_many.return_value = []

        response = authed_client.get(
            "/v2/builds/runs?createdAfter=2026-01-01T00:00:00Z&createdBefore=2026-02-01T00:00:00Z"
        )

        assert response.status_code == 200
        where = mock_db.buildrun.find_many.call_args.kwargs["where"]
        assert "gte" in where["createdAt"]
        assert "lte" in where["createdAt"]


# ---------------------------------------------------------------------------
# GET /v2/builds/runs/<id> — Pipeline detail additional paths
# ---------------------------------------------------------------------------

class TestGetBuildRunDetail:
    """Additional tests for GET /v2/builds/runs/<id>."""

    def test_get_pipeline_with_product_obj(self, authed_client, mock_db):
        """Pipeline with embedded product object is serialized correctly."""
        product = make_obj(id="prod-alpha", name="Alpha B0", slug="alpha_b0")
        pipe = _pipeline_obj(id="pipe-prod")
        pipe.product = product
        mock_db.buildrun.find_unique.return_value = pipe

        response = authed_client.get("/v2/builds/runs/pipe-prod")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /v2/builds/runs/<id>/validate — Validate pipeline
# ---------------------------------------------------------------------------

class TestValidateBuildRun:
    """Tests for POST /v2/builds/runs/<id>/validate."""

    def test_validate_pipeline_success(self, authed_client, mock_db):
        """POST validate returns 200 with validationRunId when builds succeed."""
        pipe = _pipeline_obj(
            id="pipe-val",
            status="SUCCESS",
            builds=[_build_summary(status="SUCCESS")],
            validationRunId=None,
        )
        mock_db.buildrun.find_unique.return_value = pipe

        with patch(
            "api.v2.builds.build_runs.trigger_pipeline_validation",
            return_value={"sessionId": "val-run-1", "queued": False},
        ):
            with patch("api.v2.builds.build_runs.log_audit"):
                response = authed_client.post("/v2/builds/runs/pipe-val/validate")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["validationRunId"] == "val-run-1"
        assert body["data"]["status"] == "VALIDATING"

    def test_validate_pipeline_not_found(self, authed_client, mock_db):
        """POST validate returns 404 for nonexistent pipeline."""
        mock_db.buildrun.find_unique.return_value = None

        response = authed_client.post("/v2/builds/runs/nonexistent/validate")

        assert response.status_code == 404

    def test_validate_pipeline_wrong_status_returns_400(self, authed_client, mock_db):
        """POST validate returns 400 when pipeline is still BUILDING."""
        pipe = _pipeline_obj(id="pipe-bld", status="BUILDING")
        mock_db.buildrun.find_unique.return_value = pipe

        response = authed_client.post("/v2/builds/runs/pipe-bld/validate")

        assert response.status_code == 400
        body = json.loads(response.data)
        assert "BUILDING" in body["errors"][0]["message"]

    def test_validate_pipeline_no_succeeded_builds_returns_400(self, authed_client, mock_db):
        """POST validate returns 400 when all builds failed."""
        pipe = _pipeline_obj(
            id="pipe-fail",
            status="FAILED",
            builds=[_build_summary(status="FAILED")],
        )
        mock_db.buildrun.find_unique.return_value = pipe

        response = authed_client.post("/v2/builds/runs/pipe-fail/validate")

        assert response.status_code == 400
        body = json.loads(response.data)
        assert "successful" in body["errors"][0]["message"].lower()

    def test_validate_pipeline_queued_when_prior_active(self, authed_client, mock_db):
        """POST validate queues validation when prior run is still ACTIVE."""
        prior_run = make_obj(id="val-old", status="ACTIVE", fixtureId=None)
        pipe = _pipeline_obj(
            id="pipe-active",
            status="SUCCESS",
            builds=[_build_summary(status="SUCCESS")],
            validationRunId="val-old",
        )
        queue_entry = make_obj(id="qe-1")

        mock_db.buildrun.find_unique.return_value = pipe
        mock_db.testrun.find_unique.return_value = prior_run
        mock_db.validationqueueentry.create.return_value = queue_entry

        with patch("api.v2.builds.build_runs.log_audit"):
            response = authed_client.post("/v2/builds/runs/pipe-active/validate")

        assert response.status_code == 202
        body = json.loads(response.data)
        assert body["data"]["queued"] is True

    def test_validate_pipeline_queued_by_service(self, authed_client, mock_db):
        """POST validate returns 202 when trigger_pipeline_validation returns queued=True."""
        pipe = _pipeline_obj(
            id="pipe-q",
            status="SUCCESS",
            builds=[_build_summary(status="SUCCESS")],
            validationRunId=None,
        )
        mock_db.buildrun.find_unique.return_value = pipe

        with patch(
            "api.v2.builds.build_runs.trigger_pipeline_validation",
            return_value={"queued": True, "entryId": "qe-2", "reason": "no fixture"},
        ):
            with patch("api.v2.builds.build_runs.log_audit"):
                response = authed_client.post("/v2/builds/runs/pipe-q/validate")

        assert response.status_code == 202
        body = json.loads(response.data)
        assert body["data"]["queued"] is True

    def test_validate_pipeline_service_returns_none_gives_500(self, authed_client, mock_db):
        """POST validate returns 500 when trigger_pipeline_validation returns None."""
        pipe = _pipeline_obj(
            id="pipe-none",
            status="SUCCESS",
            builds=[_build_summary(status="SUCCESS")],
            validationRunId=None,
        )
        mock_db.buildrun.find_unique.return_value = pipe

        with patch("api.v2.builds.build_runs.trigger_pipeline_validation", return_value=None):
            response = authed_client.post("/v2/builds/runs/pipe-none/validate")

        assert response.status_code == 500

    def test_validate_pipeline_unauthorized(self, client, mock_db):
        """POST validate without auth returns 401."""
        response = client.post("/v2/builds/runs/pipe-1/validate")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/builds/runs/<id>/sessions — Sessions list
# ---------------------------------------------------------------------------

class TestListBuildRunSessions:
    """Tests for GET /v2/builds/runs/<id>/sessions."""

    def test_list_sessions_success(self, authed_client, mock_db):
        """Returns paginated sessions list for the pipeline."""
        mock_db.buildrun.find_unique.return_value = _pipeline_obj(id="pipe-s")
        session = make_obj(
            id="sess-1", name="Run 1", type="VALIDATION",
            productId="prod-alpha", status="PASSED",
            targetCount=1, completedCount=1, passedCount=5, failedCount=0,
            startedAt=_now(), completedAt=_now(), createdAt=_now(),
        )
        mock_db.testrun.count.return_value = 1
        mock_db.testrun.find_many.return_value = [session]

        response = authed_client.get("/v2/builds/runs/pipe-s/sessions")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["pagination"]["total"] == 1

    def test_list_sessions_pipeline_not_found(self, authed_client, mock_db):
        """Returns 404 when pipeline does not exist."""
        mock_db.buildrun.find_unique.return_value = None

        response = authed_client.get("/v2/builds/runs/nonexistent/sessions")

        assert response.status_code == 404

    # TODO: test_list_sessions_with_product_relation
    # TODO: test_list_sessions_pagination_defaults
