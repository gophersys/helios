"""Gate tests - Stage 5: PR validation + FUOTA.

This is the merge blocker that runs on every PR.
Total duration: < 15 minutes (hard limit).

The tests are ordered and sequential - each depends on the previous.
Test IDs use GATE-ALPHA-NNN format for traceability.

Run with:
    pytest tests/gate/test_gate.py -v --timeout=900

Environment:
    MTIB_ADDRESS, DEVICE_SNR, FIXTURE_PROFILE_PATH (required)
    PIPELINE_ID, CONCORD_API_URL, CONCORD_API_KEY (for firmware)
    VAL_1_0_API_* (for FUOTA)
"""

import time
from pathlib import Path

import pytest

from corekinect.utils import Logger

from tests.common.timing import Timing
from tests.common.assertions import (
    assert_powered,
    assert_flash_success,
    assert_fuota_progress,
)
from .conftest import GateConfig, parse_cfw_header, register_fuota_cleanup

log = Logger(log_name="gate.test")


class TestGate:
    """Gate validation tests - ordered sequence.

    Tests are numbered to ensure correct execution order.
    Each test depends on previous tests passing.
    Class variables share state between tests.
    """

    # =========================================================================
    # TEST STATE (shared between tests)
    # =========================================================================

    _app_hex: Path = None
    _comms_hex: Path = None
    _source_cfw: list = []
    _target_cfw: list = []
    _source_targets: list = []
    _target_targets: list = []
    _plan_id: int = None

    # =========================================================================
    # FIXTURES
    # =========================================================================

    @pytest.fixture(autouse=True)
    def setup(self, ctx, gate_config, fuota, pipeline_assets, is_mock_mode):
        """Inject fixtures into test instance."""
        self.ctx = ctx
        self.config = gate_config
        self.fuota = fuota
        self.pipeline = pipeline_assets
        self.is_mock = is_mock_mode

    # =========================================================================
    # GATE-ALPHA-001: Download and verify firmware artifacts
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.FUOTA_UPLOAD)
    def test_01_download_artifacts(self):
        """GATE-ALPHA-001: Download firmware artifacts from pipeline."""
        if not self.pipeline:
            pytest.skip("PIPELINE_ID not set - no firmware artifacts available")

        log.info("Pipeline: %s", self.pipeline.pipeline_id)
        log.info("\n%s", self.pipeline.summary())

        # Verify builds exist
        source = self.pipeline.get_build(self.config.source_build)
        target = self.pipeline.get_build(self.config.target_build)

        assert source.status == "SUCCESS", f"{self.config.source_build} not SUCCESS"
        assert target.status == "SUCCESS", f"{self.config.target_build} not SUCCESS"

        # Download hex files for J-Link flash
        log.info("Downloading hex files...")
        TestGate._app_hex = Path(self.pipeline.get_hex(self.config.source_build, "app"))
        TestGate._comms_hex = Path(self.pipeline.get_hex(self.config.source_build, "comms"))

        assert TestGate._app_hex.exists(), f"App hex not found: {TestGate._app_hex}"
        assert TestGate._comms_hex.exists(), f"Comms hex not found: {TestGate._comms_hex}"

        log.info("App hex: %s (%d bytes)", TestGate._app_hex.name, TestGate._app_hex.stat().st_size)
        log.info("Comms hex: %s (%d bytes)", TestGate._comms_hex.name, TestGate._comms_hex.stat().st_size)

        # Download CFW files for FUOTA
        log.info("Downloading CFW files...")
        TestGate._source_cfw = [Path(p) for p in self.pipeline.get_cfw_files(self.config.source_build)]
        TestGate._target_cfw = [Path(p) for p in self.pipeline.get_cfw_files(self.config.target_build)]

        assert TestGate._source_cfw, f"No CFW files in {self.config.source_build}"
        assert TestGate._target_cfw, f"No CFW files in {self.config.target_build}"

        # Parse CFW headers to get target strings
        for cfw in TestGate._source_cfw:
            meta = parse_cfw_header(cfw)
            TestGate._source_targets.append(meta["target_string"])
            log.info("Source CFW: %s -> %s", cfw.name, meta["target_string"])

        for cfw in TestGate._target_cfw:
            meta = parse_cfw_header(cfw)
            TestGate._target_targets.append(meta["target_string"])
            log.info("Target CFW: %s -> %s", cfw.name, meta["target_string"])

        # Verify we have both app IDs (108=comms, 109=app)
        source_ids = {parse_cfw_header(c)["app_id"] for c in TestGate._source_cfw}
        target_ids = {parse_cfw_header(c)["app_id"] for c in TestGate._target_cfw}

        assert 108 in source_ids, "Source missing comms CFW (app_id=108)"
        assert 109 in source_ids, "Source missing app CFW (app_id=109)"
        assert 108 in target_ids, "Target missing comms CFW (app_id=108)"
        assert 109 in target_ids, "Target missing app CFW (app_id=109)"

        log.info("GATE-ALPHA-001 PASS: Artifacts downloaded and verified")

    # =========================================================================
    # GATE-ALPHA-002: Flash firmware (nRF52840 -> modem -> nRF9151)
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.FLASH_ALL)
    def test_02_flash_firmware(self):
        """GATE-ALPHA-002: Flash all 3 targets via J-Link."""
        if self.is_mock:
            pytest.skip("J-Link flash requires real MTIB hardware")

        from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

        # Ensure DUT is powered for SWD access
        log.info("Powering DUT for J-Link access...")
        self.ctx.fixture.power_on()
        time.sleep(3)

        # --- Flash nRF52840 (app processor) ---
        log.info("Flashing nRF52840: %s", TestGate._app_hex.name)
        err = self.ctx.mtib.UploadFwFile(str(TestGate._app_hex), HostType.HOST_TYPE_NRF52840)
        assert not err, f"Upload failed: {err}"

        file_info = FwFileInfo(name=TestGate._app_hex.name, target=HostType.HOST_TYPE_NRF52840)
        result = self.ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
        time_ms = assert_flash_success(result, "nRF52840")
        log.info("nRF52840 flashed in %dms", time_ms)

        # --- Flash modem (baseband) ---
        modem = self.config.modem_fw_path
        log.info("Flashing modem: %s", modem.name)
        err = self.ctx.mtib.UploadFwFile(str(modem), HostType.HOST_TYPE_NRF9160_MODEM)
        assert not err, f"Upload failed: {err}"

        file_info = FwFileInfo(name=modem.name, target=HostType.HOST_TYPE_NRF9160_MODEM)
        result = self.ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
        time_ms = assert_flash_success(result, "modem")
        log.info("Modem flashed in %dms", time_ms)

        # --- Flash nRF9151 (comms processor) ---
        log.info("Flashing nRF9151: %s", TestGate._comms_hex.name)
        err = self.ctx.mtib.UploadFwFile(str(TestGate._comms_hex), HostType.HOST_TYPE_NRF9151)
        assert not err, f"Upload failed: {err}"

        file_info = FwFileInfo(name=TestGate._comms_hex.name, target=HostType.HOST_TYPE_NRF9151)
        result = self.ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
        time_ms = assert_flash_success(result, "nRF9151")
        log.info("nRF9151 flashed in %dms", time_ms)

        log.info("GATE-ALPHA-002 PASS: All 3 targets flashed")

    # =========================================================================
    # GATE-ALPHA-003: Verify boot
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.BOOT_VERIFY)
    def test_03_verify_boot(self):
        """GATE-ALPHA-003: Verify device boots after flash."""
        log.info("Power cycling device...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()
        time.sleep(Timing.GATE.BOOT_SETTLE)

        avg_current = assert_powered(self.ctx.fixture, min_current_ma=5.0)
        log.info("GATE-ALPHA-003 PASS: Device booted (avg current: %.2fmA)", avg_current)

    # =========================================================================
    # GATE-ALPHA-004: Personalize device
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.PERSONALIZE)
    def test_04_personalize(self):
        """GATE-ALPHA-004: Personalize device (shell lock + EC keygen + key upload)."""
        if self.is_mock:
            pytest.skip("Device personalization requires real MTIB hardware")

        from corekinect.test.validation.device_personalizer import DevicePersonalizer

        log.info("Personalizing device: snr=%s device_id=%s",
                 self.config.device_snr, self.config.device_id)
        if self.config.device_imei:
            log.info("Using pre-known IMEI: %s (skipping modem read)", self.config.device_imei)
        if self.config.device_iccids:
            log.info("Using pre-known ICCIDs: %s", self.config.device_iccids)

        personalizer = DevicePersonalizer(
            mtib=self.ctx.mtib,
            snr=self.config.device_snr,
            known_device_id=self.config.device_id,
            imei=self.config.device_imei or None,
            iccids=self.config.device_iccids or None,
        )

        result, err = personalizer.repersonalize(power_cycle=True, lock_shells=True)
        assert result and not err, f"Personalization failed: {err}"

        log.info("Device ID: %s", result.device_id)
        log.info("Public key: %s...", result.pub_key_base64[:20] if result.pub_key_base64 else "none")
        log.info("GATE-ALPHA-004 PASS: Device personalized")

    # =========================================================================
    # GATE-ALPHA-005: Cloud check-in
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.CLOUD_CHECKIN)
    def test_05_cloud_checkin(self):
        """GATE-ALPHA-005: Wait for device to check into CoreCloud."""
        if self.is_mock:
            pytest.skip("Cloud check-in requires real CoreCloud API")

        device_id = self.config.device_id

        # Power cycle to trigger fresh check-in
        log.info("Power cycling to trigger cloud check-in...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()
        time.sleep(15)  # Wait for LTE attach

        # Get initial record ID
        initial_record_id = 0
        try:
            status = self.fuota._api_request(
                "GET", "/System/Devices/Status",
                json={"deviceIds": [device_id]}
            ).json()
            devices = status.get("devices", [])
            if devices:
                initial_record_id = devices[0].get("positionInfo", {}).get("recordId", 0)
            log.info("Initial recordId: %d", initial_record_id)
        except Exception as e:
            log.warning("Could not get initial status: %s", e)

        # Poll for new check-in
        poll_interval = Timing.GATE.CLOUD_POLL_INTERVAL
        timeout_s = Timing.GATE.CLOUD_CHECKIN - 30  # Leave buffer
        start = time.time()

        while time.time() - start < timeout_s:
            elapsed = int(time.time() - start)
            try:
                status = self.fuota._api_request(
                    "GET", "/System/Devices/Status",
                    json={"deviceIds": [device_id]}
                ).json()
                devices = status.get("devices", [])
                if devices:
                    current = devices[0].get("positionInfo", {}).get("recordId", 0)
                    if current > initial_record_id:
                        log.info("[%ds] Device checked in: recordId %d -> %d",
                                 elapsed, initial_record_id, current)
                        log.info("GATE-ALPHA-005 PASS: Cloud check-in successful")
                        return
                    log.info("[%ds] Waiting... (recordId=%d)", elapsed, current)
            except Exception as e:
                log.warning("[%ds] Status check failed: %s", elapsed, e)

            time.sleep(poll_interval)

        pytest.fail(f"Device did not check into CoreCloud within {timeout_s}s")

    # =========================================================================
    # GATE-ALPHA-006: Upload CFW files
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.FUOTA_UPLOAD)
    def test_06_upload_cfw(self):
        """GATE-ALPHA-006: Upload CFW files to CoreCloud."""
        if self.is_mock:
            pytest.skip("CFW upload requires real CoreCloud API")

        all_cfw = TestGate._source_cfw + TestGate._target_cfw

        for cfw_path in all_cfw:
            log.info("Uploading %s...", cfw_path.name)
            try:
                self.fuota.upload_cfw(str(cfw_path))
                log.info("Uploaded: %s", cfw_path.name)
            except Exception as e:
                if "already exists" in str(e).lower():
                    log.info("Already exists: %s", cfw_path.name)
                else:
                    raise

        log.info("GATE-ALPHA-006 PASS: CFW files uploaded")

    # =========================================================================
    # GATE-ALPHA-007: Create FUOTA plan and assign device
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.FUOTA_PLAN)
    def test_07_fuota_plan(self):
        """GATE-ALPHA-007: Create FUOTA plan and assign device."""
        if self.is_mock:
            pytest.skip("FUOTA plan requires real CoreCloud API")

        device_id = self.config.device_id

        log.info("Source targets: %s", TestGate._source_targets)
        log.info("Target targets: %s", TestGate._target_targets)

        # Create plan
        plan_name = f"Gate {self.config.source_build}→{self.config.target_build} {time.strftime('%Y%m%d_%H%M%S')}"
        stages = [
            {
                "targets": TestGate._source_targets,
                "description": f"Stage 0: {self.config.source_build}",
                "isSkippable": False,
            },
            {
                "targets": TestGate._target_targets,
                "description": f"Stage 1: {self.config.target_build}",
                "isSkippable": False,
            },
        ]

        log.info("Creating FUOTA plan: %s", plan_name)
        plan_id = self.fuota.create_plan(
            stages=stages,
            description=plan_name,
            device_type_id=self.config.device_type_id,
            device_variant_id=self.config.device_variant_id,
        )
        assert plan_id is not None, "Plan creation returned None"

        TestGate._plan_id = plan_id
        log.info("Created plan: %d", plan_id)

        # Ensure device is registered
        self.fuota.ensure_device_registered(
            device_id,
            device_type_id=self.config.device_type_id,
            device_variant_id=self.config.device_variant_id,
        )

        # Assign device to plan
        log.info("Assigning device %s to plan %d...", device_id, plan_id)
        self.fuota.assign_device(
            plan_id=plan_id,
            device_ids=[device_id],
            max_stage=1,
            enable=True,
            device_type_id=self.config.device_type_id,
            device_variant_id=self.config.device_variant_id,
        )

        # Register cleanup
        register_fuota_cleanup(device_id, plan_id)

        # Verify assignment
        settings = self.fuota.get_device_settings(device_id)
        assert settings and settings.get("enableFuota"), "FUOTA not enabled after assignment"
        assert settings.get("planId") == plan_id, f"Wrong planId: {settings.get('planId')} != {plan_id}"

        log.info("GATE-ALPHA-007 PASS: Plan created and device assigned")

    # =========================================================================
    # GATE-ALPHA-008: FUOTA delivery
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.FUOTA_DELIVERY)
    def test_08_fuota_delivery(self):
        """GATE-ALPHA-008: Wait for FUOTA delivery to complete."""
        if self.is_mock:
            pytest.skip("FUOTA delivery requires real hardware and CoreCloud API")

        device_id = self.config.device_id

        # Power cycle to trigger FUOTA
        log.info("Power cycling to trigger FUOTA...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()
        time.sleep(Timing.GATE.BOOT_SETTLE)

        # Monitor progress
        poll_interval = Timing.GATE.FUOTA_POLL_INTERVAL
        timeout_s = Timing.GATE.FUOTA_DELIVERY - 60  # Leave buffer
        start = time.time()
        last_progress = None

        log.info("Monitoring FUOTA progress (timeout=%ds)...", timeout_s)

        while time.time() - start < timeout_s:
            elapsed = int(time.time() - start)

            try:
                progress = self.fuota.get_progress(device_id)
            except Exception as e:
                log.warning("[%ds] Progress check failed: %s", elapsed, e)
                time.sleep(poll_interval)
                continue

            if progress and progress != last_progress:
                log.info("[%ds] Progress: %s", elapsed, progress)
                last_progress = progress

                if progress.get("isComplete"):
                    log.info("GATE-ALPHA-008 PASS: FUOTA delivery complete!")
                    return
            else:
                log.info("[%ds] Waiting for FUOTA activity...", elapsed)

            time.sleep(poll_interval)

        pytest.fail(f"FUOTA did not complete within {timeout_s}s. Last: {last_progress}")

    # =========================================================================
    # GATE-ALPHA-009: Cleanup FUOTA
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.CLEANUP)
    def test_09_cleanup_fuota(self):
        """GATE-ALPHA-009: Disable FUOTA for device (cleanup)."""
        if self.is_mock:
            pytest.skip("FUOTA cleanup requires real CoreCloud API")

        if not TestGate._plan_id:
            pytest.skip("No plan ID to clean up")

        device_id = self.config.device_id
        plan_id = TestGate._plan_id

        log.info("Disabling FUOTA for device %s (plan %d)...", device_id, plan_id)
        try:
            self.fuota.disable_device(device_id, plan_id)
            log.info("GATE-ALPHA-009 PASS: FUOTA disabled")
        except Exception as e:
            log.warning("Cleanup failed: %s (will retry on exit)", e)

    # =========================================================================
    # GATE-ALPHA-010: Post-FUOTA boot verification
    # =========================================================================

    @pytest.mark.timeout(Timing.GATE.POST_BOOT)
    def test_10_post_fuota_boot(self):
        """GATE-ALPHA-010: Verify device boots after FUOTA."""
        log.info("Power cycling for post-FUOTA verification...")
        self.ctx.fixture.power_off()
        time.sleep(Timing.COMMON.POWER_CYCLE_OFF)
        self.ctx.fixture.power_on()
        time.sleep(Timing.GATE.BOOT_SETTLE)

        avg_current = assert_powered(self.ctx.fixture, min_current_ma=5.0)
        log.info("GATE-ALPHA-010 PASS: Post-FUOTA boot successful (avg current: %.2fmA)", avg_current)
        log.info("=" * 60)
        log.info("GATE COMPLETE - All tests passed")
        log.info("=" * 60)
