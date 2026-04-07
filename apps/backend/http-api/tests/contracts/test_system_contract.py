"""
API contract tests for /v2/system and /v2/healthcheck endpoints.

Shapes derived from:
  - healthcheck() in src/api/v2/system/healthcheck.py
  - _serialize() in src/api/v2/system/poller_state.py
"""

import json
from datetime import datetime, timezone

import pytest

from tests.conftest import make_obj
from tests.contracts.validate import assert_envelope, assert_response_shape

# ---------------------------------------------------------------------------
# Shape definitions
# ---------------------------------------------------------------------------

_HEALTH_SHAPE = {
    "status": str,
    "service": str,
}

_POLLER_STATE_SHAPE = {
    "id": str,
    "repoSlug": str,
    "type": str,
    "refId": str,
    "commitSha": str,
    "metadata": (dict, type(None)),
    "createdAt": str,
    "updatedAt": str,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_poll_entry(**kwargs):
    defaults = dict(
        id="pc-1",
        repoSlug="alpha_fw",
        type="branch",
        refId="main",
        commitSha="abc123",
        metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Test: GET /v2/healthcheck
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_health_response_shape(client):
    """GET /v2/healthcheck returns status + service fields without auth."""
    resp = client.get("/v2/healthcheck")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))
    assert_response_shape(data, _HEALTH_SHAPE)

    # The service is always "http-api"
    assert data["service"] == "http-api", "service field must be 'http-api'"
    assert data["status"] == "healthy", "status field must be 'healthy'"

    # TODO: test_health_no_auth_required (healthcheck is always public)


# ---------------------------------------------------------------------------
# Test: GET /v2/system/poller-state
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_poller_state_response_shape(authed_client, mock_db):
    """GET /v2/system/poller-state returns a list of poll cache entries."""
    mock_db.pollcache.find_many.return_value = [
        _make_poll_entry(type="branch"),
        _make_poll_entry(id="pc-2", type="pr", refId="42", metadata={"title": "My PR"}),
    ]

    resp = authed_client.get("/v2/system/poller-state")

    assert resp.status_code == 200
    data = assert_envelope(json.loads(resp.data))

    assert isinstance(data, list)
    assert len(data) == 2

    for entry in data:
        assert_response_shape(entry, _POLLER_STATE_SHAPE)

    # type must be one of the documented enum values
    for entry in data:
        assert entry["type"] in ("branch", "pr"), (
            f"type must be 'branch' or 'pr', got {entry['type']!r}"
        )

    # TODO: test_poller_state_unauthenticated_returns_401
    # TODO: test_poller_state_filtered_by_repo_slug
    # TODO: test_poller_state_metadata_nullable_field
