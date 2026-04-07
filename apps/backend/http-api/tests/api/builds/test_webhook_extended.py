"""Extended tests for webhook.py — trigger_build_run and receive_repo_event endpoints."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _product_obj(**overrides):
    defaults = dict(
        id="prod-alpha",
        name="Alpha",
        slug="alpha_fw",
        active=True,
        metadata={"targets": ["app", "comms"], "ncsVersion": "2.6.0"},
        buildConfig=None,
        boards=[
            make_obj(
                ckBoardsFamily="alpha",
                revisions=[
                    make_obj(
                        ckBoardsName="alpha_b0",
                        targets=[
                            make_obj(role="app", soc="nRF52840", appId=109),
                            make_obj(role="comms", soc="nRF9151", appId=108),
                        ],
                    )
                ],
            )
        ],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _build_job(**overrides):
    defaults = dict(
        id="build-1",
        productId="prod-alpha",
        board="alpha_b0",
        target="app",
        variant="debug",
        branch="concord-main",
        commitSha="abc1234",
        status="QUEUED",
        mtibRev="1.2",
        artifacts=[],
        product=make_obj(id="prod-alpha", name="Alpha"),
        buildRun=None,
        buildNum=None,
        versionString=None,
        versionMajor=None,
        versionMinor=None,
        errorMessage=None,
        webhookData=None,
        workerId=None,
        startedAt=None,
        finishedAt=None,
        durationSeconds=None,
        matrixLabel=None,
        matrixIndex=None,
        versionBump=False,
        baseJobId=None,
        reusedFromId=None,
        createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_bitbucket_payload(branch="concord-main", commit_sha="abc1234", repo_slug="alpha_fw"):
    return {
        "eventKey": "repo:refs_changed",
        "repository": {
            "slug": repo_slug,
            "project": {"key": "CK"},
        },
        "changes": [
            {
                "ref": {"id": f"refs/heads/{branch}", "displayId": branch},
                "toHash": commit_sha,
            }
        ],
    }


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# POST /v2/builds/webhooks/bitbucket — valid webhook flow
# ---------------------------------------------------------------------------

class TestWebhookBitbucketFlow:
    """Tests for the happy path and branch-filtering in the Bitbucket webhook."""

    def test_valid_webhook_creates_builds(self, authed_client, client, mock_db):
        """Valid signed webhook for mapped repo on CI branch creates build jobs."""
        secret = "test-secret"
        payload = _make_bitbucket_payload(branch="concord-main")
        payload_bytes = json.dumps(payload).encode()
        sig = _sign_payload(payload_bytes, secret)

        mock_db.product.find_first.return_value = _product_obj()
        job1 = _build_job(id="b1", target="app")
        job2 = _build_job(id="b2", target="comms")
        mock_db.buildjob.create.side_effect = [job1, job2]

        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": secret}):
            with patch("api.v2.builds.webhook.log_audit"):
                with patch("api.v2.builds.webhook.notify_build_service", create=True):
                    response = client.post(
                        "/v2/builds/webhooks/bitbucket",
                        data=payload_bytes,
                        headers={"Content-Type": "application/json", "X-Hub-Signature": sig},
                    )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert len(body["data"]["builds"]) == 2

    def test_webhook_non_ci_branch_returns_ignored(self, client, mock_db):
        """Valid webhook for non-CI branch returns ignored=true without creating builds."""
        secret = "test-secret"
        payload = _make_bitbucket_payload(branch="feature/experiment")
        payload_bytes = json.dumps(payload).encode()
        sig = _sign_payload(payload_bytes, secret)

        mock_db.product.find_first.return_value = _product_obj()

        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": secret}):
            response = client.post(
                "/v2/builds/webhooks/bitbucket",
                data=payload_bytes,
                headers={"Content-Type": "application/json", "X-Hub-Signature": sig},
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["ignored"] is True
        assert "branch" in body["data"]["reason"]

    def test_webhook_unmapped_repo_returns_ignored(self, client, mock_db):
        """Valid webhook for unknown repo slug returns ignored=true."""
        secret = "test-secret"
        payload = _make_bitbucket_payload(repo_slug="unknown-repo")
        payload_bytes = json.dumps(payload).encode()
        sig = _sign_payload(payload_bytes, secret)

        mock_db.product.find_first.return_value = None

        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": secret}):
            response = client.post(
                "/v2/builds/webhooks/bitbucket",
                data=payload_bytes,
                headers={"Content-Type": "application/json", "X-Hub-Signature": sig},
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["ignored"] is True
        assert "repo" in body["data"]["reason"]

    def test_webhook_product_with_custom_trigger_branches(self, client, mock_db):
        """Webhook respects custom triggerBranches set in product metadata."""
        secret = "test-secret"
        payload = _make_bitbucket_payload(branch="release/v2")
        payload_bytes = json.dumps(payload).encode()
        sig = _sign_payload(payload_bytes, secret)

        product = _product_obj(metadata={"triggerBranches": ["release/v2"], "targets": ["app"]})
        mock_db.product.find_first.return_value = product
        mock_db.buildjob.create.return_value = _build_job()

        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": secret}):
            with patch("api.v2.builds.webhook.log_audit"):
                with patch("api.v2.builds.webhook.notify_build_service", create=True):
                    response = client.post(
                        "/v2/builds/webhooks/bitbucket",
                        data=payload_bytes,
                        headers={"Content-Type": "application/json", "X-Hub-Signature": sig},
                    )

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# POST /v2/builds/trigger — Manual trigger
# ---------------------------------------------------------------------------

class TestTriggerBuildRun:
    """Tests for POST /v2/builds/trigger."""

    def test_trigger_build_run_success(self, authed_client, mock_db):
        """POST /v2/builds/trigger with valid payload creates a queued build job."""
        mock_db.product.find_unique.return_value = _product_obj()
        mock_db.buildjob.create.return_value = _build_job()

        with patch("api.v2.builds.webhook.log_audit"):
            with patch("api.v2.builds.webhook.notify_build_service", create=True):
                response = authed_client.post(
                    "/v2/builds/trigger",
                    data=json.dumps({
                        "productId": "prod-alpha",
                        "repoSlug": "alpha_fw",
                        "branch": "concord-main",
                        "variant": "debug",
                    }),
                )

        assert response.status_code == 201
        body = json.loads(response.data)
        assert body["data"]["status"] == "QUEUED"

    def test_trigger_missing_product_id_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/trigger without productId returns 400."""
        response = authed_client.post(
            "/v2/builds/trigger",
            data=json.dumps({"repoSlug": "alpha_fw", "branch": "main"}),
        )
        assert response.status_code == 400

    def test_trigger_missing_branch_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/trigger without branch returns 400."""
        response = authed_client.post(
            "/v2/builds/trigger",
            data=json.dumps({"productId": "prod-1", "repoSlug": "alpha_fw"}),
        )
        assert response.status_code == 400

    def test_trigger_invalid_variant_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/trigger with invalid variant returns 400."""
        response = authed_client.post(
            "/v2/builds/trigger",
            data=json.dumps({
                "productId": "prod-1",
                "repoSlug": "alpha_fw",
                "branch": "main",
                "variant": "invalid",
            }),
        )
        assert response.status_code == 400

    def test_trigger_product_not_found_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/trigger with unknown productId returns 400."""
        mock_db.product.find_unique.return_value = None

        response = authed_client.post(
            "/v2/builds/trigger",
            data=json.dumps({
                "productId": "nonexistent",
                "repoSlug": "alpha_fw",
                "branch": "main",
                "variant": "debug",
            }),
        )
        assert response.status_code == 400
        body = json.loads(response.data)
        assert "not found" in body["errors"][0]["message"].lower()

    def test_trigger_with_version_override(self, authed_client, mock_db):
        """POST /v2/builds/trigger with firmwareVersion stores version in configFlags."""
        mock_db.product.find_unique.return_value = _product_obj()
        build = _build_job()
        mock_db.buildjob.create.return_value = build

        with patch("api.v2.builds.webhook.log_audit"):
            with patch("api.v2.builds.webhook.notify_build_service", create=True):
                response = authed_client.post(
                    "/v2/builds/trigger",
                    data=json.dumps({
                        "productId": "prod-alpha",
                        "repoSlug": "alpha_fw",
                        "branch": "main",
                        "variant": "release",
                        "firmwareVersion": "1.2.3",
                    }),
                )

        assert response.status_code == 201
        call_args = mock_db.buildjob.create.call_args
        create_data = call_args.kwargs["data"]
        assert "configFlags" in create_data

    def test_trigger_unauthorized_returns_401(self, client, mock_db):
        """POST /v2/builds/trigger without auth returns 401."""
        response = client.post(
            "/v2/builds/trigger",
            data=json.dumps({"productId": "p", "repoSlug": "r", "branch": "b"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/builds/events — Repo event
# ---------------------------------------------------------------------------

class TestReceiveRepoEvent:
    """Tests for POST /v2/builds/events."""

    def test_receive_repo_event_success(self, authed_client, mock_db):
        """POST /v2/builds/events with valid payload triggers pipeline stages."""
        with patch("api.v2.builds.webhook.handle_repo_event", return_value=[{"stageId": "s1"}]):
            with patch("api.v2.builds.webhook.log_audit"):
                response = authed_client.post(
                    "/v2/builds/events",
                    data=json.dumps({
                        "repoSlug": "alpha_fw",
                        "branch": "concord-main",
                        "commitSha": "abc1234",
                        "eventType": "push",
                        "source": "poller",
                    }),
                )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["triggered"] == 1

    def test_receive_repo_event_missing_repo_slug_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/events without repoSlug returns 400."""
        response = authed_client.post(
            "/v2/builds/events",
            data=json.dumps({"branch": "main", "eventType": "push"}),
        )
        assert response.status_code == 400

    def test_receive_repo_event_empty_body_returns_400(self, authed_client, mock_db):
        """POST /v2/builds/events with empty body returns 400."""
        response = authed_client.post(
            "/v2/builds/events",
            data=json.dumps({}),
        )
        assert response.status_code == 400

    def test_receive_repo_event_handler_error_returns_500(self, authed_client, mock_db):
        """POST /v2/builds/events returns 500 when handle_repo_event raises."""
        with patch("api.v2.builds.webhook.handle_repo_event", side_effect=Exception("DB error")):
            response = authed_client.post(
                "/v2/builds/events",
                data=json.dumps({"repoSlug": "alpha_fw", "branch": "main"}),
            )
        assert response.status_code == 500

    def test_receive_repo_event_unauthorized_returns_401(self, client, mock_db):
        """POST /v2/builds/events without auth returns 401."""
        response = client.post(
            "/v2/builds/events",
            data=json.dumps({"repoSlug": "alpha_fw", "branch": "main"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401

    # TODO: test_receive_repo_event_merge_type_triggers_merge_handling
    # TODO: test_receive_repo_event_with_metadata_forwarded
