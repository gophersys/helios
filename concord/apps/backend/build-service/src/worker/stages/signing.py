"""SigningStage — deploys MCUboot encryption/signing keys.

Keys are sourced from:
  1. webhookData.signingKeyValue (base64, from Concord Secrets)
  2. /keys/{product}/*.pem (K8s secret volume mount)
"""

from __future__ import annotations

import base64
import logging
import shutil
from pathlib import Path

from src.worker.pipeline import BuildContext, StageResult

log = logging.getLogger("build-service")


class SigningStage:
    """Deploy signing keys to both repos for MCUboot encryption."""

    name = "signing"

    def execute(self, ctx: BuildContext) -> StageResult:
        """Deploy MCUboot signing keys to both firmware repos.

        Tries two key sources in priority order:
        1. ``webhookData.signingKeyValue`` — base64-encoded key from Concord Secrets.
        2. ``/keys/{product}/*.pem`` — K8s secret volume mount.

        If no key is found, logs a warning and returns success so unsigned
        builds can still proceed (encrypted builds will fail at the build step).

        Args:
            ctx: Mutable build context shared across all pipeline stages.

        Returns:
            StageResult.ok() always — missing keys produce a warning, not a
            hard failure.
        """
        product_base = ctx.job.product.lower().replace("_fw", "").replace("_mfg", "")

        # 1. Try signing key from webhook data (base64-encoded)
        signing_key_b64 = ctx.webhook_data.get("signingKeyValue")
        if signing_key_b64:
            try:
                key_bytes = base64.b64decode(signing_key_b64)
                self._deploy_key_bytes(ctx, key_bytes)
                ctx.signing_key_deployed = True
                log.info("Signing key deployed from Concord Secrets")
                return StageResult.ok()
            except Exception as e:
                log.error("Failed to decode signing key: %s", e)

        # 2. Try K8s-mounted keys at /keys/{product}/
        keys_dir = Path(f"/keys/{product_base}")
        if keys_dir.is_dir():
            for key_file in keys_dir.glob("*.pem"):
                self._deploy_key_file(ctx, key_file)
                ctx.signing_key_deployed = True
                log.info("Signing key from K8s mount: %s", key_file.name)
                return StageResult.ok()

        # No signing key available — warn but don't fail
        log.warning("No signing key configured — encrypted builds will fail. "
                     "Add a signing key in Products → Stage Config → Signing Key")
        return StageResult.ok()

    def _deploy_key_bytes(self, ctx: BuildContext, key_bytes: bytes):
        """Write key bytes to all expected locations in both repos."""
        for target_dir in [ctx.primary_dir, ctx.secondary_dir]:
            if not target_dir or not target_dir.is_dir():
                continue
            for key_name in ["encryption_key.pem", "comms_encryption_key.pem"]:
                dest = target_dir / key_name
                dest.write_bytes(key_bytes)
                dest.chmod(0o600)
            # Also write to comm_coproc_mfg subdirectory
            comms_subdir = target_dir / "comm_coproc_mfg"
            if comms_subdir.is_dir():
                (comms_subdir / "comms_encryption_key.pem").write_bytes(key_bytes)
                (comms_subdir / "comms_encryption_key.pem").chmod(0o600)
            log.info("Signing key deployed to %s", target_dir.name)

    def _deploy_key_file(self, ctx: BuildContext, key_file: Path):
        """Copy a key file to all expected locations in both repos."""
        for target_dir in [ctx.primary_dir, ctx.secondary_dir]:
            if not target_dir or not target_dir.is_dir():
                continue
            for key_name in ["encryption_key.pem", "comms_encryption_key.pem"]:
                shutil.copy2(key_file, target_dir / key_name)
            comms_subdir = target_dir / "comm_coproc_mfg"
            if comms_subdir.is_dir():
                shutil.copy2(key_file, comms_subdir / "comms_encryption_key.pem")
