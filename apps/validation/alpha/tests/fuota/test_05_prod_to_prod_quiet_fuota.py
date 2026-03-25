"""Prod-to-Prod FUOTA (quiet) — upgrade between silent production firmware versions.

Two-phase test:
  SETUP: Flash MFG → FUOTA to PROD_QUIET (establish prod baseline)
  TEST:  FUOTA from PROD_QUIET → PROD_QUIET_BUMP (prod-to-prod upgrade)

No UART verification at all. Cloud check-in is the definitive proof.

# ═══════════════════════════════════════════════════════════════════════
# VERSION MAPPING (update when pipeline seeds change)
# ═══════════════════════════════════════════════════════════════════════
# Label              Version   FW Type     CONFIG_LOG   CFW Flags
# MFG_FLASH          v0.5.21   mfg release  y (default)  BM
# PROD_QUIET         v0.8.22   app release  n (default)  B
# PROD_QUIET_BUMP    v0.8.23   app release  n (default)  B
#
# CORECLOUD WORKAROUND (remove when CoreCloud fixes D-flag stripping)
# ═══════════════════════════════════════════════════════════════════════
# CoreCloud strips 'D' (debug) from FUOTA plan targets.
# All prod builds use release variant (no D flag).
#
# TODO(corecloud-fix): When fixed, consider switching to debug builds.
#
# VERIFICATION STRATEGY
# ═══════════════════════════════════════════════════════════════════════
# Quiet (CONFIG_LOG=n): Neither processor emits UART output.
#   → NO verify_firmware_version steps at all
#   → Boot current check after setup FUOTA proves firmware runs
#   → Cloud check-in (180s, HARD fail) after upgrade is the sole proof

Pipeline builds used:
    MFG_FLASH              → Flashed via J-Link (mfg hex)
    PROD_QUIET             → Setup FUOTA target (production CFW, CONFIG_LOG=n)
    PROD_QUIET_BUMP        → Upgrade FUOTA target (production CFW, CONFIG_LOG=n, bumped)
    triggerData.modemFirmware → Modem baseband firmware (.zip)

Flow:
    ── SETUP PHASE ──
    01. Download all artifacts
    02. Flash MFG via J-Link
    03. Verify boot (current >5mA)
    04. Personalize (EC keygen + key upload)
    05. Cloud check-in (best-effort)
    06. Upload PROD_QUIET CFW
    07. Create MFG→PROD_QUIET plan
    08. FUOTA delivery (setup)
    09. Verify boot after setup FUOTA (current check, no UART)
    ── TEST PHASE ──
    10. Upload PROD_QUIET_BUMP CFW
    11. Create PROD_QUIET→PROD_QUIET_BUMP plan
    12. FUOTA delivery (upgrade)
    13. Post-upgrade cloud check-in (HARD fail — only proof)
    14. Cleanup (disable both FUOTA assignments)
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
    wait_for_cloud_checkin,
    wait_for_fuota_completion,
)

# Pipeline build labels
FLASH_LABEL = "MFG_FLASH"
# TODO(corecloud-fix): When CoreCloud fixes D-flag stripping, consider switching to debug
SETUP_FUOTA_LABEL = "PROD_QUIET"           # Setup: MFG → this
UPGRADE_FUOTA_LABEL = "PROD_QUIET_BUMP"    # Test:  PROD_QUIET → this


@pytest.fixture(autouse=True, scope="class")
def _fuota_cleanup(request, fuota_client):
    """Ensure BOTH FUOTA assignments are cleaned up even if tests fail."""
    yield

    cls = TestProdToProdQuietFuota
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


class TestProdToProdQuietFuota:
    """Prod-to-Prod FUOTA (quiet) — two-phase upgrade, cloud-only verification."""

    # =====================================================================
    # Shared state
    # =====================================================================

    _app_hex: Optional[str] = None
    _comms_hex: Optional[str] = None
    _modem_zip: Optional[str] = None
    _flash_version: Optional[str] = None

    _setup_cfw_paths: List[str] = []
    _setup_target_strings: List[str] = []
    _setup_version: Optional[str] = None
    _setup_plan_id: Optional[int] = None

    _upgrade_cfw_paths: List[str] = []
    _upgrade_target_strings: List[str] = []
    _upgrade_version: Optional[str] = None
    _upgrade_plan_id: Optional[int] = None

    _device_id: Optional[str] = None
    _imei: Optional[str] = None
    _iccids: List[str] = []

    # =====================================================================
    # 01: Download ALL artifacts
    # =====================================================================

    def test_01_download_artifacts(self, pipeline_assets, device_config):
        """Download MFG hex + modem + PROD_QUIET CFW + PROD_QUIET_BUMP CFW."""
        cls = TestProdToProdQuietFuota

        # --- MFG firmware ---
        flash_build = pipeline_assets.get_build(FLASH_LABEL)
        assert flash_build, f"Build '{FLASH_LABEL}' not found"
        assert flash_build.status in ("SUCCESS", "CACHED"), f"{FLASH_LABEL} is {flash_build.status}"
        print(f"{FLASH_LABEL}: v{flash_build.version_string} [{flash_build.status}]")

        app_hex = pipeline_assets.get_hex(FLASH_LABEL, "app")
        assert app_hex and Path(app_hex).exists(), f"{FLASH_LABEL} app hex download failed"
        comms_hex = pipeline_assets.get_hex(FLASH_LABEL, "comms")
        assert comms_hex and Path(comms_hex).exists(), f"{FLASH_LABEL} comms hex download failed"

        cls._app_hex = app_hex
        cls._comms_hex = comms_hex
        cls._flash_version = flash_build.version_string

        # --- Modem firmware ---
        modem_zip = pipeline_assets.get_modem_firmware()
        if modem_zip:
            cls._modem_zip = modem_zip
            print(f"Modem FW:  {Path(modem_zip).name}")
        else:
            print("WARNING: No modem firmware — modem flash will be skipped")

        # --- Setup CFW (PROD_QUIET) ---
        setup_build = pipeline_assets.get_build(SETUP_FUOTA_LABEL)
        assert setup_build, f"Build '{SETUP_FUOTA_LABEL}' not found"
        assert setup_build.status in ("SUCCESS", "CACHED"), f"{SETUP_FUOTA_LABEL} is {setup_build.status}"

        setup_cfws = pipeline_assets.get_cfw_files(SETUP_FUOTA_LABEL)
        assert setup_cfws, f"{SETUP_FUOTA_LABEL} has no CFW files"

        setup_targets = []
        for cfw_path in setup_cfws:
            meta = parse_cfw_header(Path(cfw_path))
            setup_targets.append(meta["target_string"])
            print(f"Setup CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        cls._setup_cfw_paths = setup_cfws
        cls._setup_target_strings = setup_targets
        cls._setup_version = setup_build.version_string

        # --- Upgrade CFW (PROD_QUIET_BUMP) ---
        upgrade_build = pipeline_assets.get_build(UPGRADE_FUOTA_LABEL)
        assert upgrade_build, f"Build '{UPGRADE_FUOTA_LABEL}' not found"
        assert upgrade_build.status in ("SUCCESS", "CACHED"), f"{UPGRADE_FUOTA_LABEL} is {upgrade_build.status}"

        upgrade_cfws = pipeline_assets.get_cfw_files(UPGRADE_FUOTA_LABEL)
        assert upgrade_cfws, f"{UPGRADE_FUOTA_LABEL} has no CFW files"

        upgrade_targets = []
        for cfw_path in upgrade_cfws:
            meta = parse_cfw_header(Path(cfw_path))
            upgrade_targets.append(meta["target_string"])
            print(f"Upgrade CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        cls._upgrade_cfw_paths = upgrade_cfws
        cls._upgrade_target_strings = upgrade_targets
        cls._upgrade_version = upgrade_build.version_string

        print(f"\nPlan: MFG v{flash_build.version_string} -> PROD v{setup_build.version_string} -> PROD v{upgrade_build.version_string}")

    # =====================================================================
    # 02: Flash MFG firmware
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link."""
        cls = TestProdToProdQuietFuota
        assert cls._app_hex and cls._comms_hex

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        print(f"Flashing nRF52840: {Path(cls._app_hex).name}")
        flash_processor(ctx.mtib, cls._app_hex, HostType.HOST_TYPE_NRF52840)

        if cls._modem_zip:
            print(f"Flashing modem: {Path(cls._modem_zip).name}")
            flash_processor(ctx.mtib, cls._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)

        print(f"Flashing nRF9151: {Path(cls._comms_hex).name}")
        flash_processor(ctx.mtib, cls._comms_hex, HostType.HOST_TYPE_NRF9151)

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
        cls = TestProdToProdQuietFuota
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
        cls = TestProdToProdQuietFuota
        assert cls._device_id

        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)
        try:
            record_id = wait_for_cloud_checkin(fuota_client, cls._device_id, timeout_s=120)
            print(f"CoreCloud check-in confirmed (recordId={record_id})")
        except BaseException:
            print("WARNING: Cloud check-in timed out — continuing")

    # ═════════════════════════════════════════════════════════════════════
    # SETUP PHASE: MFG → PROD_QUIET
    # ═════════════════════════════════════════════════════════════════════

    # =====================================================================
    # 06: Upload setup CFW
    # =====================================================================

    def test_06_setup_upload_cfw(self, fuota_client):
        """Upload PROD_QUIET CFW files to CoreCloud."""
        cls = TestProdToProdQuietFuota
        assert cls._setup_cfw_paths

        upload_cfw_files(fuota_client, cls._setup_cfw_paths)
        print(f"{len(cls._setup_cfw_paths)} setup CFW file(s) uploaded")

    # =====================================================================
    # 07: Create setup plan
    # =====================================================================

    def test_07_setup_create_plan(self, fuota_client, device_config):
        """Create MFG → PROD_QUIET FUOTA plan."""
        cls = TestProdToProdQuietFuota
        assert cls._device_id

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"Setup MFG->Prod-Quiet {timestamp}: "
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
        """Wait for setup FUOTA delivery (MFG → PROD_QUIET)."""
        cls = TestProdToProdQuietFuota
        assert cls._device_id and cls._setup_plan_id

        print("Power cycling to trigger setup FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        wait_for_fuota_completion(
            fuota_client,
            device_id=cls._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
        )
        print("Setup FUOTA delivery complete")

    # =====================================================================
    # 09: Verify boot after setup (current check, no UART)
    # =====================================================================

    def test_09_setup_verify_boot(self, ctx):
        """Power cycle and verify DUT boots after setup FUOTA (current check only).

        Quiet firmware has no UART output. Boot current is the only
        hardware-level proof that the setup FUOTA succeeded.
        """
        print("Power cycling to verify post-setup boot...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=10.0)

        avg_current = read_total_current_ma(ctx.mtib, samples=10, interval_s=0.5)
        assert avg_current > 5.0, (
            f"Post-setup DUT not booting: {avg_current:.2f}mA (expected >5mA)"
        )
        print(f"Post-setup DUT booted: avg current = {avg_current:.2f}mA")

    # ═════════════════════════════════════════════════════════════════════
    # TEST PHASE: PROD_QUIET → PROD_QUIET_BUMP
    # ═════════════════════════════════════════════════════════════════════

    # =====================================================================
    # 10: Upload upgrade CFW
    # =====================================================================

    def test_10_upgrade_upload_cfw(self, fuota_client):
        """Upload PROD_QUIET_BUMP CFW files to CoreCloud."""
        cls = TestProdToProdQuietFuota
        assert cls._upgrade_cfw_paths

        upload_cfw_files(fuota_client, cls._upgrade_cfw_paths)
        print(f"{len(cls._upgrade_cfw_paths)} upgrade CFW file(s) uploaded")

    # =====================================================================
    # 11: Create upgrade plan
    # =====================================================================

    def test_11_upgrade_create_plan(self, fuota_client, device_config):
        """Create PROD_QUIET → PROD_QUIET_BUMP FUOTA plan."""
        cls = TestProdToProdQuietFuota
        assert cls._device_id

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"Upgrade Prod-Quiet {timestamp}: "
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
        """Wait for upgrade FUOTA delivery (PROD_QUIET → PROD_QUIET_BUMP)."""
        cls = TestProdToProdQuietFuota
        assert cls._device_id and cls._upgrade_plan_id

        print("Power cycling to trigger upgrade FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        wait_for_fuota_completion(
            fuota_client,
            device_id=cls._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
        )
        print("Upgrade FUOTA delivery complete")

    # =====================================================================
    # 13: Post-upgrade cloud check-in (HARD fail — only proof)
    # =====================================================================

    def test_13_post_upgrade_checkin(self, fuota_client, ctx):
        """Cloud check-in after quiet prod-to-prod upgrade (HARD fail).

        For quiet firmware, this is the ONLY proof that the upgrade worked.
        No UART verification is possible.
        """
        cls = TestProdToProdQuietFuota
        assert cls._device_id

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client, cls._device_id, timeout_s=180,
        )
        print(f"Post-upgrade CoreCloud check-in confirmed (recordId={record_id})")
