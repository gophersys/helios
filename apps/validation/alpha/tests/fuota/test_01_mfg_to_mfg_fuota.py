"""MFG-to-MFG FUOTA — sanity check (same code, version bump).

Flash older MFG firmware, run POST, then FUOTA to newer MFG firmware.
Proves the FUOTA delivery mechanism works before testing cross-variant
upgrades (MFG→PROD).

Pipeline builds used:
    MFG_BASE               → Flashed via J-Link (older mfg hex, v0.5.3)
    MFG_BUMP               → Delivered via FUOTA (newer mfg CFW, v0.5.4)
    triggerData.modemFirmware → Modem baseband firmware (.zip)

Flow:
    01. Download artifacts (older mfg hex + modem zip + newer mfg CFW)
    02. Flash older MFG via J-Link (nRF52840 + modem + nRF9151)
    03. Verify DUT boots (current check)
    04. POST — power-on self-test on both processors
    05. Personalize device (EC keygen + CoreCloud key upload)
    06. Wait for CoreCloud check-in (best-effort)
    07. Upload newer MFG CFW to CoreCloud
    08. Create FUOTA plan and assign device
    09. Wait for FUOTA delivery (both 108 + 109 at 100%)
    10. Verify new MFG firmware version via UART boot logs
    11. POST after FUOTA — verify new firmware works
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
    verify_firmware_version,
    wait_for_cloud_checkin,
    wait_for_fuota_completion,
)

# Pipeline build labels
FLASH_LABEL = "MFG_BASE"     # Older MFG firmware to flash via J-Link
FUOTA_LABEL = "MFG_BUMP"     # Newer MFG firmware to deliver via FUOTA (same code, bumped version)


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

    cls = TestMfgToMfgFuota
    device_id = cls._device_id
    plan_id = cls._plan_id

    if not device_id or not plan_id:
        # No plan was created — nothing to clean up
        return

    print(f"\nCleaning up FUOTA assignment...")
    try:
        # Check if device is still assigned to this plan
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


@pytest.mark.fuota_fast
class TestMfgToMfgFuota:
    """MFG-to-MFG FUOTA — sanity check (same code, version bump)."""

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

        # Comms hex: only download if the build has a comms target
        try:
            comms_hex = flash_build.hex("comms")
        except Exception:
            comms_hex = None

        print(f"App hex:   {Path(app_hex).name} ({Path(app_hex).stat().st_size} bytes)")
        if comms_hex:
            print(f"Comms hex: {Path(comms_hex).name} ({Path(comms_hex).stat().st_size} bytes)")

        TestMfgToMfgFuota._app_hex = app_hex
        TestMfgToMfgFuota._comms_hex = comms_hex
        TestMfgToMfgFuota._flash_version = flash_version

        # Store flash targets for later use in flash step
        TestMfgToMfgFuota._flash_targets = flash_targets

        # --- Modem firmware: from manifest or pipeline triggerData ---

        modem_zip = stage_assets.modem_zip()
        if modem_zip:
            print(f"Modem FW:  {Path(modem_zip).name} ({Path(modem_zip).stat().st_size} bytes)")
            TestMfgToMfgFuota._modem_zip = modem_zip
        else:
            print("WARNING: No modem firmware in pipeline — modem flash will be skipped")

        # --- FUOTA target firmware: CFW files for OTA delivery ---

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

        TestMfgToMfgFuota._target_cfw_paths = cfw_paths
        TestMfgToMfgFuota._target_strings = target_strings
        TestMfgToMfgFuota._target_version = fuota_version
        TestMfgToMfgFuota._fuota_targets = fuota_targets

        print(f"Ready: flash MFG v{flash_version} -> FUOTA to MFG v{fuota_version}")

    # =====================================================================
    # 02: Flash firmware (nRF52840 + modem + nRF9151)
    # =====================================================================

    def test_02_flash_firmware(self, ctx):
        """Flash MFG firmware via J-Link using targets from manifest."""
        assert TestMfgToMfgFuota._app_hex, "No app hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor, host_type_from_manifest

        print("Powering DUT for J-Link access...")
        power_on(ctx.mtib)
        time.sleep(3)

        # Flash app processor using manifest target metadata
        app_target = next(
            (t for t in TestMfgToMfgFuota._flash_targets if t.role == "app"), None
        )
        assert app_target, "No app target in flash build manifest"
        app_host_type = host_type_from_manifest(app_target.host_type)
        print(f"Flashing {app_target.processor}: {Path(TestMfgToMfgFuota._app_hex).name}")
        app_ms = flash_processor(ctx.mtib, TestMfgToMfgFuota._app_hex, app_host_type)
        print(f"{app_target.processor} flashed in {app_ms}ms")

        # Flash modem baseband (must be before comms app — chiperase wipes both)
        if TestMfgToMfgFuota._modem_zip:
            print(f"Flashing modem: {Path(TestMfgToMfgFuota._modem_zip).name}")
            modem_ms = flash_processor(ctx.mtib, TestMfgToMfgFuota._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)
            print(f"Modem flashed in {modem_ms}ms")
        else:
            print("Modem flash skipped (no modem firmware)")

        # Flash comms processor if present
        if TestMfgToMfgFuota._comms_hex:
            comms_target = next(
                (t for t in TestMfgToMfgFuota._flash_targets if t.role == "comms"), None
            )
            assert comms_target, "No comms target in flash build manifest"
            comms_host_type = host_type_from_manifest(comms_target.host_type)
            print(f"Flashing {comms_target.processor}: {Path(TestMfgToMfgFuota._comms_hex).name}")
            comms_ms = flash_processor(ctx.mtib, TestMfgToMfgFuota._comms_hex, comms_host_type)
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
            TestMfgToMfgFuota._imei = result.imei
            TestMfgToMfgFuota._iccids = result.iccids

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
        imei = TestMfgToMfgFuota._imei or device_config.device_imei or None
        iccids = TestMfgToMfgFuota._iccids or device_config.device_iccids or None

        print(f"SNR={device_config.device_snr}")
        if imei:
            print(f"IMEI={imei} (from {'POST' if TestMfgToMfgFuota._imei else 'env'})")

        result = personalize_device(
            ctx.mtib,
            snr=device_config.device_snr,
            device_id=device_config.device_id or None,
            imei=imei,
            iccids=iccids,
        )

        TestMfgToMfgFuota._device_id = result["device_id"]

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
        assert TestMfgToMfgFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=15.0)

        try:
            record_id = wait_for_cloud_checkin(
                fuota_client,
                TestMfgToMfgFuota._device_id,
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
        assert TestMfgToMfgFuota._target_cfw_paths, "No CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, TestMfgToMfgFuota._target_cfw_paths)

        print(f"{len(TestMfgToMfgFuota._target_cfw_paths)} CFW file(s) uploaded to CoreCloud")

    # =====================================================================
    # 08: Create FUOTA plan
    # =====================================================================

    def test_08_create_plan(self, fuota_client, device_config):
        """Create FUOTA plan and assign device."""
        assert TestMfgToMfgFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToMfgFuota._target_strings, "No target strings — test_01 must pass first"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"MFG->Prod FUOTA {timestamp}: "
            f"v{TestMfgToMfgFuota._flash_version} -> v{TestMfgToMfgFuota._target_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=TestMfgToMfgFuota._device_id,
            target_strings=TestMfgToMfgFuota._target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        TestMfgToMfgFuota._plan_id = plan_id
        register_fuota_cleanup(TestMfgToMfgFuota._device_id, plan_id)

        print(f"Plan {plan_id} created and device assigned")
        print(f"Targets: {TestMfgToMfgFuota._target_strings}")

    # =====================================================================
    # 09: FUOTA delivery
    # =====================================================================

    def test_09_fuota_delivery(self, fuota_client, ctx):
        """Wait for FUOTA delivery (all targets to 100%)."""
        assert TestMfgToMfgFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgToMfgFuota._plan_id, "No plan_id — test_08 must pass first"

        # Pass expected app IDs from manifest targets (product-agnostic)
        expected_app_ids = {t.app_id for t in TestMfgToMfgFuota._fuota_targets}

        print("Power cycling to trigger FUOTA...")
        power_cycle(ctx.mtib, off_s=2.0, settle_s=5.0)

        print("Monitoring FUOTA progress...")
        wait_for_fuota_completion(
            fuota_client,
            device_id=TestMfgToMfgFuota._device_id,
            timeout_s=1200,
            mtib_client=ctx.mtib,
            expected_app_ids=expected_app_ids,
        )

        print("FUOTA delivery complete")

    # =====================================================================
    # 10: Verify version
    # =====================================================================

    def test_10_verify_version(self, ctx):
        """Power cycle and verify new MFG firmware version via UART boot logs.

        Waits up to 180s for MCUboot swap to complete (swap can take 30-60s).
        Uses AlphaVersionDetector for product-specific pattern matching.
        """
        assert TestMfgToMfgFuota._target_version, "No target version — test_01 must pass first"

        versions = verify_firmware_version(
            ctx.mtib,
            expected_version=TestMfgToMfgFuota._target_version,
            timeout_s=180.0,
        )

        print(f"Post-FUOTA versions: comms={versions['comms']}, app={versions['app']}")

    # =====================================================================
    # 11: POST after FUOTA
    # =====================================================================

    def test_11_post_after_fuota(self, ctx):
        """Re-run POST to verify the new MFG firmware works after FUOTA.

        This confirms the FUOTA-delivered firmware is functional — shells lock,
        chip IDs read, BMS/charger/GPS respond, modem works.
        """
        from corekinect.test.post import run_post

        print("Running POST on FUOTA-delivered firmware...")
        result = run_post(ctx.mtib, skip_ext_flash=True)

        # Update IMEI/ICCIDs if POST collected them
        if result.imei:
            TestMfgToMfgFuota._imei = result.imei
            TestMfgToMfgFuota._iccids = result.iccids

        print(f"\n{result.summary()}")

        assert result.passed, (
            f"Post-FUOTA POST failed: {sum(1 for s in result.steps if not s.passed)} step(s) failed"
        )

    # Cleanup is handled by the _fuota_cleanup fixture (runs after all tests, even on failure)
