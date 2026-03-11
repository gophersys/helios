"""Integration tests for Codebases API."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_presigned_url():
    """Mock presigned_url in codebases.shared so no real storage connection is made."""
    with patch("api.v2.codebases.shared.presigned_get_url", return_value=None):
        yield


def test_list_codebases(authed_client, mock_db):
    """Test listing codebases with pagination."""
    mock_db.codebase.count.return_value = 2
    mock_db.codebase.find_many.return_value = [
        make_obj(
            id="codebase-1",
            name="Backend API",
            description="REST API for Concord",
            repoUrl="https://github.com/org/backend",
            defaultBranch="main",
            imageKey=None,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            releases=[
                make_obj(
                    id="release-1",
                    codebaseId="codebase-1",
                    version="1.0.0",
                    status="RELEASED",
                    releaseNotes="Initial release",
                    tagName="v1.0.0",
                    releasedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    artifacts=[],
                ),
            ],
        ),
        make_obj(
            id="codebase-2",
            name="Frontend App",
            description="React SPA for Concord",
            repoUrl="https://github.com/org/frontend",
            defaultBranch="main",
            imageKey="codebases/codebase-2/logo.png",
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            releases=[],
        ),
    ]

    response = authed_client.get("/v2/builds/codebases")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_create_codebase(authed_client, mock_db):
    """Test creating a new codebase."""
    mock_db.codebase.find_unique.return_value = None

    mock_db.codebase.create.return_value = make_obj(
        id="codebase-new",
        name="New Codebase",
        description="A new codebase",
        repoUrl="https://github.com/org/new-repo",
        defaultBranch="main",
        imageKey=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        releases=[],
    )

    with patch("api.v2.codebases.codebases.log_audit"):
        response = authed_client.post(
            "/v2/builds/codebases",
            data=json.dumps({
                "name": "New Codebase",
                "description": "A new codebase",
                "repoUrl": "https://github.com/org/new-repo",
                "defaultBranch": "main",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Codebase"
    assert data["data"]["repoUrl"] == "https://github.com/org/new-repo"


def test_create_codebase_duplicate_name(authed_client, mock_db):
    """Test creating codebase with duplicate name returns 409."""
    mock_db.codebase.find_unique.return_value = make_obj(
        id="existing-codebase",
        name="Existing Codebase",
        description="",
        repoUrl="https://github.com/org/existing",
        defaultBranch="main",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/builds/codebases",
        data=json.dumps({"name": "Existing Codebase"}),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_get_codebase(authed_client, mock_db):
    """Test getting a single codebase."""
    mock_db.codebase.find_unique.return_value = make_obj(
        id="codebase-123",
        name="Test Codebase",
        description="A test codebase",
        repoUrl="https://github.com/org/test",
        defaultBranch="main",
        imageKey="codebases/codebase-123/logo.png",
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        releases=[
            make_obj(
                id="release-1",
                codebaseId="codebase-123",
                version="1.0.0",
                status="RELEASED",
                releaseNotes="Initial release",
                tagName="v1.0.0",
                releasedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                artifacts=[],
            ),
        ],
    )

    response = authed_client.get("/v2/builds/codebases/codebase-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "codebase-123"
    assert data["data"]["name"] == "Test Codebase"
    assert "releases" in data["data"]


def test_get_codebase_not_found(authed_client, mock_db):
    """Test getting a non-existent codebase returns 404."""
    mock_db.codebase.find_unique.return_value = None

    response = authed_client.get("/v2/builds/codebases/nonexistent")
    assert response.status_code == 404


def test_update_codebase(authed_client, mock_db):
    """Test updating an existing codebase."""
    existing = make_obj(
        id="codebase-update",
        name="Old Name",
        description="Old description",
        repoUrl="https://github.com/org/old",
        defaultBranch="main",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.codebase.find_unique.return_value = existing

    mock_db.codebase.update.return_value = make_obj(
        id="codebase-update",
        name="Old Name",
        description="New description",
        repoUrl="https://github.com/org/new",
        defaultBranch="develop",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        releases=[],
    )

    with patch("api.v2.codebases.codebases.log_audit"):
        response = authed_client.put(
            "/v2/builds/codebases/codebase-update",
            data=json.dumps({
                "description": "New description",
                "repoUrl": "https://github.com/org/new",
                "defaultBranch": "develop",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "New description"
    assert data["data"]["defaultBranch"] == "develop"


def test_delete_codebase(authed_client, mock_db):
    """Test deleting a codebase."""
    mock_db.codebase.find_unique.return_value = make_obj(
        id="codebase-delete",
        name="Codebase to Delete",
        description="",
        repoUrl="https://github.com/org/delete",
        defaultBranch="main",
        imageKey="codebases/codebase-delete/logo.png",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        releases=[
            make_obj(
                id="release-1",
                codebaseId="codebase-delete",
                artifacts=[
                    make_obj(
                        id="artifact-1",
                        releaseId="release-1",
                        type="UPLOAD",
                        storageKey="artifacts/release-1/artifact-1/file.zip",
                    ),
                ],
            ),
        ],
    )

    mock_storage = MagicMock()
    mock_storage.remove_object = MagicMock()

    with patch("api.v2.codebases.codebases.get_storage_client", return_value=mock_storage):
        with patch("api.v2.codebases.codebases.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.codebases.codebases.log_audit"):
                response = authed_client.delete("/v2/builds/codebases/codebase-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True

    # Verify storage cleanup was called for both artifact and image
    assert mock_storage.remove_object.call_count == 2
