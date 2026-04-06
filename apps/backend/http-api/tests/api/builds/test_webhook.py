"""Tests for CI webhook endpoint — verifies error responses use proper ErrorDetail format."""

import hashlib
import hmac
import json
import os
from unittest.mock import patch

from tests.conftest import make_obj


class TestWebhookBitbucket:
    """Tests for POST /v2/builds/webhooks/bitbucket."""

    def test_invalid_signature_returns_proper_error(self, client, mock_db):
        """Verify 401 for invalid HMAC returns proper error envelope, not raw string."""
        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": "test-secret"}):
            response = client.post(
                "/v2/builds/webhooks/bitbucket",
                data=json.dumps({"eventKey": "repo:refs_changed"}),
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature": "sha256=invalid",
                },
            )

        assert response.status_code == 401
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
        assert "signature" in body["errors"][0]["message"].lower()

    def test_missing_secret_returns_proper_error(self, client, mock_db):
        """Verify 401 when BITBUCKET_WEBHOOK_SECRET is not set (fail-closed)."""
        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": ""}):
            response = client.post(
                "/v2/builds/webhooks/bitbucket",
                data=json.dumps({"eventKey": "repo:refs_changed"}),
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature": "sha256=anything",
                },
            )

        assert response.status_code == 401
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]

    def test_valid_signature_with_bad_payload_returns_400(self, client, mock_db):
        """Verify valid HMAC but invalid payload returns 400 with proper error format."""
        secret = "test-webhook-secret"
        payload = json.dumps({"invalid": "payload"}).encode()
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        with patch.dict(os.environ, {"BITBUCKET_WEBHOOK_SECRET": secret}):
            response = client.post(
                "/v2/builds/webhooks/bitbucket",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature": f"sha256={sig}",
                },
            )

        assert response.status_code == 400
        body = json.loads(response.data)
        assert body["data"] is None
        assert len(body["errors"]) > 0
        assert isinstance(body["errors"][0], dict)
        assert "message" in body["errors"][0]
