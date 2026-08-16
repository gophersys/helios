"""Test build lifecycle with real DB and MinIO.

Covers build listing, status, and artifact retrieval.

NOTE: Build creation via POST /v2/builds has a known bug where
`triggerType` is passed to Prisma but doesn't exist in the BuildJob
schema. Tests that depend on creating builds use the Prisma client
directly to insert test data.
"""

import io
import pytest
import uuid
from datetime import datetime, timezone


def _get_alpha_id(test_api, admin_headers):
    """Get the Alpha product ID."""
    resp = test_api.get("/v2/products", headers=admin_headers)
    products = resp.get_json()["data"]["data"]
    alpha = next(p for p in products if p["name"] == "Alpha")
    return alpha["id"]


class TestListBuilds:
    """Test build listing."""

    def test_list_builds_returns_200(self, test_api, admin_headers):
        """GET /v2/builds returns 200 with pagination."""
        resp = test_api.get("/v2/builds", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "data" in body


class TestCreateBuild:
    """Test build creation validation."""

    def test_create_build_missing_fields_returns_400(self, test_api, admin_headers):
        """POST /v2/builds with missing required fields returns 400."""
        resp = test_api.post("/v2/builds", headers=admin_headers, json={})
        assert resp.status_code == 400

    def test_create_build_missing_board_returns_400(self, test_api, admin_headers):
        """POST /v2/builds without board returns 400."""
        product_id = _get_alpha_id(test_api, admin_headers)
        resp = test_api.post("/v2/builds", headers=admin_headers, json={
            "productId": product_id,
            "branch": "main",
            "target": "app",
            "variant": "debug",
            "triggerTypes": "manual",
        })
        assert resp.status_code == 400

    def test_create_build_invalid_variant_returns_400(self, test_api, admin_headers):
        """POST /v2/builds with invalid variant returns 400."""
        product_id = _get_alpha_id(test_api, admin_headers)
        resp = test_api.post("/v2/builds", headers=admin_headers, json={
            "productId": product_id,
            "branch": "main",
            "board": "alpha_b0",
            "target": "app",
            "variant": "invalid",
            "triggerTypes": "manual",
        })
        assert resp.status_code == 400


class TestBuildLifecycle:
    """Test build operations with DB-inserted builds."""

    def test_get_build_not_found(self, test_api, admin_headers):
        """GET /v2/builds/<fake_id> returns 404."""
        fake_id = "clxxxxxxxxxxxxxxxxxxxxxxxxx"
        resp = test_api.get(f"/v2/builds/{fake_id}", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_build_by_id(self, test_api, admin_headers, _prisma_client):
        """GET /v2/builds/<id> returns build details."""
        product_id = _get_alpha_id(test_api, admin_headers)

        # Insert a build directly via Prisma (bypassing the buggy API)
        build = _prisma_client.buildjob.create(data={
            "productId": product_id,
            "board": "alpha_b0",
            "target": "app",
            "variant": "debug",
            "branch": "main",
            "status": "QUEUED",
        })

        resp = test_api.get(f"/v2/builds/{build.id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["id"] == build.id
        assert data["board"] == "alpha_b0"
        assert data["status"] == "QUEUED"

    def test_update_build_status(self, test_api, admin_headers, _prisma_client):
        """PATCH /v2/builds/<id> updates status."""
        product_id = _get_alpha_id(test_api, admin_headers)

        build = _prisma_client.buildjob.create(data={
            "productId": product_id,
            "board": "alpha_b0",
            "target": "app",
            "variant": "debug",
            "branch": "main",
            "status": "QUEUED",
        })

        # Claim the build
        resp = test_api.patch(f"/v2/builds/{build.id}", headers=admin_headers, json={
            "status": "BUILDING",
            "workerId": "test-worker-1",
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "BUILDING"

        # Complete it
        complete_resp = test_api.patch(f"/v2/builds/{build.id}", headers=admin_headers, json={
            "status": "SUCCESS",
            "versionString": "0.99.0-test",
        })
        assert complete_resp.status_code == 200
        assert complete_resp.get_json()["data"]["status"] == "SUCCESS"
        assert complete_resp.get_json()["data"]["versionString"] == "0.99.0-test"

    def test_upload_and_list_artifacts(self, test_api, admin_headers, _prisma_client, test_minio):
        """Upload an artifact and list it back."""
        product_id = _get_alpha_id(test_api, admin_headers)

        build = _prisma_client.buildjob.create(data={
            "productId": product_id,
            "board": "alpha_b0",
            "target": "app",
            "variant": "debug",
            "branch": "main",
            "status": "BUILDING",
        })

        # Upload artifact
        artifact_data = b"fake firmware hex content for integration test"
        upload_resp = test_api.post(
            f"/v2/builds/{build.id}/artifacts",
            headers={"Authorization": admin_headers["Authorization"]},
            data={"file": (io.BytesIO(artifact_data), "test_firmware.hex")},
            content_type="multipart/form-data",
        )
        assert upload_resp.status_code in (200, 201), f"Upload failed: {upload_resp.get_json()}"

        # List artifacts
        list_resp = test_api.get(f"/v2/builds/{build.id}/artifacts", headers=admin_headers)
        assert list_resp.status_code == 200
        artifacts = list_resp.get_json()["data"]
        if isinstance(artifacts, dict) and "data" in artifacts:
            artifacts = artifacts["data"]
        assert len(artifacts) >= 1

    def test_cannot_claim_already_building(self, test_api, admin_headers, _prisma_client):
        """PATCH /v2/builds/<id> with BUILDING on non-QUEUED build returns 409."""
        product_id = _get_alpha_id(test_api, admin_headers)

        build = _prisma_client.buildjob.create(data={
            "productId": product_id,
            "board": "alpha_b0",
            "target": "app",
            "variant": "debug",
            "branch": "main",
            "status": "BUILDING",
        })

        resp = test_api.patch(f"/v2/builds/{build.id}", headers=admin_headers, json={
            "status": "BUILDING",
        })
        assert resp.status_code == 409
