"""Tests for SigningStage — encryption key deployment."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from src.worker.pipeline import BuildContext
from src.worker.stages.signing import SigningStage


@pytest.fixture
def signing_stage():
    return SigningStage()


@pytest.fixture
def ctx(tmp_path, sample_job, config, mock_api_client):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    output_dir = work_dir / "artifacts"
    output_dir.mkdir()

    primary_dir = work_dir / "alpha_fw"
    primary_dir.mkdir()
    secondary_dir = work_dir / "alpha_mfg_fw"
    secondary_dir.mkdir()

    return BuildContext(
        job=sample_job,
        config=config,
        client=mock_api_client,
        work_dir=work_dir,
        output_dir=output_dir,
        primary_dir=primary_dir,
        secondary_dir=secondary_dir,
    )


class TestWebhookKey:
    """Test signing key from webhookData (base64)."""

    def test_deploys_from_webhook_data(self, ctx, signing_stage):
        """Key from webhookData.signingKeyValue is deployed to both repos."""
        key_content = b"-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----"
        ctx.webhook_data = {"signingKeyValue": base64.b64encode(key_content).decode()}

        result = signing_stage.execute(ctx)

        assert result.success
        assert ctx.signing_key_deployed
        assert (ctx.primary_dir / "encryption_key.pem").read_bytes() == key_content
        assert (ctx.secondary_dir / "encryption_key.pem").read_bytes() == key_content
        assert (ctx.primary_dir / "comms_encryption_key.pem").read_bytes() == key_content

    def test_deploys_to_comm_coproc_subdir(self, ctx, signing_stage):
        """Key is also deployed to comm_coproc_mfg subdirectory."""
        key_content = b"test-key-data"
        ctx.webhook_data = {"signingKeyValue": base64.b64encode(key_content).decode()}
        comms_dir = ctx.primary_dir / "comm_coproc_mfg"
        comms_dir.mkdir()

        signing_stage.execute(ctx)

        assert (comms_dir / "comms_encryption_key.pem").read_bytes() == key_content

    def test_invalid_base64_does_not_crash(self, ctx, signing_stage):
        """Invalid base64 in webhook data doesn't crash the stage."""
        ctx.webhook_data = {"signingKeyValue": "not-valid-b64!!!"}

        result = signing_stage.execute(ctx)

        # Stage still succeeds (warns but continues)
        assert result.success
        assert not ctx.signing_key_deployed


class TestK8sMountKey:
    """Test signing key from K8s volume mount."""

    def test_deploys_from_k8s_mount(self, ctx, signing_stage, tmp_path):
        """Key from /keys/{product}/*.pem is deployed."""
        keys_dir = tmp_path / "keys_alpha"
        keys_dir.mkdir()
        (keys_dir / "signing.pem").write_text("k8s-key-content")

        with patch("src.worker.stages.signing.Path") as MockPath:
            # Make Path("/keys/alpha") return our temp dir
            def path_factory(p):
                if p == "/keys/alpha":
                    return keys_dir
                return Path(p)
            MockPath.side_effect = path_factory

            result = signing_stage.execute(ctx)

        assert result.success
        assert ctx.signing_key_deployed


class TestNoKey:
    """Test behavior when no signing key is available."""

    def test_no_key_is_warning_not_failure(self, ctx, signing_stage):
        """Missing signing key is a warning, not a failure."""
        ctx.webhook_data = {}

        result = signing_stage.execute(ctx)

        assert result.success
        assert not ctx.signing_key_deployed
