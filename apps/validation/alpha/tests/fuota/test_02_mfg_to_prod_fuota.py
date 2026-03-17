"""MFG-to-Production FUOTA — cross-variant upgrade.

Flash MFG firmware via J-Link, run POST, then FUOTA to production firmware.
This is the primary real-world upgrade path: devices ship with manufacturing
firmware and receive production firmware over the air.

Pipeline builds used:
    MFG_FLASH              → Flashed via J-Link (mfg hex)
    FUOTA_TARGET_RELEASE   → Delivered via FUOTA (production CFW)
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
    12. Post-FUOTA smoke — CoreCloud check-in on production firmware
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
    flash_both_processors,
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
FLASH_LABEL = "MFG_BASE"               # MFG firmware to flash via J-Link
FUOTA_LABEL = "FUOTA_TARGET_RELEASE"    # Production firmware to deliver via FUOTA


@pytest.fixture(autouse=True, scope="class")
def _fuota_cleanup(request, fuota_client):
    """Ensure FUOTA assignment is cleaned up even if tests fail.

    Cleanup hierarchy (most to least reliable):
    1. This fixture — runs after all tests in the class, even on failure
    2. register_fuota_cleanup() atexit handler — runs on process exit
    3. Manual cleanup via CoreCloud API if all else fails

    Only attempts cleanup if a plan was actually created (plan_id exists).
    Gracefully handles cases where the device/plan don't exist anymore.
    """
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


class TestMfgToProdFuota:
    """MFG-to-Production FUOTA — cross-variant upgrade."""

    # =====================================================================
    # Shared state (populated by earlier tests, consumed by later ones)
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
    # Collected from POST
    _imei: Optional[str] = None
    _iccids: List[str] = []

    # =====================================================================
    # 01: Download artifacts
    # =====================================================================

    def test_01_download_artifacts(self, pipeline_assets, device_config):
        """Download MFG hex + modem zip + production CFW from pipeline."""

        # --- MFG firmware: hex files for J-Link flash ---

        flash_build = pipeline_assets.get_build(FLASH_LABEL)
        assert flash_build, f"Build '{FLASH_LABEL}' not found in pipeline"
        assert flash_build.status in ("SUCCESS", "CACHED"), (
            f"{FLASH_LABEL} is {flash_build.status}"
        )

        print(f"{FLASH_LABEL}: v{flash_build.version_string} [{flash_build.status}]")

        app_hex = pipeline_assets.get_hex(FLASH_LABEL, "app")
        assert app_hex and Path(app_hex).exists(), f"{FLASH_LABEL} app hex download failed"

        comms_hex = pipeline_assets.get_hex(FLASH_LABEL, "comms")
        assert comms_hex and Path(comms_hex).exists(), f"{FLASH_LABEL} comms hex download failed"

        print(f"App hex:   {Path(app_hex).name} ({Path(app_hex).stat().st_size} bytes)")
        print(f"Comms hex: {Path(comms_hex).name} ({Path(comms_hex).stat().st_size} bytes)")

        TestMfgToProdFuota._app_hex = app_hex
        TestMfgToProdFuota._comms_hex = comms_hex
        TestMfgToProdFuota._flash_version = flash_build.version_string

        # --- Modem firmware: baseband zip from pipeline triggerData ---

        modem_zip = pipeline_assets.get_modem_firmware()
        if modem_zip:
            print(f"Modem FW:  {Path(modem_zip).name} ({Path(modem_zip).stat().st_size} bytes)")
            TestMfgToProdFuota._modem_zip = modem_zip
        else:
            print("WARNING: No modem firmware in pipeline — modem flash will be skipped")

        # --- Production firmware: CFW files for FUOTA delivery ---

        fuota_build = pipeline_assets.get_build(FUOTA_LABEL)
        assert fuota_build, f"Build '{FUOTA_LABEL}' not found in pipeline"
        assert fuota_build.status in ("SUCCESS", "CACHED"), (
            f"{FUOTA_LABEL} is {fuota_build.status}"
        )

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

        TestMfgToProdFuota._target_cfw_paths = cfw_paths
        TestMfgToProdFuota._target_strings = target_strings
        TestMfgToProdFuota._target_version = fuota_build.version_string

        print(f"Ready: flash MFG v{flash_build.version_string} -> FUOTA to prod v{fuota_build.version_string}")

    # =====================================================================
    # 02: Flash firmware (nRF52840 + modem + nRF9151)
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link (nRF52840 + modem + nRF9151)."""
        assert TestMfgToProdFuota._app_hex, "No app hex — test_01 must pass first"
        assert TestMfgToProdFuota._comms_hex, "No comms hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        # Flash nRF52840 (app processor)
        print(f"Flashing nRF52840: {Path(TestMfgToProdFuota._app_hex).name}")
        app_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._app_hex, HostType.HOST_TYPE_NRF52840)
        print(f"nRF52840 flashed in {app_ms}ms")

        # Flash modem baseband (must be before nRF9151 app — chiperase wipes both)
        if TestMfgToProdFuota._modem_zip:
            print(f"Flashing modem: {Path(TestMfgToProdFuota._modem_zip).name}")
            modem_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)
            print(f"Modem flashed in {modem_ms}ms")
        else:
            print("Modem flash skipped (no modem firmware)")

        # Flash nRF9151 (comms coprocessor)
        print(f"Flashing nRF9151: {Path(TestMfgToProdFuota._comms_hex).name}")
        comms_ms = flash_processor(ctx.mtib, TestMfgToProdFuota._comms_hex, HostType.HOST_TYPE_NRF9151)
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
            f"MFG->Prod FUOTA {timestamp}: "
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
        """Wait for FUOTA delivery (both 108 + 109 to 100%).

        Production firmware is typically larger than MFG — allow extra time.
        """
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToProdFuota._plan_id, "No plan_id — test_08 must pass first"

        print("Power cycling to trigger FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        print("Monitoring FUOTA progress...")
        wait_for_fuota_completion(
            fuota_client,
            device_id=TestMfgToProdFuota._device_id,
            timeout_s=5400,
            mtib_client=ctx.mtib,
            power_cycle_interval_s=600,
        )

        print("FUOTA delivery complete")

    # =====================================================================
    # 10: Verify version
    # =====================================================================

    def test_10_verify_version(self, ctx):
        """Power cycle and verify production firmware version via UART boot logs.

        Production firmware has different boot patterns than MFG:
        - No manufacturing shell activation
        - Different startup sequence (BLE advertising, sensor init)
        - MCUboot swap may take 30-60s after FUOTA delivery

        Uses AlphaVersionDetector which handles both MFG and production patterns.
        """
        assert TestMfgToProdFuota._target_version, "No target version — test_01 must pass first"

        versions = verify_firmware_version(
            ctx.mtib,
            expected_version=TestMfgToProdFuota._target_version,
            timeout_s=180.0,
        )

        print(f"Post-FUOTA versions: comms={versions['comms']}, app={versions['app']}")

    # =====================================================================
    # 11: POST after FUOTA
    # =====================================================================

    def test_11_post_after_fuota(self, ctx):
        """Re-run POST to verify the production firmware works after FUOTA.

        IMPORTANT: Production firmware does NOT have a manufacturing shell.
        POST will skip shell-dependent steps (they require MFG firmware).
        The key checks are: DUT boots, current draw is healthy, chip IDs
        are readable via J-Link (not shell), and modem responds.

        If POST fails here, the production firmware has a functional issue
        that the MFG firmware didn't have — likely a regression.
        """
        from corekinect.test.post import run_post

        print("Running POST on production firmware...")
        result = run_post(ctx.mtib, skip_ext_flash=True)

        # Update IMEI/ICCIDs if POST collected them
        if result.imei:
            TestMfgToProdFuota._imei = result.imei
            TestMfgToProdFuota._iccids = result.iccids

        print(f"\n{result.summary()}")

        assert result.passed, (
            f"Post-FUOTA POST failed: {sum(1 for s in result.steps if not s.passed)} step(s) failed"
        )

    # =====================================================================
    # 12: Post-FUOTA smoke test
    # =====================================================================

    def test_12_post_fuota_smoke(self, fuota_client, ctx):
        """Power cycle and wait for CoreCloud check-in on production firmware.

        After FUOTA + POST, power cycle and confirm the device checks into
        CoreCloud with the production firmware. This proves end-to-end: the
        production firmware boots, initializes the modem, and successfully
        communicates with the cloud backend.
        """
        assert TestMfgToProdFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in on production firmware...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client,
            TestMfgToProdFuota._device_id,
            timeout_s=180,
        )

        print(f"Post-FUOTA CoreCloud check-in confirmed (recordId={record_id})")

    # Cleanup is handled by the _fuota_cleanup fixture (runs after all tests, even on failure)
