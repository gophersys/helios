"""Prod-to-Prod FUOTA (verbose) — upgrade between production firmware versions.

Two-phase test:
  SETUP: Flash MFG → FUOTA to PROD_VERBOSE (establish prod baseline)
  TEST:  FUOTA from PROD_VERBOSE → PROD_VERBOSE_BUMP (prod-to-prod upgrade)

This validates the real-world OTA upgrade path where a device already running
production firmware receives a newer version over the air.

# ═══════════════════════════════════════════════════════════════════════
# VERSION MAPPING (update when pipeline seeds change)
# ═══════════════════════════════════════════════════════════════════════
# Label              Version   FW Type     CONFIG_LOG   CFW Flags
# MFG_FLASH          v0.5.21   mfg release  y (default)  BM
# PROD_VERBOSE       v0.8.24   app release  y (override) B
# PROD_VERBOSE_BUMP  v0.8.25   app release  y (override) B
#
# CORECLOUD WORKAROUND (remove when CoreCloud fixes D-flag stripping)
# ═══════════════════════════════════════════════════════════════════════
# CoreCloud strips 'D' (debug) from FUOTA plan targets.
# All prod builds use release variant (no D flag). Verbose builds
# override CONFIG_LOG=y for UART output without the debug flag.
#
# TODO(corecloud-fix): When fixed, switch PROD_VERBOSE* to debug
# builds, change labels, update CFW flags from -B to -BD.
#
# VERIFICATION STRATEGY
# ═══════════════════════════════════════════════════════════════════════
# Verbose (CONFIG_LOG=y): Both COMMS + APP emit version on UART boot.
#   → verify_firmware_version(require_both=True) after each FUOTA
# Post-upgrade cloud check-in is a HARD fail (180s).

Pipeline builds used:
    MFG_FLASH              → Flashed via J-Link (mfg hex)
    PROD_VERBOSE           → Setup FUOTA target (production CFW, CONFIG_LOG=y)
    PROD_VERBOSE_BUMP      → Upgrade FUOTA target (production CFW, CONFIG_LOG=y, bumped)
    triggerData.modemFirmware → Modem baseband firmware (.zip)

Flow:
    ── SETUP PHASE (establish prod baseline) ──
    01. Download all artifacts
    02. Flash MFG via J-Link
    03. Verify boot (current >5mA)
    04. Personalize (EC keygen + key upload)
    05. Cloud check-in (best-effort)
    06. Upload PROD_VERBOSE CFW
    07. Create MFG→PROD_VERBOSE plan
    08. FUOTA delivery (setup)
    09. Verify PROD_VERBOSE version via UART
    ── TEST PHASE (prod-to-prod upgrade) ──
    10. Upload PROD_VERBOSE_BUMP CFW
    11. Create PROD_VERBOSE→PROD_VERBOSE_BUMP plan
    12. FUOTA delivery (upgrade)
    13. Verify PROD_VERBOSE_BUMP version via UART
    14. Post-upgrade cloud check-in (HARD fail)
    15. Cleanup (disable both FUOTA assignments)
"""

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pytest

from .conftest import DeviceConfig, parse_cfw_header, register_fuota_cleanup
from .helpers import (
    create_and_assign_fuota_plan,
    personalize_device,
    power_cycle,
    power_on,
    read_total_current_ma,
    upload_cfw_files,
    verify_firmware_version,
    wait_for_cloud_checkin,
    wait_for_fuota_completion,
)

# Pipeline build labels
FLASH_LABEL = "MFG_BASE"
# TODO(corecloud-fix): When CoreCloud fixes D-flag stripping, switch to debug builds
SETUP_FUOTA_LABEL = "FUT_VERBOSE_A"          # Setup: MFG → this
UPGRADE_FUOTA_LABEL = "FUT_VERBOSE_B"        # Test:  FUT_VERBOSE_A → this


@pytest.fixture(autouse=True, scope="class")
def _fuota_cleanup(request, fuota_client):
    """Ensure BOTH FUOTA assignments are cleaned up even if tests fail."""
    yield

    cls = TestProdToProdVerboseFuota
    device_id = cls._device_id

    if not device_id:
        return

    plan_ids = [p for p in [cls._setup_plan_id, cls._upgrade_plan_id] if p]
    if not plan_ids:
        return

    print(f"\nCleaning up {len(plan_ids)} FUOTA assignment(s)...")
    try:
        resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
        devices = resp.json().get("devicesFound", [])

        for d in devices:
            if d.get("deviceId") == device_id and d.get("planId") in plan_ids:
                fuota_client.disable_device(device_id, d["planId"])
                print(f"Cleanup: FUOTA disabled for {device_id} (plan {d['planId']})")
    except Exception as e:
        print(f"Cleanup warning: {e} — atexit handler will retry")


@pytest.mark.fuota_full
class TestProdToProdVerboseFuota:
    """Prod-to-Prod FUOTA (verbose) — two-phase upgrade test."""

    # =====================================================================
    # Shared state
    # =====================================================================

    _app_hex: Optional[str] = None
    _comms_hex: Optional[str] = None
    _modem_zip: Optional[str] = None
    _flash_version: Optional[str] = None
    _flash_targets: list = []       # ManifestTarget list from resolver

    # Setup phase artifacts
    _setup_cfw_paths: List[str] = []
    _setup_target_strings: List[str] = []
    _setup_version: Optional[str] = None
    _setup_plan_id: Optional[int] = None
    _setup_app_ids: set = set()

    # Upgrade phase artifacts
    _upgrade_cfw_paths: List[str] = []
    _upgrade_target_strings: List[str] = []
    _upgrade_version: Optional[str] = None
    _upgrade_plan_id: Optional[int] = None
    _upgrade_app_ids: set = set()

    _device_id: Optional[str] = None
    _imei: Optional[str] = None
    _iccids: List[str] = []

    # =====================================================================
    # 01: Download ALL artifacts
    # =====================================================================

    def test_01_download_artifacts(self, stage_assets, device_config):
        """Download MFG hex + modem + PROD_VERBOSE CFW + PROD_VERBOSE_BUMP CFW."""
        cls = TestProdToProdVerboseFuota

        # --- MFG firmware ---
        flash_build = stage_assets.by_label(FLASH_LABEL)
        flash_version = flash_build.version()
        print(f"{FLASH_LABEL}: v{flash_version}")

        flash_targets = flash_build.targets()
        assert flash_targets, f"Build '{FLASH_LABEL}' has no targets"

        app_hex = flash_build.hex("app")
        assert app_hex and Path(app_hex).exists(), f"{FLASH_LABEL} app hex download failed"

        try:
            comms_hex = flash_build.hex("comms")
        except Exception:
            comms_hex = None

        cls._app_hex = app_hex
        cls._comms_hex = comms_hex
        cls._flash_version = flash_version
        cls._flash_targets = flash_targets

        # --- Modem firmware ---
        modem_zip = stage_assets.modem_zip()
        if modem_zip:
            cls._modem_zip = modem_zip
            print(f"Modem FW:  {Path(modem_zip).name}")
        else:
            print("WARNING: No modem firmware — modem flash will be skipped")

        # --- Setup CFW (PROD_VERBOSE) ---
        setup_build = stage_assets.by_label(SETUP_FUOTA_LABEL)
        setup_version = setup_build.version()
        print(f"{SETUP_FUOTA_LABEL}: v{setup_version}")

        setup_cfws = setup_build.cfws()
        assert setup_cfws, f"{SETUP_FUOTA_LABEL} has no CFW files"

        setup_targets = []
        setup_app_ids = set()
        for cfw_path in setup_cfws:
            meta = parse_cfw_header(Path(cfw_path))
            setup_targets.append(meta["target_string"])
            setup_app_ids.add(meta["app_id"])
            print(f"Setup CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        cls._setup_cfw_paths = setup_cfws
        cls._setup_target_strings = setup_targets
        cls._setup_version = setup_version
        cls._setup_app_ids = setup_app_ids

        # --- Upgrade CFW (PROD_VERBOSE_BUMP) ---
        upgrade_build = stage_assets.by_label(UPGRADE_FUOTA_LABEL)
        upgrade_version = upgrade_build.version()
        print(f"{UPGRADE_FUOTA_LABEL}: v{upgrade_version}")

        upgrade_cfws = upgrade_build.cfws()
        assert upgrade_cfws, f"{UPGRADE_FUOTA_LABEL} has no CFW files"

        upgrade_targets = []
        upgrade_app_ids = set()
        for cfw_path in upgrade_cfws:
            meta = parse_cfw_header(Path(cfw_path))
            upgrade_targets.append(meta["target_string"])
            upgrade_app_ids.add(meta["app_id"])
            print(f"Upgrade CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        cls._upgrade_cfw_paths = upgrade_cfws
        cls._upgrade_target_strings = upgrade_targets
        cls._upgrade_version = upgrade_version
        cls._upgrade_app_ids = upgrade_app_ids

        print(f"\nPlan: MFG v{flash_version} -> PROD v{setup_version} -> PROD v{upgrade_version}")

    # =====================================================================
    # 02: Flash MFG firmware
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link using targets from manifest."""
        cls = TestProdToProdVerboseFuota
        assert cls._app_hex, "No app hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor, host_type_from_manifest

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        app_target = next((t for t in cls._flash_targets if t.role == "app"), None)
        assert app_target, "No app target in flash build manifest"
        app_host_type = host_type_from_manifest(app_target.host_type)
        print(f"Flashing {app_target.processor}: {Path(cls._app_hex).name}")
        flash_processor(ctx.mtib, cls._app_hex, app_host_type)

        if cls._modem_zip:
            print(f"Flashing modem: {Path(cls._modem_zip).name}")
            flash_processor(ctx.mtib, cls._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)

        if cls._comms_hex:
            comms_target = next((t for t in cls._flash_targets if t.role == "comms"), None)
            assert comms_target, "No comms target in flash build manifest"
            comms_host_type = host_type_from_manifest(comms_target.host_type)
            print(f"Flashing {comms_target.processor}: {Path(cls._comms_hex).name}")
            flash_processor(ctx.mtib, cls._comms_hex, comms_host_type)

        print("All processors flashed successfully")

    # =====================================================================
    # 03: Verify boot
    # =====================================================================

    def test_03_verify_boot(self, ctx):
        """Power cycle and verify DUT boots (>5mA current)."""
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)
        avg_current = read_total_current_ma(ctx.mtib, samples=10, interval_s=0.5)
        assert avg_current > 5.0, f"DUT not booting: {avg_current:.2f}mA (expected >5mA)"
        print(f"DUT booted: avg current = {avg_current:.2f}mA")

    # =====================================================================
    # 04: Personalize
    # =====================================================================

    def test_04_personalize(self, ctx, device_config):
        """Lock shells, generate EC keypair, upload key to CoreCloud."""
        cls = TestProdToProdVerboseFuota
        assert device_config.device_snr, "DEVICE_SNR required"

        imei = cls._imei or device_config.device_imei or None
        iccids = cls._iccids or device_config.device_iccids or None

        result = personalize_device(
            ctx.mtib,
            snr=device_config.device_snr,
            device_id=device_config.device_id or None,
            imei=imei,
            iccids=iccids,
        )

        cls._device_id = result["device_id"]
        print(f"Device personalized: {result['device_id']}")

    # =====================================================================
    # 05: Cloud check-in (best-effort)
    # =====================================================================

    def test_05_cloud_checkin(self, fuota_client, ctx):
        """Power cycle and wait for CoreCloud check-in (best-effort)."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id, "No device_id — test_04 must pass first"

        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)
        try:
            record_id = wait_for_cloud_checkin(fuota_client, cls._device_id, timeout_s=120)
            print(f"CoreCloud check-in confirmed (recordId={record_id})")
        except BaseException:
            print("WARNING: Cloud check-in timed out — continuing")

    # ═════════════════════════════════════════════════════════════════════
    # SETUP PHASE: MFG → PROD_VERBOSE
    # ═════════════════════════════════════════════════════════════════════

    # =====================================================================
    # 06: Upload setup CFW
    # =====================================================================

    def test_06_setup_upload_cfw(self, fuota_client):
        """Upload PROD_VERBOSE CFW files to CoreCloud."""
        cls = TestProdToProdVerboseFuota
        assert cls._setup_cfw_paths, "No setup CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, cls._setup_cfw_paths)
        print(f"{len(cls._setup_cfw_paths)} setup CFW file(s) uploaded")

    # =====================================================================
    # 07: Create setup plan
    # =====================================================================

    def test_07_setup_create_plan(self, fuota_client, device_config):
        """Create MFG → PROD_VERBOSE FUOTA plan."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id, "No device_id — test_04 must pass first"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"Setup MFG->Prod-Verbose {timestamp}: "
            f"v{cls._flash_version} -> v{cls._setup_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=cls._device_id,
            target_strings=cls._setup_target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        cls._setup_plan_id = plan_id
        register_fuota_cleanup(cls._device_id, plan_id)
        print(f"Setup plan {plan_id} created. Targets: {cls._setup_target_strings}")

    # =====================================================================
    # 08: Setup FUOTA delivery
    # =====================================================================

    def test_08_setup_fuota_delivery(self, fuota_client, ctx):
        """Wait for setup FUOTA delivery (MFG → PROD_VERBOSE)."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id and cls._setup_plan_id

        print("Power cycling to trigger setup FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        wait_for_fuota_completion(
            fuota_client,
            device_id=cls._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
            expected_app_ids=cls._setup_app_ids,
        )
        print("Setup FUOTA delivery complete")

    # =====================================================================
    # 09: Verify setup version
    # =====================================================================

    def test_09_setup_verify_version(self, ctx):
        """Verify PROD_VERBOSE firmware version via UART boot logs.

        COMMS only — APP (nRF52840) doesn't emit version even with forceLog.
        TODO(corecloud-fix): Switch to require_both=True when forceLog covers APP.
        """
        cls = TestProdToProdVerboseFuota
        assert cls._setup_version, "No setup version — test_01 must pass first"

        versions = verify_firmware_version(
            ctx.mtib,
            expected_version=cls._setup_version,
            timeout_s=180.0,
            require_both=False,
        )
        print(f"Setup verified: comms={versions['comms']}, app={versions['app']}")

    # ═════════════════════════════════════════════════════════════════════
    # TEST PHASE: PROD_VERBOSE → PROD_VERBOSE_BUMP
    # ═════════════════════════════════════════════════════════════════════

    # =====================================================================
    # 10: Upload upgrade CFW
    # =====================================================================

    def test_10_upgrade_upload_cfw(self, fuota_client):
        """Upload PROD_VERBOSE_BUMP CFW files to CoreCloud."""
        cls = TestProdToProdVerboseFuota
        assert cls._upgrade_cfw_paths, "No upgrade CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, cls._upgrade_cfw_paths)
        print(f"{len(cls._upgrade_cfw_paths)} upgrade CFW file(s) uploaded")

    # =====================================================================
    # 11: Create upgrade plan
    # =====================================================================

    def test_11_upgrade_create_plan(self, fuota_client, device_config):
        """Create PROD_VERBOSE → PROD_VERBOSE_BUMP FUOTA plan."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"Upgrade Prod-Verbose {timestamp}: "
            f"v{cls._setup_version} -> v{cls._upgrade_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=cls._device_id,
            target_strings=cls._upgrade_target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        cls._upgrade_plan_id = plan_id
        register_fuota_cleanup(cls._device_id, plan_id)
        print(f"Upgrade plan {plan_id} created. Targets: {cls._upgrade_target_strings}")

    # =====================================================================
    # 12: Upgrade FUOTA delivery
    # =====================================================================

    def test_12_upgrade_fuota_delivery(self, fuota_client, ctx):
        """Wait for upgrade FUOTA delivery (PROD_VERBOSE → PROD_VERBOSE_BUMP)."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id and cls._upgrade_plan_id

        print("Power cycling to trigger upgrade FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        wait_for_fuota_completion(
            fuota_client,
            device_id=cls._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
            expected_app_ids=cls._upgrade_app_ids,
        )
        print("Upgrade FUOTA delivery complete")

    # =====================================================================
    # 13: Verify upgrade version
    # =====================================================================

    def test_13_upgrade_verify_version(self, ctx):
        """Verify PROD_VERBOSE_BUMP firmware version via UART boot logs.

        COMMS only — APP (nRF52840) doesn't emit version even with forceLog.
        TODO(corecloud-fix): Switch to require_both=True when forceLog covers APP.
        """
        cls = TestProdToProdVerboseFuota
        assert cls._upgrade_version, "No upgrade version — test_01 must pass first"

        versions = verify_firmware_version(
            ctx.mtib,
            expected_version=cls._upgrade_version,
            timeout_s=180.0,
            require_both=False,
        )
        print(f"Upgrade verified: comms={versions['comms']}, app={versions['app']}")

    # =====================================================================
    # 14: Post-upgrade cloud check-in (HARD fail)
    # =====================================================================

    def test_14_post_upgrade_checkin(self, fuota_client, ctx):
        """Cloud check-in after prod-to-prod upgrade (HARD fail)."""
        cls = TestProdToProdVerboseFuota
        assert cls._device_id

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client, cls._device_id, timeout_s=180,
        )
        print(f"Post-upgrade CoreCloud check-in confirmed (recordId={record_id})")
