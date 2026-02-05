"""
Unit tests for codebase types validation in src/api/v2/codebases/types.py.

Tests all from_json() methods and to_update_data() methods.
"""

import pytest


def test_codebase_create_valid():
    from src.api.v2.codebases.types import CodebaseCreateRequest

    data = {
        "name": "Firmware SDK",
        "description": "Main firmware codebase",
        "repoUrl": "https://github.com/example/firmware",
        "defaultBranch": "main",
    }
    req, err = CodebaseCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Firmware SDK"
    assert req.description == "Main firmware codebase"
    assert req.repoUrl == "https://github.com/example/firmware"
    assert req.defaultBranch == "main"


def test_codebase_create_missing_name():
    from src.api.v2.codebases.types import CodebaseCreateRequest

    data = {"description": "Test"}
    req, err = CodebaseCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_codebase_create_invalid_repo_url_protocol():
    from src.api.v2.codebases.types import CodebaseCreateRequest

    data = {"name": "Test", "repoUrl": "ftp://example.com/repo"}
    req, err = CodebaseCreateRequest.from_json(data)

    assert req is None
    assert err == "Repository URL must use http or https protocol"


def test_codebase_create_valid_https_repo_url():
    from src.api.v2.codebases.types import CodebaseCreateRequest

    data = {"name": "Test", "repoUrl": "https://github.com/example/repo"}
    req, err = CodebaseCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.repoUrl == "https://github.com/example/repo"


def test_codebase_update_valid():
    from src.api.v2.codebases.types import CodebaseUpdateRequest

    data = {"name": "Updated Codebase", "defaultBranch": "develop"}
    req, err = CodebaseUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Codebase"
    assert req.defaultBranch == "develop"

    update_data = req.to_update_data()
    assert update_data["name"] == "Updated Codebase"
    assert update_data["defaultBranch"] == "develop"


def test_codebase_update_no_fields():
    from src.api.v2.codebases.types import CodebaseUpdateRequest

    req, err = CodebaseUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = CodebaseUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_codebase_update_empty_name():
    from src.api.v2.codebases.types import CodebaseUpdateRequest

    data = {"name": "   "}
    req, err = CodebaseUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


def test_codebase_update_invalid_repo_url():
    from src.api.v2.codebases.types import CodebaseUpdateRequest

    data = {"repoUrl": "ftp://example.com/repo"}
    req, err = CodebaseUpdateRequest.from_json(data)

    assert req is None
    assert err == "Repository URL must use http or https protocol"


def test_codebase_update_to_update_data():
    from src.api.v2.codebases.types import CodebaseUpdateRequest

    data = {"description": None, "repoUrl": "https://github.com/new/repo"}
    req, err = CodebaseUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "description" in update_data
    assert update_data["description"] is None
    assert update_data["repoUrl"] == "https://github.com/new/repo"


def test_release_create_valid():
    from src.api.v2.codebases.types import ReleaseCreateRequest

    data = {
        "version": "v1.2.3",
        "status": "RELEASED",
        "releaseNotes": "Bug fixes",
        "tagName": "release-1.2.3",
    }
    req, err = ReleaseCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v1.2.3"
    assert req.status == "RELEASED"
    assert req.releaseNotes == "Bug fixes"
    assert req.tagName == "release-1.2.3"


def test_release_create_missing_version():
    from src.api.v2.codebases.types import ReleaseCreateRequest

    data = {"status": "DRAFT"}
    req, err = ReleaseCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_release_create_invalid_status():
    from src.api.v2.codebases.types import ReleaseCreateRequest

    data = {"version": "v1.0.0", "status": "INVALID"}
    req, err = ReleaseCreateRequest.from_json(data)

    assert req is None
    assert err == "Status must be DRAFT, RELEASED, or DEPRECATED"


def test_release_update_valid():
    from src.api.v2.codebases.types import ReleaseUpdateRequest

    data = {"status": "DEPRECATED", "releaseNotes": "No longer supported"}
    req, err = ReleaseUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.status == "DEPRECATED"
    assert req.releaseNotes == "No longer supported"

    update_data = req.to_update_data()
    assert update_data["status"] == "DEPRECATED"
    assert update_data["releaseNotes"] == "No longer supported"


def test_release_update_no_fields():
    from src.api.v2.codebases.types import ReleaseUpdateRequest

    req, err = ReleaseUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = ReleaseUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_release_update_invalid_status():
    from src.api.v2.codebases.types import ReleaseUpdateRequest

    data = {"status": "INVALID"}
    req, err = ReleaseUpdateRequest.from_json(data)

    assert req is None
    assert err == "Status must be DRAFT, RELEASED, or DEPRECATED"


def test_release_update_to_update_data():
    from src.api.v2.codebases.types import ReleaseUpdateRequest

    data = {"releaseNotes": None, "tagName": "v2.0"}
    req, err = ReleaseUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "releaseNotes" in update_data
    assert update_data["releaseNotes"] is None
    assert update_data["tagName"] == "v2.0"


def test_artifact_create_valid():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"name": "Build Artifact", "externalUrl": "https://cdn.example.com/artifact.zip"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Build Artifact"
    assert req.externalUrl == "https://cdn.example.com/artifact.zip"


def test_artifact_create_missing_name():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"externalUrl": "https://example.com/file"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_artifact_create_missing_url():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"name": "Artifact"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert req is None
    assert err == "External URL is required"


def test_artifact_create_invalid_protocol_javascript():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"name": "Test", "externalUrl": "javascript:alert(1)"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert req is None
    assert err == "External URL must use http or https protocol"


def test_artifact_create_invalid_protocol_data():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"name": "Test", "externalUrl": "data:text/html,<script>alert(1)</script>"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert req is None
    assert err == "External URL must use http or https protocol"


def test_artifact_create_invalid_protocol_ftp():
    from src.api.v2.codebases.types import ArtifactCreateRequest

    data = {"name": "Test", "externalUrl": "ftp://example.com/file"}
    req, err = ArtifactCreateRequest.from_json(data)

    assert req is None
    assert err == "External URL must use http or https protocol"
