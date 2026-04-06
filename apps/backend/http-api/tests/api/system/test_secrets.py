"""Integration tests for the Secrets API.

Secret values must NEVER appear in API responses.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


# ── Helpers ──────────────────────────────────────────────────


def _make_secret(id="sec-1", **overrides):
    defaults = {
        "name": "my-signing-key",
        "type": "signing_key",
        "description": "Test signing key",
        "value": "super-secret-value-do-not-leak",
        "createdAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return make_obj(id=id, **defaults)


# ── List ─────────────────────────────────────────────────────


def test_list_secrets(authed_client, mock_db):
    """GET /v2/system/secrets returns secrets without values."""
    mock_db.secret.find_many.return_value = [
        _make_secret(id="sec-1", name="key-a"),
        _make_secret(id="sec-2", name="key-b", type="api_token"),
    ]

    response = authed_client.get("/v2/system/secrets")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert len(data["data"]) == 2
    assert len(data["errors"]) == 0

    # Value must NEVER appear in the response
    raw = response.data.decode("utf-8")
    assert "super-secret-value-do-not-leak" not in raw
    for item in data["data"]:
        assert "value" not in item


def test_list_secrets_unauthorized(client):
    """GET /v2/system/secrets without auth returns 401."""
    response = client.get("/v2/system/secrets")
    assert response.status_code == 401


# ── Create ───────────────────────────────────────────────────


def test_create_secret(authed_client, mock_db):
    """POST /v2/system/secrets creates a new secret."""
    mock_db.secret.find_first.return_value = None
    mock_db.user.find_unique.return_value = None

    created = _make_secret(id="sec-new", name="new-key", type="ssh_key")
    mock_db.secret.create.return_value = created

    with patch("src.api.v2.system.secrets.log_audit"):
        response = authed_client.post(
            "/v2/system/secrets",
            data=json.dumps({
                "name": "new-key",
                "type": "ssh_key",
                "value": "the-actual-secret-value",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "sec-new"
    assert data["data"]["name"] == "new-key"

    # Value must NEVER appear in response
    raw = response.data.decode("utf-8")
    assert "the-actual-secret-value" not in raw
    assert "super-secret-value-do-not-leak" not in raw
    assert "value" not in data["data"]


def test_create_secret_duplicate(authed_client, mock_db):
    """POST /v2/system/secrets returns 409 when name already exists."""
    mock_db.secret.find_first.return_value = _make_secret(id="existing")

    response = authed_client.post(
        "/v2/system/secrets",
        data=json.dumps({
            "name": "my-signing-key",
            "type": "signing_key",
            "value": "some-value",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_create_secret_missing_name(authed_client, mock_db):
    """POST /v2/system/secrets returns 400 without name."""
    response = authed_client.post(
        "/v2/system/secrets",
        data=json.dumps({"type": "signing_key", "value": "x"}),
    )
    assert response.status_code == 400


def test_create_secret_invalid_type(authed_client, mock_db):
    """POST /v2/system/secrets returns 400 for invalid type."""
    response = authed_client.post(
        "/v2/system/secrets",
        data=json.dumps({
            "name": "key",
            "type": "invalid_type",
            "value": "x",
        }),
    )
    assert response.status_code == 400


# ── Update ───────────────────────────────────────────────────


def test_update_secret(authed_client, mock_db):
    """PUT /v2/system/secrets/<id> rotates value or updates description."""
    mock_db.secret.find_unique.return_value = _make_secret(id="sec-upd")

    updated = _make_secret(
        id="sec-upd",
        description="Updated description",
        updatedAt=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    # find_unique is called twice: once for existence check, once for re-fetch
    mock_db.secret.find_unique.side_effect = [
        _make_secret(id="sec-upd"),
        updated,
    ]

    with patch("src.api.v2.system.secrets.log_audit"):
        response = authed_client.put(
            "/v2/system/secrets/sec-upd",
            data=json.dumps({"description": "Updated description"}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "Updated description"

    # Value must NEVER appear in response
    raw = response.data.decode("utf-8")
    assert "super-secret-value-do-not-leak" not in raw
    assert "value" not in data["data"]


def test_update_secret_not_found(authed_client, mock_db):
    """PUT /v2/system/secrets/<id> returns 404 when not found."""
    mock_db.secret.find_unique.return_value = None

    response = authed_client.put(
        "/v2/system/secrets/missing",
        data=json.dumps({"description": "x"}),
    )
    assert response.status_code == 404


def test_update_secret_no_fields(authed_client, mock_db):
    """PUT /v2/system/secrets/<id> returns 400 with no valid fields."""
    mock_db.secret.find_unique.return_value = _make_secret(id="sec-noop")

    response = authed_client.put(
        "/v2/system/secrets/sec-noop",
        data=json.dumps({"name": "cant-change-name"}),
    )
    assert response.status_code == 400


# ── Delete ───────────────────────────────────────────────────


def test_delete_secret(authed_client, mock_db):
    """DELETE /v2/system/secrets/<id> deletes unreferenced secret."""
    mock_db.secret.find_unique.return_value = _make_secret(id="sec-del")
    mock_db.productstageconfig.count.return_value = 0

    with patch("src.api.v2.system.secrets.log_audit"):
        response = authed_client.delete("/v2/system/secrets/sec-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
    mock_db.secret.delete.assert_called_once_with(where={"id": "sec-del"})


def test_delete_secret_not_found(authed_client, mock_db):
    """DELETE /v2/system/secrets/<id> returns 404 when not found."""
    mock_db.secret.find_unique.return_value = None

    response = authed_client.delete("/v2/system/secrets/missing")
    assert response.status_code == 404


def test_delete_secret_has_refs(authed_client, mock_db):
    """DELETE /v2/system/secrets/<id> returns 400 when stage configs reference it."""
    mock_db.secret.find_unique.return_value = _make_secret(id="sec-ref")
    mock_db.productstageconfig.count.return_value = 2

    response = authed_client.delete("/v2/system/secrets/sec-ref")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
