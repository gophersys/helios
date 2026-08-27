"""
API contract tests for /v2/builds endpoints.

Shapes derived from _serialize_build_job() and _serialize_build_artifact()
in src/api/v2/builds/builds.py.
"""

import json
from datetime import datetime, timezone

import pytest

from tests.conftest import make_obj
from tests.contracts.validate import assert_envelope, assert_response_shape

# ---------------------------------------------------------------------------
# Shape definitions
# ---------------------------------------------------------------------------

_BUILD_ARTIFACT_SHAPE = {
    "id": str,
    "buildJobId": str,
    "name": str,
    "storageKey": str,
    "sizeBytes": int,
    "checksum": str,
    "role": (str, type(None)),
    "processor": (str, type(None)),
    "artifactType": (str, type(None)),
    "contentType": (str, type(None)),
    "createdAt": str,
}

_BUILD_JOB_SHAPE = {
    "id": str,
    "product": (str, type(None)),
    "productId": (str, type(None)),
    "productName": (str, type(None)),
    "board": (str, type(None)),
    "target": (str, type(None)),
    "variant": (str, type(None)),
    "mtibRev": (str, type(None)),
    "branch": (str, type(None)),
    "commitSha": (str, type(None)),
    "status": str,
    "versionMajor": (int, type(None)),
    "versionMinor": (int, type(None)),
    "buildNum": (int, type(None)),
    "versionString": (str, type(None)),
    "errorMessage": (str, type(None)),
    "workerId": (str, type(None)),
    "webhookData": (dict, type(None)),
    "startedAt": (str, type(None)),
    "finishedAt": (str, type(None)),
    "durationSeconds": (int, type(None)),
    "createdAt": str,
    "updatedAt": str,
    "matrixLabel": (str, type(None)),
    "matrixIndex": (int, type(None)),
    "versionBump": (bool, type(None)),
    "baseJobId": (str, type(None)),
    "configFlags": (dict, type(None)),
    "reusedFromId": (str, type(None)),
    "buildFingerprint": (str, type(None)),
    "recipeVersionId": (str, type(None)),
    "triggerTypes": (str, type(None)),
    "notes": (str, type(None)),
    "stage": (int, type(None)),
    "artifacts": list,
    "artifactCount": int,
}

_PAGINATION_SHAPE = {
    "page": int,
    "limit": int,
    "total": int,
    "pages": int,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact(**kwargs):
    defaults = dict(
        id="art-1",
        buildJobId="build-1",
        name="app_nrf52840.hex",
        storageKey="firmware-builds/alpha_b0/build-1/app_nrf52840.hex",
        sizeBytes=123456,
        checksum="abc123def456",
        role="app",
        processor="nrf52840",
        artifactType="hex",
        contentType="application/octet-stream",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


def _make_build(**kwargs):
    defaults = dict(
        id="build-1",
        productId="prod-1",
        product=make_obj(id="prod-1", name="Alpha B0", slug="alpha_b0"),
        board="alpha_b0",
        target="app",
        variant="debug",
        mtibRev="1.2",
        branch="main",
        commitSha="abc1234",
        status="SUCCESS",
        versionMajor=0,
        versionMinor=5,
        buildNum=2,
        versionString="0.5.2",
        errorMessage=None,
        workerId=None,
        webhookData=None,
        startedAt=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        finishedAt=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
        durationSeconds=300,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        matrixLabel=None,
        matrixIndex=None,
        versionBump=False,
        baseJobId=None,
        configFlags=None,
        reusedFromId=None,
        buildFingerprint=None,
        recipeVersionId=None,
        triggerType="worker",
        notes=None,
        artifacts=[],
        buildRun=None,
        buildRunId=None,
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Test: GET /v2/builds
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_builds_response_shape(authed_client, mock_db):
    """GET /v2/builds returns a paginated envelope containing build job objects."""
    mock_db.buildjob.count.return_value = 1
    mock_db.buildjob.find_many.return_value = [_make_build()]

    resp = authed_client.get("/v2/builds")

    assert resp.status_code == 200
    body = assert_envelope(json.loads(resp.data))

    assert "data" in body
    assert "pagination" in body
    assert_response_shape(body["pagination"], _PAGINATION_SHAPE)

    if body["data"]:
        assert_response_shape(body["data"][0], _BUILD_JOB_SHAPE)

    # TODO: test_list_builds_filter_by_status
    # TODO: test_list_builds_filter_by_product_id
    # TODO: test_list_builds_filter_by_branch


# ---------------------------------------------------------------------------
# Test: GET /v2/builds/<id>
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_build_response_shape(authed_client, mock_db):
    """GET /v2/builds/<id> returns a build job with artifacts and buildLog."""
    artifact = _make_artifact()
    build = _make_build(artifacts=[artifact], buildLog="Build output here...")
    mock_db.buildjob.find_unique.return_value = build

    resp = authed_client.get("/v2/builds/build-1")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _BUILD_JOB_SHAPE)

    # Detail view includes buildLog
    assert "buildLog" in data, "Detail view must include buildLog"
    assert isinstance(data["buildLog"], (str, type(None)))

    # Artifacts are embedded in the response
    assert data["artifactCount"] == 1
    assert_response_shape(data["artifacts"][0], _BUILD_ARTIFACT_SHAPE)

    # TODO: test_get_build_not_found_returns_404
    # TODO: test_get_build_no_artifacts_returns_empty_list
