"""Tests for API Keys API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.lib.permissions import Permissions
from tests.conftest import make_obj

_all_perms = list(Permissions.all())


def test_list_api_keys(authed_client, mock_db):
    """Test listing API keys with pagination."""
    mock_db.apikey.count.return_value = 1
    mock_db.apikey.find_many.return_value = [
        make_obj(
            id="key-1",
            name="CI Deploy Key",
            keyPrefix="ck_live_abcdef01",
            userId="user-1",
            user=make_obj(name="Alice"),
            expiresAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
            lastUsedAt=datetime(2025, 6, 15, tzinfo=timezone.utc),
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/api-keys")
    assert response.status_code == 200

    body = json.loads(response.data)
    assert "data" in body
    assert "data" in body["data"]
    assert "pagination" in body["data"]
    assert len(body["data"]["data"]) == 1
    assert body["data"]["pagination"]["total"] == 1

    first = body["data"]["data"][0]
    assert first["id"] == "key-1"
    assert first["name"] == "CI Deploy Key"
    assert first["userName"] == "Alice"


def test_create_api_key(authed_client, mock_db):
    """Test creating an API key returns 201 with plaintext key."""
    created = make_obj(
        id="key-new",
        name="My Key",
        keyPrefix="ck_live_abcdef01",
        userId="test-user-id",
        expiresAt=None,
        createdAt=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )
    mock_db.apikey.create.return_value = created

    with patch("api.v2.auth.api_keys.log_audit"):
        response = authed_client.post(
            "/v2/api-keys",
            data=json.dumps({"name": "My Key"}),
        )

    assert response.status_code == 201
    body = json.loads(response.data)
    assert body["data"]["id"] == "key-new"
    assert body["data"]["name"] == "My Key"
    # The plaintext key is returned on creation
    assert "key" in body["data"]
    assert body["data"]["key"].startswith("ck_live_")


def test_create_api_key_missing_name(authed_client, mock_db):
    """Test creating an API key without a name returns 400."""
    response = authed_client.post(
        "/v2/api-keys",
        data=json.dumps({}),
    )

    assert response.status_code == 400
    body = json.loads(response.data)
    assert len(body["errors"]) > 0


def test_delete_api_key(authed_client, mock_db):
    """Test deleting an API key."""
    mock_db.apikey.find_unique.return_value = make_obj(
        id="key-1",
        name="Old Key",
    )

    with patch("api.v2.auth.api_keys.log_audit"):
        response = authed_client.delete("/v2/api-keys/key-1")

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["errors"] == []


def test_delete_api_key_not_found(authed_client, mock_db):
    """Test deleting a non-existent API key returns 404."""
    mock_db.apikey.find_unique.return_value = None

    response = authed_client.delete("/v2/api-keys/nonexistent")

    assert response.status_code == 404
    body = json.loads(response.data)
    assert len(body["errors"]) > 0
