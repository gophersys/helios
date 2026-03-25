"""MFG-to-Production FUOTA (quiet) — cross-variant upgrade, cloud-only verification.

Flash MFG firmware via J-Link, run POST, then FUOTA to production firmware
with CONFIG_LOG=n. Neither processor emits UART output, so verification
relies on boot current check + cloud check-in ONLY.

# ═══════════════════════════════════════════════════════════════════════
# VERSION MAPPING (update when pipeline seeds change)
# ═══════════════════════════════════════════════════════════════════════
# Label            Version   FW Type     CONFIG_LOG   CFW Flags
# MFG_FLASH        v0.5.21   mfg release  y (default)  BM
# PROD_QUIET       v0.8.22   app release  n (default)  B
#
# CORECLOUD WORKAROUND (remove when CoreCloud fixes D-flag stripping)
# ═══════════════════════════════════════════════════════════════════════
# CoreCloud strips 'D' (debug) from FUOTA plan targets:
#   Submitted: 108.0.8.22-BD  →  Stored: 108.0.8.22-B  →  MISMATCH
# All prod builds use release variant (no D flag).
#
# TODO(corecloud-fix): When fixed, switch PROD_QUIET to debug build
# if UART output is desired. Currently quiet = release with no log override.
#
# VERIFICATION STRATEGY
# ═══════════════════════════════════════════════════════════════════════
# Quiet (CONFIG_LOG=n): Neither processor emits UART output.
#   → NO verify_firmware_version step
#   → Boot current check proves firmware runs
#   → Cloud check-in (180s, HARD fail) is the sole proof of successful update

Pipeline builds used:
    MFG_FLASH              → Flashed via J-Link (mfg hex)
    PROD_QUIET             → Delivered via FUOTA (production CFW, CONFIG_LOG=n)
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
    10. Verify boot after FUOTA (current check — no UART)
    11. Post-FUOTA cloud check-in (HARD fail — only proof of update)
    12. Cleanup (disable FUOTA assignment)
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
FLASH_LABEL = "MFG_FLASH"       # MFG firmware to flash via J-Link
# TODO(corecloud-fix): When CoreCloud fixes D-flag stripping, consider switching to debug
FUOTA_LABEL = "PROD_QUIET"      # Production firmware with CONFIG_LOG=n (release, default)


@pytest.fixture(autouse=True, scope="class")
def _fuota_cleanup(request, fuota_client):
    """Ensure FUOTA assignment is cleaned up even if tests fail."""
    yield

    cls = TestMfgToProdQuietFuota
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


class TestMfgToProdQuietFuota:
    """MFG-to-Production FUOTA (quiet) — cloud-only verification."""

    # =====================================================================
    # Shared state
    # =====================================================================

    _app_hex: Optional[str] = None
    _comms_hex: Optional[str] = None
    _modem_zip: Optional[str] = None
    _flash_version: Optional[str] = None
    _target_cfw_paths: List[str] = []
    _target_strings: List[str] = []
    _target_version: Optional[str] = None
    _device_id: Optional[str] = None
    _plan_id: Optional[int] = None
    _imei: Optional[str] = None
    _iccids: List[str] = []

    # =====================================================================
    # 01: Download artifacts
    # =====================================================================

    def test_01_download_artifacts(self, pipeline_assets, device_config):
        """Download MFG hex + modem zip + quiet production CFW from pipeline."""

        # --- MFG firmware ---
        flash_build = pipeline_assets.get_build(FLASH_LABEL)
        assert flash_build, f"Build '{FLASH_LABEL}' not found in pipeline"
        assert flash_build.status in ("SUCCESS", "CACHED"), f"{FLASH_LABEL} is {flash_build.status}"
        print(f"{FLASH_LABEL}: v{flash_build.version_string} [{flash_build.status}]")

        app_hex = pipeline_assets.get_hex(FLASH_LABEL, "app")
        assert app_hex and Path(app_hex).exists(), f"{FLASH_LABEL} app hex download failed"
        comms_hex = pipeline_assets.get_hex(FLASH_LABEL, "comms")
        assert comms_hex and Path(comms_hex).exists(), f"{FLASH_LABEL} comms hex download failed"

        print(f"App hex:   {Path(app_hex).name} ({Path(app_hex).stat().st_size} bytes)")
        print(f"Comms hex: {Path(comms_hex).name} ({Path(comms_hex).stat().st_size} bytes)")

        TestMfgToProdQuietFuota._app_hex = app_hex
        TestMfgToProdQuietFuota._comms_hex = comms_hex
        TestMfgToProdQuietFuota._flash_version = flash_build.version_string

        # --- Modem firmware ---
        modem_zip = pipeline_assets.get_modem_firmware()
        if modem_zip:
            print(f"Modem FW:  {Path(modem_zip).name} ({Path(modem_zip).stat().st_size} bytes)")
            TestMfgToProdQuietFuota._modem_zip = modem_zip
        else:
            print("WARNING: No modem firmware in pipeline — modem flash will be skipped")

        # --- Quiet production firmware ---
        fuota_build = pipeline_assets.get_build(FUOTA_LABEL)
        assert fuota_build, f"Build '{FUOTA_LABEL}' not found in pipeline"
        assert fuota_build.status in ("SUCCESS", "CACHED"), f"{FUOTA_LABEL} is {fuota_build.status}"
        print(f"{FUOTA_LABEL}: v{fuota_build.version_string} [{fuota_build.status}]")

        cfw_paths = pipeline_assets.get_cfw_files(FUOTA_LABEL)
        assert cfw_paths, f"{FUOTA_LABEL} has no CFW files"

        target_strings = []
        app_ids_found = set()
        for cfw_path in cfw_paths:
            meta = parse_cfw_header(Path(cfw_path))
            target_strings.append(meta["target_string"])
            app_ids_found.add(meta["app_id"])
            print(f"CFW: {Path(cfw_path).name} -> {meta['target_string']}")

        assert 108 in app_ids_found, f"{FUOTA_LABEL} missing comms CFW (app_id=108)"
        assert 109 in app_ids_found, f"{FUOTA_LABEL} missing app CFW (app_id=109)"

        TestMfgToProdQuietFuota._target_cfw_paths = cfw_paths
        TestMfgToProdQuietFuota._target_strings = target_strings
        TestMfgToProdQuietFuota._target_version = fuota_build.version_string

        print(f"Ready: flash MFG v{flash_build.version_string} -> FUOTA to quiet prod v{fuota_build.version_string}")

    # =====================================================================
    # 02: Flash firmware
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link (nRF52840 + modem + nRF9151)."""
        assert TestMfgToProdQuietFuota._app_hex, "No app hex — test_01 must pass first"
        assert TestMfgToProdQuietFuota._comms_hex, "No comms hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        print(f"Flashing nRF52840: {Path(TestMfgToProdQuietFuota._app_hex).name}")
        app_ms = flash_processor(ctx.mtib, TestMfgToProdQuietFuota._app_hex, HostType.HOST_TYPE_NRF52840)
        print(f"nRF52840 flashed in {app_ms}ms")

        if TestMfgToProdQuietFuota._modem_zip:
            print(f"Flashing modem: {Path(TestMfgToProdQuietFuota._modem_zip).name}")
            modem_ms = flash_processor(ctx.mtib, TestMfgToProdQuietFuota._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)
            print(f"Modem flashed in {modem_ms}ms")
        else:
            print("Modem flash skipped (no modem firmware)")

        print(f"Flashing nRF9151: {Path(TestMfgToProdQuietFuota._comms_hex).name}")
        comms_ms = flash_processor(ctx.mtib, TestMfgToProdQuietFuota._comms_hex, HostType.HOST_TYPE_NRF9151)
        print(f"nRF9151 flashed in {comms_ms}ms")

        print("All processors flashed successfully")

    # =====================================================================
    # 03: Verify boot
    # =====================================================================

    def test_03_verify_boot(self, ctx):
        """Power cycle and verify DUT boots (>5mA current)."""
        print("Power cycling DUT...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        avg_current = read_total_current_ma(ctx.mtib, samples=10, interval_s=0.5)
        assert avg_current > 5.0, f"DUT not drawing sufficient current: {avg_current:.2f}mA (expected >5mA)"
        print(f"DUT booted: avg current = {avg_current:.2f}mA")

    # =====================================================================
    # 04: POST
    # =====================================================================

    def test_04_post(self, ctx):
        """Run POST on both processors."""
        from corekinect.test.post import run_post

        print("Running POST suite...")
        result = run_post(ctx.mtib, skip_ext_flash=True)

        if result.imei:
            TestMfgToProdQuietFuota._imei = result.imei
            TestMfgToProdQuietFuota._iccids = result.iccids

        print(f"\n{result.summary()}")
        assert result.passed, f"POST failed: {sum(1 for s in result.steps if not s.passed)} step(s) failed"

    # =====================================================================
    # 05: Personalize
    # =====================================================================

    def test_05_personalize(self, ctx, device_config):
        """Lock shells, generate EC keypair, upload key to CoreCloud."""
        assert device_config.device_snr, "DEVICE_SNR required"

        imei = TestMfgToProdQuietFuota._imei or device_config.device_imei or None
        iccids = TestMfgToProdQuietFuota._iccids or device_config.device_iccids or None

        print(f"SNR={device_config.device_snr}")
        if imei:
            print(f"IMEI={imei} (from {'POST' if TestMfgToProdQuietFuota._imei else 'env'})")

        result = personalize_device(
            ctx.mtib,
            snr=device_config.device_snr,
            device_id=device_config.device_id or None,
            imei=imei,
            iccids=iccids,
        )

        TestMfgToProdQuietFuota._device_id = result["device_id"]
        print(f"Device personalized: {result['device_id']}")
        print(f"Public key: {result['public_key'][:24]}...")

    # =====================================================================
    # 06: Cloud check-in (best-effort)
    # =====================================================================

    def test_06_cloud_checkin(self, fuota_client, ctx):
        """Power cycle and wait for CoreCloud check-in (best-effort)."""
        assert TestMfgToProdQuietFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        try:
            record_id = wait_for_cloud_checkin(
                fuota_client, TestMfgToProdQuietFuota._device_id, timeout_s=120,
            )
            print(f"CoreCloud check-in confirmed (recordId={record_id})")
        except BaseException:
            print("WARNING: Cloud check-in timed out (modem likely in backoff)")
            print("Device will check in during FUOTA delivery — continuing")

    # =====================================================================
    # 07: Upload CFW
    # =====================================================================

    def test_07_upload_cfw(self, fuota_client):
        """Upload quiet production CFW files to CoreCloud."""
        assert TestMfgToProdQuietFuota._target_cfw_paths, "No CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, TestMfgToProdQuietFuota._target_cfw_paths)
        print(f"{len(TestMfgToProdQuietFuota._target_cfw_paths)} CFW file(s) uploaded to CoreCloud")

    # =====================================================================
    # 08: Create FUOTA plan
    # =====================================================================

    def test_08_create_plan(self, fuota_client, device_config):
        """Create FUOTA plan and assign device."""
        assert TestMfgToProdQuietFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToProdQuietFuota._target_strings, "No target strings — test_01 must pass first"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"MFG->Prod-Quiet FUOTA {timestamp}: "
            f"v{TestMfgToProdQuietFuota._flash_version} -> v{TestMfgToProdQuietFuota._target_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=TestMfgToProdQuietFuota._device_id,
            target_strings=TestMfgToProdQuietFuota._target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        TestMfgToProdQuietFuota._plan_id = plan_id
        register_fuota_cleanup(TestMfgToProdQuietFuota._device_id, plan_id)

        print(f"Plan {plan_id} created and device assigned")
        print(f"Targets: {TestMfgToProdQuietFuota._target_strings}")

    # =====================================================================
    # 09: FUOTA delivery
    # =====================================================================

    def test_09_fuota_delivery(self, fuota_client, ctx):
        """Wait for FUOTA delivery (both 108 + 109 to 100%)."""
        assert TestMfgToProdQuietFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToProdQuietFuota._plan_id, "No plan_id — test_08 must pass first"

        print("Power cycling to trigger FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        print("Monitoring FUOTA progress...")
        wait_for_fuota_completion(
            fuota_client,
            device_id=TestMfgToProdQuietFuota._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
        )

        print("FUOTA delivery complete")

    # =====================================================================
    # 10: Verify boot after FUOTA (no UART — current check only)
    # =====================================================================

    def test_10_verify_boot_after_fuota(self, ctx):
        """Power cycle and verify DUT boots after FUOTA (current check).

        Quiet firmware has no UART output — boot current is the only
        hardware-level proof that firmware runs. Cloud check-in (next step)
        is the definitive proof.
        """
        print("Power cycling to verify post-FUOTA boot...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=10.0)

        avg_current = read_total_current_ma(ctx.mtib, samples=10, interval_s=0.5)
        assert avg_current > 5.0, (
            f"Post-FUOTA DUT not drawing sufficient current: {avg_current:.2f}mA "
            f"(expected >5mA — firmware may not have booted after FUOTA)"
        )

        print(f"Post-FUOTA DUT booted: avg current = {avg_current:.2f}mA")

    # =====================================================================
    # 11: Post-FUOTA cloud check-in (HARD fail — only proof of update)
    # =====================================================================

    def test_11_post_fuota_checkin(self, fuota_client, ctx):
        """Wait for CoreCloud check-in on quiet production firmware.

        HARD FAIL — for quiet firmware this is the ONLY proof that:
        1. The FUOTA-delivered firmware boots correctly
        2. The modem initializes and connects
        3. The device authenticates with CoreCloud
        """
        assert TestMfgToProdQuietFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in on quiet production firmware...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client,
            TestMfgToProdQuietFuota._device_id,
            timeout_s=180,
        )

        print(f"Post-FUOTA CoreCloud check-in confirmed (recordId={record_id})")
