"""Integration test: mock FUOTA flow end-to-end.

Exercises the full call chain across framework modules using stubs:
    StageAssets → FuotaOrchestrator → BuildAsset

Flow: resolve assets → upload CFW → create plan → verify assignment

This catches interface mismatches between modules that unit tests miss.
No hardware, no network — everything in-memory via stubs.
"""

import pytest

from corekinect.errors import (
    CloudError,
    ConfigError,
    TimeoutError as ValidationTimeoutError,
)
from corekinect.test.fuota_orchestrator import FuotaOrchestrator
from corekinect.test.stage_assets import STAGE_REQUIRED_LABELS, StageAssets
from corekinect.test.cfw import parse_cfw_header

from .stubs import StubArtifactResolver, StubFuotaClient


# =============================================================================
# Helpers
# =============================================================================


def _build_fuota_resolver() -> StubArtifactResolver:
    """Create a StubArtifactResolver with all FUOTA-required builds."""
    resolver = StubArtifactResolver()
    resolver.add_build("MFG_BASE", version="0.5.0", variant="mfg", track="BM")
    resolver.add_build("MFG_BUMP", version="0.5.1", variant="mfg", track="BM")
    resolver.add_build("FUT_VERBOSE_A", version="0.5.0", variant="debug", track="BM")
    resolver.add_build("FUT_VERBOSE_B", version="0.5.1", variant="debug", track="BM")
    resolver.add_build("FUT_QUIET_A", version="0.5.0", variant="release", track="BM")
    resolver.add_build("FUT_QUIET_B", version="0.5.1", variant="release", track="BM")
    resolver.add_build("MAIN_BASELINE", version="0.5.0", variant="debug", track="BM")
    resolver.add_build("MAIN_MERGED", version="0.5.0", variant="debug", track="BM")
    return resolver


DEVICE_ID = "70B3D584C01E1FCC"
DEVICE_TYPE_ID = 2
DEVICE_VARIANT_ID = 3


# =============================================================================
# Test: Full FUOTA transition flow
# =============================================================================


class TestFuotaTransitionFlow:
    """End-to-end test: resolve assets → upload → plan → assign → verify."""

    def test_full_mfg_to_mfg_transition(self):
        """Simulate a MFG v0.5.0 → v0.5.1 FUOTA transition."""
        # ── 1. Resolve stage assets ──
        resolver = _build_fuota_resolver()
        assets = StageAssets(resolver, stage="fuota", strict=True)

        assert assets.missing_labels() == []
        assert len(assets.labels) == 8

        # ── 2. Get source and target builds ──
        source = assets.by_label("FUT_VERBOSE_A")
        target = assets.by_label("FUT_VERBOSE_B")

        assert source.version() == "0.5.0"
        assert target.version() == "0.5.1"

        # ── 3. Verify CFW files exist and are parseable ──
        source_cfws = source.cfws()
        target_cfws = target.cfws()
        assert len(source_cfws) == 2  # app + comms
        assert len(target_cfws) == 2

        for cfw_path in target_cfws:
            info = parse_cfw_header(cfw_path)
            assert info["version_string"] == "0.5.1"
            assert info["is_mfg"] is True  # track=BM includes Mfg flag

        # ── 4. Verify target strings for FUOTA plan ──
        target_strings = target.target_strings()
        assert len(target_strings) == 2
        assert "109.0.5.1-BM" in target_strings  # app
        assert "108.0.5.1-BM" in target_strings  # comms

        # ── 5. Upload CFWs via orchestrator ──
        fuota_client = StubFuotaClient()
        fuota_client.set_plan_id(42)
        orchestrator = FuotaOrchestrator(fuota_client)

        orchestrator.upload_transition(source, target)

        upload_events = [
            e for e in fuota_client.events if e["action"] == "upload_cfw"
        ]
        assert len(upload_events) == 4  # 2 source + 2 target

        # ── 6. Create and assign FUOTA plan ──
        plan_id = orchestrator.create_transition_plan(
            device_id=DEVICE_ID,
            source=source,
            target=target,
            description="MFG v0.5.0 → v0.5.1",
            device_type_id=DEVICE_TYPE_ID,
            device_variant_id=DEVICE_VARIANT_ID,
        )
        assert plan_id == 42

        # Verify device was registered
        reg_events = [
            e for e in fuota_client.events
            if e["action"] == "ensure_device_registered"
        ]
        assert len(reg_events) == 1
        assert reg_events[0]["device_id"] == DEVICE_ID

        # Verify plan was created with correct targets
        plan_events = [
            e for e in fuota_client.events if e["action"] == "create_plan"
        ]
        assert len(plan_events) == 1
        plan_targets = plan_events[0]["stages"][0]["targets"]
        assert sorted(plan_targets) == sorted(target_strings)

        # Verify device was assigned
        assign_events = [
            e for e in fuota_client.events if e["action"] == "assign_device"
        ]
        assert len(assign_events) == 1
        assert assign_events[0]["plan_id"] == 42
        assert assign_events[0]["device_ids"] == [DEVICE_ID]

        # ── 7. Cleanup ──
        resolver.cleanup()


class TestStageAssetsToOrchestrator:
    """Test that StageAssets and FuotaOrchestrator integrate cleanly."""

    def test_mfg_hex_files_exist_on_disk(self):
        """MFG hex files should be real files on disk (not just paths)."""
        resolver = _build_fuota_resolver()
        assets = StageAssets(resolver, stage="fuota")

        mfg = assets.mfg()
        app_hex = mfg.hex("app")
        comms_hex = mfg.hex("comms")

        from pathlib import Path
        assert Path(app_hex).exists()
        assert Path(comms_hex).exists()
        assert app_hex != comms_hex

        resolver.cleanup()

    def test_quiet_builds_use_bm_track(self):
        """Quiet CFWs use BM track (same as all Alpha FUOTA builds)."""
        resolver = _build_fuota_resolver()
        assets = StageAssets(resolver, stage="fuota")

        quiet_a = assets.by_label("FUT_QUIET_A")
        cfws = quiet_a.cfws()

        for cfw_path in cfws:
            info = parse_cfw_header(cfw_path)
            # All Alpha FUOTA builds use BM track — no D flag
            assert info["track"] == "B"
            assert info["is_debug"] is False, "D flag must NEVER be set for FUOTA CFWs"

        resolver.cleanup()

    def test_version_strings_match_manifest(self):
        """BuildAsset version_string should match CFW header target_string."""
        resolver = _build_fuota_resolver()
        assets = StageAssets(resolver, stage="fuota")

        target = assets.by_label("FUT_VERBOSE_B")

        # Version string from manifest
        app_version_string = target.version_string("app")

        # Version string from CFW header
        app_cfw = target.cfw("app")
        cfw_info = parse_cfw_header(app_cfw)

        assert app_version_string == cfw_info["target_string"]

        resolver.cleanup()


class TestStageValidation:
    """Test stage-level validation catches problems early."""

    def test_missing_build_blocks_test_start(self):
        """If a required build is missing, StageAssets refuses to construct."""
        resolver = StubArtifactResolver()
        # Only add 7 of 8 required FUOTA builds
        resolver.add_build("MFG_BASE", version="0.5.0", variant="mfg", track="BM")
        resolver.add_build("MFG_BUMP", version="0.5.1", variant="mfg", track="BM")
        resolver.add_build("FUT_VERBOSE_A", version="0.5.0", variant="debug", track="BM")
        resolver.add_build("FUT_VERBOSE_B", version="0.5.1", variant="debug", track="BM")
        resolver.add_build("FUT_QUIET_A", version="0.5.0", variant="release", track="B")
        resolver.add_build("FUT_QUIET_B", version="0.5.1", variant="release", track="B")
        resolver.add_build("MAIN_BASELINE", version="0.5.0", variant="debug", track="BM")
        # Missing: MAIN_MERGED

        with pytest.raises(ConfigError, match="MAIN_MERGED"):
            StageAssets(resolver, stage="fuota", strict=True)

    def test_failed_build_blocks_test_start(self):
        """If a build failed, StageAssets.validate() catches it."""
        resolver = _build_fuota_resolver()
        # Corrupt one build
        resolver._builds["FUT_VERBOSE_B"].status = "FAILED"

        with pytest.raises(ConfigError, match="failed builds"):
            StageAssets(resolver, stage="fuota", strict=True)

    def test_smoke_stage_needs_fewer_builds(self):
        """Smoke stage only needs 2 builds — simpler pipeline."""
        resolver = StubArtifactResolver()
        resolver.add_build("MFG_BASE", version="0.5.0", variant="mfg", track="BM")
        resolver.add_build("APP_DEBUG", version="0.5.0", variant="debug", track="BM")

        assets = StageAssets(resolver, stage="smoke", strict=True)
        assert assets.missing_labels() == []
        assert len(assets.labels) == 2

    def test_cloud_checkin_timeout_is_catchable(self):
        """TimeoutError from orchestrator should be catchable as ValidationTimeoutError."""
        fuota_client = StubFuotaClient()
        fuota_client.set_device_record_id(DEVICE_ID, 0)
        orchestrator = FuotaOrchestrator(fuota_client)

        with pytest.raises(ValidationTimeoutError):
            orchestrator.wait_for_cloud_checkin(
                DEVICE_ID, timeout_s=0.5, poll_interval_s=0.1,
            )
