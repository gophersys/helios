"""MFG Flash + POST + FUOTA to Production — the core upgrade path.

Flash MFG firmware via J-Link (including modem firmware), run POST
to verify all hardware, then deliver production firmware via FUOTA.

Pipeline builds used:
    MFG_FLASH_DEBUG      → Flashed via J-Link (mfg hex files)
    FUOTA_TARGET_RELEASE → Delivered via FUOTA (prod CFW files)
    triggerData.modemFirmware → Modem baseband firmware (.zip)

Flow:
    01. Download artifacts from pipeline (mfg hex + modem zip + prod CFW)
    02. Flash firmware via J-Link (nRF52840 app + modem baseband + nRF9151 comms)
    03. Verify DUT boots (current check)
    04. POST — power-on self-test on both processors
    05. Personalize device (EC keygen + CoreCloud key upload)
    06. Wait for CoreCloud check-in
    07. Upload prod CFW files to CoreCloud
    08. Create FUOTA plan and assign device
    09. Wait for FUOTA delivery (both 108 + 109 at 100%)
    10. Verify new firmware version via UART boot logs
    11. Cleanup (disable FUOTA assignment)

Tests are sequential — each depends on the previous. With -x (fail fast),
any failure stops the run. Class variables pass state between tests.
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
FLASH_LABEL = "MFG_FLASH_DEBUG"       # MFG firmware to flash via J-Link
FUOTA_LABEL = "FUOTA_TARGET_RELEASE"   # Production firmware to deliver via FUOTA


class TestMfgFuota:
    """MFG flash + POST + FUOTA to production firmware."""

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

        TestMfgFuota._app_hex = app_hex
        TestMfgFuota._comms_hex = comms_hex
        TestMfgFuota._flash_version = flash_build.version_string

        # --- Modem firmware: baseband zip from pipeline triggerData ---

        modem_zip = pipeline_assets.get_modem_firmware()
        if modem_zip:
            print(f"Modem FW:  {Path(modem_zip).name} ({Path(modem_zip).stat().st_size} bytes)")
            TestMfgFuota._modem_zip = modem_zip
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

        TestMfgFuota._target_cfw_paths = cfw_paths
        TestMfgFuota._target_strings = target_strings
        TestMfgFuota._target_version = fuota_build.version_string

        print(f"Ready: flash MFG v{flash_build.version_string} -> FUOTA to prod v{fuota_build.version_string}")

    # =====================================================================
    # 02: Flash firmware (nRF52840 + modem + nRF9151)
    # =====================================================================

    def test_02_flash_firmware(self, mtib_client):
        """Flash MFG firmware via J-Link (nRF52840 + modem + nRF9151)."""
        assert TestMfgFuota._app_hex, "No app hex — test_01 must pass first"
        assert TestMfgFuota._comms_hex, "No comms hex — test_01 must pass first"

        from protocols.mtib.mtib_pb2 import HostType
        from .helpers import flash_processor

        print("Powering DUT for J-Link access...")
        power_on(mtib_client)
        time.sleep(3)

        # Flash nRF52840 (app processor)
        print(f"Flashing nRF52840: {Path(TestMfgFuota._app_hex).name}")
        app_ms = flash_processor(mtib_client, TestMfgFuota._app_hex, HostType.HOST_TYPE_NRF52840)
        print(f"nRF52840 flashed in {app_ms}ms")

        # Flash modem baseband (must be before nRF9151 app — chiperase wipes both)
        if TestMfgFuota._modem_zip:
            print(f"Flashing modem: {Path(TestMfgFuota._modem_zip).name}")
            modem_ms = flash_processor(mtib_client, TestMfgFuota._modem_zip, HostType.HOST_TYPE_NRF9160_MODEM)
            print(f"Modem flashed in {modem_ms}ms")
        else:
            print("Modem flash skipped (no modem firmware)")

        # Flash nRF9151 (comms coprocessor)
        print(f"Flashing nRF9151: {Path(TestMfgFuota._comms_hex).name}")
        comms_ms = flash_processor(mtib_client, TestMfgFuota._comms_hex, HostType.HOST_TYPE_NRF9151)
        print(f"nRF9151 flashed in {comms_ms}ms")

        print("All processors flashed successfully")

    # =====================================================================
    # 03: Verify boot
    # =====================================================================

    def test_03_verify_boot(self, mtib_client):
        """Power cycle and verify DUT boots (>5mA current)."""
        print("Power cycling DUT...")
        power_cycle(mtib_client, off_s=2.0, settle_s=5.0)

        avg_current = read_total_current_ma(mtib_client, samples=10, interval_s=0.5)
        assert avg_current > 5.0, (
            f"DUT not drawing sufficient current: {avg_current:.2f}mA "
            f"(expected >5mA)"
        )

        print(f"DUT booted: avg current = {avg_current:.2f}mA")

    # =====================================================================
    # 04: POST — power-on self-test
    # =====================================================================

    def test_04_post(self, mtib_client):
        """Run POST on both processors (chip IDs, BMS, GPS, modem, IMEI, flash)."""
        from corekinect.test.post import run_post

        print("Running POST suite...")
        result = run_post(mtib_client, skip_ext_flash=False)

        # Store collected data for subsequent steps
        if result.imei:
            TestMfgFuota._imei = result.imei
            TestMfgFuota._iccids = result.iccids

        print(f"\n{result.summary()}")

        assert result.passed, (
            f"POST failed: {sum(1 for s in result.steps if not s.passed)} step(s) failed"
        )

    # =====================================================================
    # 05: Personalize
    # =====================================================================

    def test_05_personalize(self, mtib_client, device_config):
        """Lock shells, generate EC keypair, upload key to CoreCloud."""
        assert device_config.device_snr, "DEVICE_SNR required"

        # Use IMEI/ICCIDs from POST if available, else from env
        imei = TestMfgFuota._imei or device_config.device_imei or None
        iccids = TestMfgFuota._iccids or device_config.device_iccids or None

        print(f"SNR={device_config.device_snr}")
        if imei:
            print(f"IMEI={imei} (from {'POST' if TestMfgFuota._imei else 'env'})")

        result = personalize_device(
            mtib_client,
            snr=device_config.device_snr,
            device_id=device_config.device_id or None,
            imei=imei,
            iccids=iccids,
        )

        TestMfgFuota._device_id = result["device_id"]

        print(f"Device personalized: {result['device_id']}")
        print(f"Public key: {result['public_key'][:24]}...")

    # =====================================================================
    # 06: Cloud check-in
    # =====================================================================

    def test_06_cloud_checkin(self, fuota_client, mtib_client):
        """Power cycle and wait for device to check into CoreCloud."""
        assert TestMfgFuota._device_id, "No device_id — test_05 must pass first"

        print("Power cycling to trigger CoreCloud check-in...")
        power_cycle(mtib_client, off_s=2.0, settle_s=15.0)

        record_id = wait_for_cloud_checkin(
            fuota_client,
            TestMfgFuota._device_id,
            timeout_s=300,
        )

        print(f"CoreCloud check-in confirmed (recordId={record_id})")

    # =====================================================================
    # 07: Upload CFW
    # =====================================================================

    def test_07_upload_cfw(self, fuota_client):
        """Upload production CFW files to CoreCloud."""
        assert TestMfgFuota._target_cfw_paths, "No CFW paths — test_01 must pass first"

        upload_cfw_files(fuota_client, TestMfgFuota._target_cfw_paths)

        print(f"{len(TestMfgFuota._target_cfw_paths)} CFW file(s) uploaded to CoreCloud")

    # =====================================================================
    # 08: Create FUOTA plan
    # =====================================================================

    def test_08_create_plan(self, fuota_client, device_config):
        """Create FUOTA plan and assign device."""
        assert TestMfgFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgFuota._target_strings, "No target strings — test_01 must pass first"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        description = (
            f"MFG->Prod FUOTA {timestamp}: "
            f"v{TestMfgFuota._flash_version} -> v{TestMfgFuota._target_version}"
        )

        plan_id = create_and_assign_fuota_plan(
            fuota_client,
            device_id=TestMfgFuota._device_id,
            target_strings=TestMfgFuota._target_strings,
            description=description,
            device_type_id=device_config.device_type_id,
            device_variant_id=device_config.device_variant_id,
        )

        TestMfgFuota._plan_id = plan_id
        register_fuota_cleanup(TestMfgFuota._device_id, plan_id)

        print(f"Plan {plan_id} created and device assigned")
        print(f"Targets: {TestMfgFuota._target_strings}")

    # =====================================================================
    # 09: FUOTA delivery
    # =====================================================================

    def test_09_fuota_delivery(self, fuota_client, mtib_client):
        """Wait for FUOTA delivery (both 108 + 109 to 100%)."""
        assert TestMfgFuota._device_id, "No device_id — test_05 must pass first"
        assert TestMfgFuota._plan_id, "No plan_id — test_08 must pass first"

        print("Power cycling to trigger FUOTA...")
        power_cycle(mtib_client, off_s=2.0, settle_s=5.0)

        print("Monitoring FUOTA progress...")
        wait_for_fuota_completion(
            fuota_client,
            device_id=TestMfgFuota._device_id,
            timeout_s=5400,
            mtib_client=mtib_client,
            power_cycle_interval_s=180,
        )

        print("FUOTA delivery complete")

    # =====================================================================
    # 10: Verify version
    # =====================================================================

    def test_10_verify_version(self, mtib_client):
        """Power cycle and verify new firmware version via UART boot logs."""
        assert TestMfgFuota._target_version, "No target version — test_01 must pass first"

        versions = verify_firmware_version(
            mtib_client,
            expected_version=TestMfgFuota._target_version,
            timeout_s=90.0,
        )

        print(f"Post-FUOTA versions: comms={versions['comms']}, app={versions['app']}")

    # =====================================================================
    # 11: Cleanup
    # =====================================================================

    def test_11_cleanup(self, fuota_client):
        """Disable FUOTA assignment for device."""
        if not TestMfgFuota._device_id or not TestMfgFuota._plan_id:
            pytest.skip("No FUOTA assignment to clean up")

        try:
            fuota_client.disable_device(
                TestMfgFuota._device_id,
                TestMfgFuota._plan_id,
            )
            print(f"FUOTA disabled for device {TestMfgFuota._device_id}")
        except Exception as e:
            print(f"Cleanup warning: {e} — atexit handler will retry")
