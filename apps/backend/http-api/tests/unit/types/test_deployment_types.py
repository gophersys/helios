"""Unit tests for deployment types validation."""

import pytest


def test_deployment_create_valid():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    data = {"name": "Deploy 1", "fixtureId": "fix-1", "version": "1.0"}
    req, err = DeploymentCreateRequest.from_json(data)
    assert err is None
    assert req.name == "Deploy 1"
    assert req.fixtureId == "fix-1"
    assert req.version == "1.0"


def test_deployment_create_missing_name():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    req, err = DeploymentCreateRequest.from_json({"fixtureId": "fix-1"})
    assert req is None
    assert err == "Name is required"


def test_deployment_create_missing_fixture_id():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    req, err = DeploymentCreateRequest.from_json({"name": "Deploy"})
    assert req is None
    assert err == "Fixture ID is required"


def test_deployment_create_null_body():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    req, err = DeploymentCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_deployment_create_with_config():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    data = {"name": "D", "fixtureId": "f", "config": {"image": "test:latest"}}
    req, err = DeploymentCreateRequest.from_json(data)
    assert err is None
    assert req.config == {"image": "test:latest"}


def test_deployment_create_optional_fields():
    from src.api.v2.kubernetes.deployment_types import DeploymentCreateRequest
    data = {"name": "Deploy", "fixtureId": "fix-1"}
    req, err = DeploymentCreateRequest.from_json(data)
    assert err is None
    assert req.config is None
    assert req.version is None
