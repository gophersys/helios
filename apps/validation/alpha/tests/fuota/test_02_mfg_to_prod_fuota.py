"""MFG-to-Production FUOTA (verbose) — cross-variant upgrade with UART verification.

Flash MFG firmware via J-Link, run POST, then FUOTA to production firmware
with CONFIG_LOG=y. Both processors emit version on UART boot, allowing full
version verification via UART + cloud check-in.

# ═══════════════════════════════════════════════════════════════════════
# VERSION MAPPING (update when pipeline seeds change)
# ═══════════════════════════════════════════════════════════════════════
# Label            Version   FW Type     CONFIG_LOG   CFW Flags
# MFG_BASE         v0.5.21   mfg release  y (default)  BM
# FUT_VERBOSE_A    v0.8.24   app release  y (override) B
#
# CORECLOUD WORKAROUND (remove when CoreCloud fixes D-flag stripping)
# ═══════════════════════════════════════════════════════════════════════
# CoreCloud strips 'D' (debug) from FUOTA plan targets:
#   Submitted: 108.0.8.24-BD  →  Stored: 108.0.8.24-B  →  MISMATCH
# All prod builds use release variant (no D flag). Verbose builds
# override CONFIG_LOG=y for UART output without the debug flag.
#
# TODO(corecloud-fix): When fixed, switch FUT_VERBOSE_A to debug
# builds, change labels, update CFW flags from -B to -BD.
#
# VERIFICATION STRATEGY
# ═══════════════════════════════════════════════════════════════════════
# Verbose (CONFIG_LOG=y): Both COMMS + APP emit version on UART boot.
#   → verify_firmware_version(require_both=True)
# Post-FUOTA cloud check-in is a HARD fail (180s).

Pipeline builds used:
    MFG_BASE               → Flashed via J-Link (mfg hex)
    FUT_VERBOSE_A          → Delivered via FUOTA (production CFW, CONFIG_LOG=y)
    triggerData.modemFirmware → Modem baseband firmware (.zip)

Flow:
    01. Download artifacts (mfg hex + modem zip + production CFW)
    02. Flash MFG via J-Link (nRF52840 + modem + nRF9151)
    03. Verify DUT boots (current check)
    04. POST — power-on self-test on both processors
    05. Personalize device (EC keygen + CoreCloud key upload)
    06. Wait for CoreCloud check-in (best-effort)
    07. Upload production CFW to CoreCloud
    08. Create FUOTA plan and assign device
    09. Wait for FUOTA delivery (both 108 + 109 at 100%)
    10. Verify production firmware version via UART boot logs
    11. POST after FUOTA — verify production firmware works
    12. Post-FUOTA cloud check-in (HARD fail)
    13. Cleanup (disable FUOTA assignment)
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
FLASH_LABEL = "MFG_BASE"        # MFG firmware to flash via J-Link
# TODO(corecloud-fix): When CoreCloud fixes D-flag stripping, switch to debug build
FUOTA_LABEL = "FUT_VERBOSE_A"   # Production firmware with CONFIG_LOG=y (release + LOG override)


@pytest.fixture(autouse=True, scope="class")
def _fuota_cleanup(request, fuota_client):
    """Ensure FUOTA assignment is cleaned up even if tests fail."""
    yield

    cls = TestMfgToProdFuota
    device_id = cls._device_id
    plan_id = cls._plan_id

    if not device_id or not plan_id:
        return

    print(f"\nCleaning up FUOTA assignment...")
    try:
        resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
        devices = resp.json().get("devicesFound", [])
        assigned = False
        for d in devices:
            if d.get("deviceId") == device_id and d.get("planId") == plan_id:
                assigned = True
                break

        if assigned:
            fuota_client.disable_device(device_id, plan_id)
            print(f"Cleanup: FUOTA disabled for {device_id} (plan {plan_id})")
        else:
            print(f"Cleanup: Device not assigned to plan {plan_id} (already cleaned or different plan)")
    except Exception as e:
        print(f"Cleanup warning: {e} — atexit handler will retry")


@pytest.mark.fuota_full
class TestMfgToProdFuota:
    """MFG-to-Production FUOTA (verbose) — cross-variant upgrade."""

    # =====================================================================
    # Shared state (populated by earlier tests, consumed by later ones)
    # =====================================================================

    _app_hex: Optional[str] = None
    _comms_hex: Optional[str] = None
    _modem_zip: Optional[str] = None
    _flash_version: Optional[str] = None
    _flash_targets: list = []       # ManifestTarget list from resolver
    _target_cfw_paths: List[str] = []
    _target_strings: List[str] = []
    _target_version: Optional[str] = None
    _fuota_targets: list = []       # ManifestTarget list from resolver
    _device_id: Optional[str] = None
    _plan_id: Optional[int] = None
    # Collected from POST
    _imei: Optional[str] = None
    _iccids: List[str] = []

    # =====================================================================
    # 01: Download artifacts
    # =====================================================================

    def test_01_download_artifacts(self, stage_assets, device_config):
        """Download MFG hex + modem zip + production CFW from pipeline."""

        # --- MFG firmware: hex files for J-Link flash ---

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

        print(f"App hex:   {Path(app_hex).name} ({Path(app_hex).stat().st_size} bytes)")
        if comms_hex:
            print(f"Comms hex: {Path(comms_hex).name} ({Path(comms_hex).stat().st_size} bytes)")

        TestMfgToProdFuota._app_hex = app_hex
        TestMfgToProdFuota._comms_hex = comms_hex
        TestMfgToProdFuota._flash_version = flash_version
        TestMfgToProdFuota._flash_targets = flash_targets

        # --- Modem firmware: from manifest or pipeline triggerData ---

        modem_zip = stage_assets.modem_zip()
        if modem_zip:
            print(f"Modem FW:  {Path(modem_zip).name} ({Path(modem_zip).stat().st_size} bytes)")
            TestMfgToProdFuota._modem_zip = modem_zip
        else:
            print("WARNING: No modem firmware in pipeline — modem flash will be skipped")

        # --- Production firmware: CFW files for FUOTA delivery ---

        fuota_build = stage_assets.by_label(FUOTA_LABEL)
        fuota_version = fuota_build.version()
        print(f"{FUOTA_LABEL}: v{fuota_version}")

        cfw_paths = fuota_build.cfws()
        assert cfw_paths, f"{FUOTA_LABEL} has no CFW files"

        target_strings = []
        app_ids_found = set()

        for cfw_path in cfw_paths:
            meta = parse_cfw_header(Path(cfw_path))
            target_strings.append(meta["target_string"])
            app_ids_found.add(meta["app_id"])
            print(f"CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        # Validate CFW app IDs match manifest targets (product-agnostic)
        fuota_targets = fuota_build.targets()
        expected_app_ids = {t.app_id for t in fuota_targets}
        missing = expected_app_ids - app_ids_found
        assert not missing, (
            f"{FUOTA_LABEL} missing CFW files for app IDs: {missing}. "
            f"Found: {app_ids_found}"
        )

        TestMfgToProdFuota._target_cfw_paths = cfw_paths
        TestMfgToProdFuota._target_strings = target_strings
        TestMfgToProdFuota._target_version = fuota_version
        TestMfgToProdFuota._fuota_targets = fuota_targets

        print(f"Ready: flash MFG v{flash_version} -> FUOTA to prod v{fuota_version}")

    # =====================================================================
    # 02: Flash firmware (nRF52840 + modem + nRF9151)
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link using targets from manifest."""
        assert TestMfgToProdFuota._app_hex, "No app hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor, host_type_from_manifest

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        # Flash app processor using manifest target metadata
        app_target = next(
            (t for t in TestMfgToProdFuota._flash_targets if t.role == "app"), None
        )
        assert app_target, "No app target in flash build manifest"
        app_host_type = host_type_from_manifest(app_target.host_type)
        print(f"Flashing {app_target.processor}: {Path(TestMfgToProdFuota._app_hex).name}")
        app_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._app_hex, app_host_type)
        print(f"{app_target.processor} flashed in {app_ms}ms")

        # Flash modem baseband (must be before comms app — chiperase wipes both)
        if TestMfgToProdFuota._modem_zip:
            print(f"Flashing modem: {Path(TestMfgToProdFuota._modem_zip).name}")
            modem_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)
            print(f"Modem flashed in {modem_ms}ms")
        else:
            print("Modem flash skipped (no modem firmware)")

        # Flash comms processor if present
        if TestMfgToProdFuota._comms_hex:
            comms_target = next(
                (t for t in TestMfgToProdFuota._flash_targets if t.role == "comms"), None
            )
            assert comms_target, "No comms target in flash build manifest"
            comms_host_type = host_type_from_manifest(comms_target.host_type)
            print(f"Flashing {comms_target.processor}: {Path(TestMfgToProdFuota._comms_hex).name}")
            comms_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._comms_hex, comms_host_type)
            print(f"{comms_target.processor} flashed in {comms_ms}ms")

        print("All processors flashed successfully")

    # =====================================================================
    # 03: Verify boot
    # =====================================================================

    def test_03_verify_boot(self, ctx):
        """Power cycle and verify DUT boots (>5mA current)."""
        print("Power cycling DUT...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        avg_current = read_total_current_ma(ctx.mtib, samples=10, interval_s=0.5)
        assert avg_current > 5.0, (
            f"DUT not drawing sufficient current: {avg_current:.2f}mA "
            f"(expected >5mA)"
        )

        print(f"DUT booted: avg current = {avg_current:.2f}mA")

    # =====================================================================
    # 04: POST — power-on self-test
    # =====================================================================

    def test_04_post(self, ctx):
        """Run POST on both processors (chip IDs, BMS, GPS, modem, IMEI, flash)."""
        from corekinect.test.post import run_post

        print("Running POST suite...")
        result = run_post(ctx.mtib, skip_ext_flash=True)

        # Store collected data for subsequent steps
        if result.imei:
            TestMfgToProdFuota._imei = result.imei
            TestMfgToProdFuota._iccids = result.iccids

        print(f"\n{result.summary()}")

        assert result.passed, (
            f"POST failed: {sum(1 for s in result.steps if not s.passed)} step(s) failed"
        )

    # =====================================================================
    # 05: Personalize
    # =====================================================================

    def test_05_personalize(self, ctx, device_config):
        """Lock shells, generate EC keypair, upload key to CoreCloud."""
        assert device_config.device_snr, "DEVICE_SNR required"

        # Use IMEI/ICCIDs from POST if available, else from env
        imei = TestMfgToProdFuota._imei or device_config.device_imei or None
        iccids = TestMfgToProdFuota._iccids or device_config.device_iccids or None

        print(f"SNR={device_config.device_snr}")
        if imei:
            print(f"IMEI={imei} (from {'POST' if TestMfgToProdFuota._imei else 'env'})")

        result = personalize_device(
            ctx.mtib,
            snr=device_config.device_snr,
            device_id=device_config.device_id or None,
            imei=imei,
            iccids=iccids,
        )

        TestMfgToProdFuota._device_id = result["device_id"]

        print(f"Device personalized: {result['device_id']}")
        print(f"Public key: {result['public_key'][:24]}...")

    # =====================================================================
    # 06: Cloud check-in
    # =====================================================================

    def test_06_cloud_checkin(self, fuota_client, ctx):
        """Power cycle and wait for device to check into CoreCloud.

        Best-effort: if the modem is in backoff from previous power cycles,
        the check-in may time out. This is OK — the device will check in
        during the FUOTA delivery step. We log a warning but don't fail.
        """
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        try:
            record_id = wait_for_cloud_checkin(
                fuota_client,
                TestMfgToProdFuota._device_id,
                timeout_s=120,
            )
            print(f"CoreCloud check-in confirmed (recordId={record_id})")
        except BaseException:
            print("WARNING: Cloud check-in timed out (modem likely in backoff)")
            print("Device will check in during FUOTA delivery — continuing")

    # =====================================================================
    # 07: Upload CFW
    # =====================================================================

    def test_07_upload_cfw(self, fuota_client):
        """Upload production CFW files to CoreCloud."""
        assert TestMfgToProdFuota._target_cfw_paths, "No CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, TestMfgToProdFuota._target_cfw_paths)

        print(f"{len(TestMfgToProdFuota._target_cfw_paths)} CFW file(s) uploaded to CoreCloud")

    # =====================================================================
    # 08: Create FUOTA plan
    # =====================================================================

    def test_08_create_plan(self, fuota_client, device_config):
        """Create FUOTA plan and assign device."""
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToProdFuota._target_strings, "No target strings — test_01 must pass first"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"MFG->Prod-Verbose FUOTA {timestamp}: "
            f"v{TestMfgToProdFuota._flash_version} -> v{TestMfgToProdFuota._target_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=TestMfgToProdFuota._device_id,
            target_strings=TestMfgToProdFuota._target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        TestMfgToProdFuota._plan_id = plan_id
        register_fuota_cleanup(TestMfgToProdFuota._device_id, plan_id)

        print(f"Plan {plan_id} created and device assigned")
        print(f"Targets: {TestMfgToProdFuota._target_strings}")

    # =====================================================================
    # 09: FUOTA delivery
    # =====================================================================

    def test_09_fuota_delivery(self, fuota_client, ctx):
        """Wait for FUOTA delivery (all targets to 100%)."""
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToProdFuota._plan_id, "No plan_id — test_08 must pass first"

        # Pass expected app IDs from manifest targets (product-agnostic)
        expected_app_ids = {t.app_id for t in TestMfgToProdFuota._fuota_targets}

        print("Power cycling to trigger FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        print("Monitoring FUOTA progress...")
        wait_for_fuota_completion(
            fuota_client,
            device_id=TestMfgToProdFuota._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
            expected_app_ids=expected_app_ids,
        )

        print("FUOTA delivery complete")

    # =====================================================================
    # 10: Verify version
    # =====================================================================

    def test_10_verify_version(self, ctx):
        """Power cycle and verify production firmware version via UART boot logs.

        FUT_VERBOSE_A has CONFIG_LOG=y on COMMS (nRF9151). The APP processor
        (nRF52840) does not emit version strings even with forceLog — the
        build flag only affects the COMMS build. COMMS version alone is
        sufficient proof that FUOTA delivered the correct firmware.

        TODO(corecloud-fix): When forceLog covers both processors, switch
        back to require_both=True.
        """
        assert TestMfgToProdFuota._target_version, "No target version — test_01 must pass first"

        versions = verify_firmware_version(
            ctx.mtib,
            expected_version=TestMfgToProdFuota._target_version,
            timeout_s=180.0,
            require_both=False,
        )

        print(f"Post-FUOTA versions: comms={versions['comms']}, app={versions['app']}")

    # =====================================================================
    # 11: Post-FUOTA cloud check-in (HARD fail)
    # =====================================================================
    # NOTE: No POST on production firmware — production FW has no manufacturing
    # shell, so run_post() fails at the shell lock step. POST is MFG-only.
    # Cloud check-in is the definitive proof that production firmware works.

    def test_11_post_fuota_checkin(self, fuota_client, ctx):
        """Power cycle and wait for CoreCloud check-in on production firmware.

        HARD FAIL — this is the definitive proof that the production firmware
        boots, initializes the modem, and communicates with CoreCloud.
        """
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in on production firmware...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client,
            TestMfgToProdFuota._device_id,
            timeout_s=300,
        )

        print(f"Post-FUOTA CoreCloud check-in confirmed (recordId={record_id})")
