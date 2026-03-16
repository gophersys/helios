"""Tests for CI request type validation."""
import pytest

from src.api.v2.builds.types import (
    BitbucketWebhookPayload,
    CiTriggerRequest,
    BuildCreateRequest,
    PipelineCreateRequest,
)


class TestBitbucketWebhookPayload:
    def test_valid_pr_opened(self):
        data = {
            "eventKey": "pr:opened",
            "repository": {"slug": "alpha_fw", "project": {"key": "FIRM"}},
            "pullRequest": {
                "id": 42,
                "title": "Add sensor support",
                "fromRef": {
                    "displayId": "feature/sensor",
                    "latestCommit": "abc123def456",
                },
                "toRef": {"displayId": "main"},
            },
        }
        payload, error = BitbucketWebhookPayload.from_json(data)
        assert error is None
        assert payload.event_key == "pr:opened"
        assert payload.repo_slug == "alpha_fw"
        assert payload.project_key == "FIRM"
        assert payload.branch == "feature/sensor"
        assert payload.commit_sha == "abc123def456"
        assert payload.pr_id == 42
        assert payload.pr_title == "Add sensor support"

    def test_valid_push_event(self):
        data = {
            "eventKey": "repo:refs_changed",
            "repository": {"slug": "alpha_mfg_fw", "project": {"key": "FIRM"}},
            "changes": [{
                "ref": {"id": "refs/heads/concord-main", "displayId": "concord-main"},
                "toHash": "deadbeef12345678",
            }],
        }
        payload, error = BitbucketWebhookPayload.from_json(data)
        assert error is None
        assert payload.event_key == "repo:refs_changed"
        assert payload.branch == "concord-main"
        assert payload.commit_sha == "deadbeef12345678"
        assert payload.pr_id is None

    def test_missing_event_key(self):
        data = {"repository": {"slug": "alpha_fw"}}
        payload, error = BitbucketWebhookPayload.from_json(data)
        assert payload is None
        assert "eventKey" in error

    def test_missing_repo_slug(self):
        data = {"eventKey": "pr:opened", "repository": {"project": {"key": "FIRM"}}}
        payload, error = BitbucketWebhookPayload.from_json(data)
        assert payload is None
        assert "slug" in error

    def test_empty_data(self):
        payload, error = BitbucketWebhookPayload.from_json(None)
        assert payload is None
        assert "JSON" in error


class TestCiTriggerRequest:
    def test_valid_trigger(self):
        data = {
            "productId": "abc123",
            "repoSlug": "alpha_fw",
            "branch": "concord-main",
            "variant": "debug",
        }
        req, error = CiTriggerRequest.from_json(data)
        assert error is None
        assert req.product_id == "abc123"
        assert req.repo_slug == "alpha_fw"
        assert req.branch == "concord-main"
        assert req.variant == "debug"
        assert req.mtib_rev == "1.2"

    def test_missing_product_id(self):
        data = {"repoSlug": "alpha_fw", "branch": "main"}
        req, error = CiTriggerRequest.from_json(data)
        assert req is None
        assert "productId" in error

    def test_invalid_variant(self):
        data = {
            "productId": "abc",
            "repoSlug": "alpha_fw",
            "branch": "main",
            "variant": "invalid",
        }
        req, error = CiTriggerRequest.from_json(data)
        assert req is None
        assert "variant" in error


class TestBuildCreateRequest:
    def test_valid_build(self):
        data = {
            "product": "alpha",
            "board": "alpha_b0",
            "target": "app",
            "variant": "debug",
            "branch": "concord-main",
        }
        req, error = BuildCreateRequest.from_json(data)
        assert error is None
        assert req.product == "alpha"
        assert req.board == "alpha_b0"
        assert req.variant == "debug"

    def test_missing_product(self):
        data = {"board": "alpha_b0", "target": "app", "branch": "main"}
        req, error = BuildCreateRequest.from_json(data)
        assert req is None
        assert "product" in error


class TestPipelineCreateRequest:
    def test_valid_pipeline(self):
        data = {
            "name": "Alpha CI",
            "product": "alpha",
            "board": "alpha_b0",
            "branch": "concord-main",
        }
        req, error = PipelineCreateRequest.from_json(data)
        assert error is None
        assert req.name == "Alpha CI"
        assert req.build_variant == "debug"

    def test_pipeline_without_name(self):
        """Name is optional - pipeline gets auto-generated name."""
        data = {"product": "alpha", "board": "alpha_b0", "branch": "main"}
        req, error = PipelineCreateRequest.from_json(data)
        assert error is None
        assert req.name is None
        assert req.product == "alpha"
        assert req.branch == "main"

    def test_missing_product(self):
        data = {"board": "alpha_b0", "branch": "main"}
        req, error = PipelineCreateRequest.from_json(data)
        assert req is None
        assert "product" in error

    def test_pipeline_build_variants(self):
        """Pipeline creates builds with both debug and release variants."""
        data = {
            "product": "alpha",
            "board": "alpha_b0",
            "branch": "main",
            "buildVariant": "debug",
        }
        req, error = PipelineCreateRequest.from_json(data)
        assert error is None
        assert req.build_variant == "debug"
        # Note: The actual 4-build creation happens in create_pipeline(),
        # which creates both debug and release variants regardless of buildVariant
