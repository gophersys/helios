#!/usr/bin/env python3
"""FUOTA Test - Automated firmware update over the air.

Validates the complete FUOTA workflow:
1. Flash device with base MFG firmware (v0.5.0)
2. Personalize device (generate EC keypair, upload to CoreCloud)
3. Upload target CFW files to CoreCloud
4. Create FUOTA plan and assign device
5. Poll for FUOTA completion (device checks in on LTE-M PSM wake)
6. Verify device reports target firmware version

Requirements:
- MTIB connected with DUT
- VAL_1_0_API_* environment variables set (CoreCloud auth)
- COREOPS_* environment variables (device ID assignment)
- MinIO access for firmware artifacts

Usage:
    pytest tests/fuota/test_fuota.py -v -s \\
        --mtib-addr 10.4.45.33 \\
        --device-snr 09J5

    # Or set env vars:
    MTIB_ADDR=10.4.45.33 DEVICE_SNR=09J5 pytest tests/fuota/test_fuota.py -v -s
"""

import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

import pytest

# Ensure proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/python"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/protocols"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs"))

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================================
# Test Configuration
# ============================================================================

# Firmware versions for FUOTA test
SOURCE_VERSION = "0.5.0"  # Version to flash as base
TARGET_VERSION = "0.5.1"  # Version to FUOTA to
# CFW track suffix (B=Bench, M=Mfg) - must match for FUOTA to work
CFW_TRACK = "-BM"

# MinIO paths for firmware artifacts
MINIO_BUCKET = "concord"
MINIO_V050_BUILD = "firmware/builds/alpha_mfg_fw/cmmk9o90200028785zcfxqlxe"
MINIO_V051_BUILD = "firmware/builds/alpha_mfg_fw/cmmk9o90v00048785vl0v4od5"

# Device type/variant for Alpha B0
DEVICE_TYPE_ID = 2
DEVICE_VARIANT_ID = 3

# Timeouts
FUOTA_TIMEOUT_MINUTES = 90  # LTE-M PSM wake can take up to 60 min


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def firmware_files():
    """Download firmware files from MinIO."""
    from minio import Minio

    # Get MinIO credentials from environment or use staging defaults
    minio_host = os.environ.get("MINIO_ENDPOINT", "127.0.0.1:9000")
    minio_access = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret = os.environ.get("MINIO_SECRET_ACCESS_KEY", "minioadmin-staging")

    client = Minio(minio_host, access_key=minio_access, secret_key=minio_secret, secure=False)

    # Create temp directory for firmware
    tmpdir = Path(tempfile.mkdtemp(prefix="fuota_test_"))

    files = {
        # v0.5.0 hex files (base firmware to flash)
        "app_hex": (f"{MINIO_V050_BUILD}/{SOURCE_VERSION}_no_debug_app_nrf52840.hex", tmpdir / "app_nrf52840.hex"),
        "comms_hex": (f"{MINIO_V050_BUILD}/{SOURCE_VERSION}_no_debug_comms_nrf9151.hex", tmpdir / "comms_nrf9151.hex"),
        # v0.5.1 CFW files (FUOTA target)
        "cfw_108": (f"{MINIO_V051_BUILD}/{TARGET_VERSION}_no_debug_108.{TARGET_VERSION}.cfw", tmpdir / f"108.{TARGET_VERSION}.cfw"),
        "cfw_109": (f"{MINIO_V051_BUILD}/{TARGET_VERSION}_no_debug_109.{TARGET_VERSION}.cfw", tmpdir / f"109.{TARGET_VERSION}.cfw"),
    }

    downloaded = {}
    for key, (remote_path, local_path) in files.items():
        print(f"Downloading {remote_path}...")
        client.fget_object(MINIO_BUCKET, remote_path, str(local_path))
        downloaded[key] = local_path
        print(f"  -> {local_path}")

    yield downloaded

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="module")
def mtib_client(request):
    """Connect to MTIB."""
    from corekinect.mtib_client.v1.client.core import MtibV1Client
    from corekinect.mtib_client.v1.client.config import NetConfig

    mtib_addr = request.config.getoption("--mtib-addr", default="10.4.45.33")

    cfg = MtibV1Client.Config(net=NetConfig(addr=mtib_addr, port=50053))
    client = MtibV1Client(cfg)

    err = client.connect()
    assert err is None, f"Failed to connect to MTIB: {err}"

    yield client

    # Cleanup: power off DUT
    from corekinect.mtib_client.v1.client.types import PowerChannel
    try:
        client.PowerDisable(channel=PowerChannel.DUT)
    except Exception:
        pass


@pytest.fixture(scope="module")
def device_snr(request):
    """Get device SNR from command line."""
    return request.config.getoption("--device-snr", default="09J5")


@pytest.fixture(scope="module")
def device_id_override(request):
    """Optional device ID from --device-id CLI arg (defined in conftest.py)."""
    return request.config.getoption("--device-id", default=None) or os.environ.get("DEVICE_ID")


@pytest.fixture(scope="module")
def fuota_client():
    """Create FUOTA client."""
    from corekinect.test.validation.fuota_client import FuotaClient
    return FuotaClient(api_env="VAL_1_0")


# ============================================================================
# Helper Functions
# ============================================================================

def flash_firmware(client, app_hex: Path, comms_hex: Path):
    """Flash firmware via J-Link through MTIB."""
    from protocols.mtib.mtib_pb2 import HostType
    from corekinect.mtib_client.v1.client.types import PowerChannel, GpioDirection, GpioResistorConfig

    # Power on DUT for flashing (J-Link needs powered target)
    client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioWrite(gpio=0, state=False)
    client.GpioWrite(gpio=1, state=False)
    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)
    time.sleep(2)

    # Upload and flash nRF52840 (APP)
    print(f"Uploading nRF52840 hex: {app_hex.name}")
    err = client.UploadFwFile(str(app_hex), HostType.HOST_TYPE_NRF52840)
    assert err is None, f"nRF52840 upload failed: {err}"

    print(f"Flashing nRF52840...")
    files_list, err = client.ListFwFiles()
    assert err is None, f"ListFwFiles failed: {err}"
    app_file = next((f for f in files_list if "app" in f.name.lower() or "52840" in f.name), None)
    assert app_file is not None, f"Could not find uploaded app file"
    time_ms, err = client.FlashFwFile(app_file, recover=True)
    assert err is None, f"nRF52840 flash failed: {err}"
    print(f"  nRF52840 flashed in {time_ms}ms")

    # Upload and flash nRF9151 (COMMS)
    print(f"Uploading nRF9151 hex: {comms_hex.name}")
    err = client.UploadFwFile(str(comms_hex), HostType.HOST_TYPE_NRF9151)
    assert err is None, f"nRF9151 upload failed: {err}"

    print(f"Flashing nRF9151...")
    files_list, err = client.ListFwFiles()
    assert err is None, f"ListFwFiles failed: {err}"
    comms_file = next((f for f in files_list if "comms" in f.name.lower() or "9151" in f.name), None)
    assert comms_file is not None, f"Could not find uploaded comms file"
    time_ms, err = client.FlashFwFile(comms_file, recover=True)
    assert err is None, f"nRF9151 flash failed: {err}"
    print(f"  nRF9151 flashed in {time_ms}ms")


def power_cycle_dut(client, wait_s: float = 5.0):
    """Power cycle the DUT and wait for boot.

    Uses battery-installed mode (ch0 + ch1) per fixture profile.
    Boot power timeline:
      t=0-3s: DUT boots from ch0 (battery sim), ~65-100mA
      t=4s:   BQ25180 charger takes over, ch0→~0mA, ch1→17-33mA
      t=5s+:  Steady state on ch1
    """
    from corekinect.mtib_client.v1.client.types import PowerChannel, GpioDirection, GpioResistorConfig

    # Power off both channels
    client.PowerDisable(channel=PowerChannel.DUT)
    client.PowerDisable(channel=PowerChannel.CHARGER)
    time.sleep(2)

    # GPIO 0+1 as output LOW — REQUIRED for DUT to boot
    client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioWrite(gpio=0, state=False)
    client.GpioWrite(gpio=1, state=False)

    # Power on both rails (battery_installed=true)
    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)
    time.sleep(wait_s)


def personalize_device(client, snr: str, device_id: Optional[str] = None) -> dict:
    """Personalize device and upload EC public key to CoreCloud.

    The personalizer handles the full sequence:
    1. Power cycle + lock mfg shells (within 8s window)
    2. Read IMEI/ICCIDs from modem via shell
    3. Get device ID from CoreOps (deterministic per SNR)
    4. Generate new EC keypair on device
    5. Upload public key to CoreCloud (b64 format, verified after upload)

    Nothing is hardcoded — all device identity comes from the hardware itself.
    """
    from corekinect.test.validation.device_personalizer import DevicePersonalizer

    personalizer = DevicePersonalizer(
        mtib=client,
        snr=snr,
        known_device_id=device_id,  # Optional fallback if CoreOps unavailable
        db_env="VAL_1_0",
        require_corecloud_key=True,  # FUOTA requires verified key in CoreCloud
    )

    result, err = personalizer.repersonalize(
        power_cycle=True,
        lock_shells=True,
    )

    # FAIL HARD — no point continuing if personalization fails
    assert err is None, f"Personalization FAILED: {err}"
    assert result is not None, "Personalization returned no result"
    assert result.device_id, "No device ID assigned"
    assert result.pub_key_base64, "No public key generated"

    print(f"Personalized: device_id={result.device_id}, key={result.pub_key_base64[:20]}...")

    return {
        "device_id": result.device_id,
        "public_key": result.pub_key_base64,
    }


def upload_cfw_files(fuota_client, cfw_108: Path, cfw_109: Path):
    """Upload CFW files to CoreCloud.

    CFW files must be named with track suffix (e.g., 108.0.5.1-BM.cfw)
    for the FUOTA server to recognize them as valid targets.
    """
    import shutil

    # Rename files with track suffix for upload
    tmpdir = cfw_108.parent
    cfw_108_bm = tmpdir / f"108.{TARGET_VERSION}{CFW_TRACK}.cfw"
    cfw_109_bm = tmpdir / f"109.{TARGET_VERSION}{CFW_TRACK}.cfw"

    shutil.copy(cfw_108, cfw_108_bm)
    shutil.copy(cfw_109, cfw_109_bm)

    print(f"Uploading CFW: {cfw_108_bm.name}")
    fuota_client.upload_cfw(str(cfw_108_bm))

    print(f"Uploading CFW: {cfw_109_bm.name}")
    fuota_client.upload_cfw(str(cfw_109_bm))


def create_fuota_plan(fuota_client, device_id: str, target_version: str) -> int:
    """Create FUOTA plan and assign device."""
    # Ensure device is registered
    print(f"Ensuring device {device_id} is registered...")
    fuota_client.ensure_device_registered(
        device_id=device_id,
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )

    # Clean up existing assignments
    print("Checking for existing FUOTA assignments...")
    resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
    devices = resp.json().get('devicesFound', [])

    for d in devices:
        if d.get('deviceId') == device_id:
            old_plan = d.get('planId')
            print(f"  Device in plan {old_plan}, disabling...")
            fuota_client.disable_device(device_id, old_plan)

    # Create plan
    # CFW targets must include track suffix (e.g., -BM for Bench+Mfg)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stages = [
        {
            "targets": [f"108.{target_version}{CFW_TRACK}", f"109.{target_version}{CFW_TRACK}"],
            "description": f"Stage 1: MFG v{SOURCE_VERSION} -> v{target_version}",
            "isSkippable": False
        }
    ]

    print(f"Creating FUOTA plan: {SOURCE_VERSION} -> {target_version}")
    plan_id = fuota_client.create_plan(
        stages=stages,
        description=f"FUOTA Test {timestamp}",
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )
    print(f"  Plan ID: {plan_id}")

    # Assign device
    print(f"Assigning device {device_id} to plan {plan_id}...")
    result = fuota_client.assign_device(
        plan_id=plan_id,
        device_ids=[device_id],
        max_stage=0,
        enable=True,
    )
    print(f"  Assignment result: {result}")

    # Verify assignment
    resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
    devices = resp.json().get('devicesFound', [])

    for d in devices:
        if d.get('deviceId') == device_id:
            assert d.get('planId') == plan_id, f"Device not assigned to plan {plan_id}"
            assert d.get('enableFuota') is True, "Device FUOTA not enabled"
            print(f"  Verified: planId={d.get('planId')}, enabled={d.get('enableFuota')}")
            break
    else:
        pytest.fail(f"Device {device_id} not found in FUOTA settings after assignment")

    return plan_id


def wait_for_fuota_completion(fuota_client, device_id: str, timeout_minutes: int = 90) -> bool:
    """Wait for FUOTA to complete.

    Returns True if FUOTA completed successfully, False otherwise.
    """
    start_time = time.time()
    timeout_s = timeout_minutes * 60
    poll_interval = 60  # Check every minute

    print(f"\nWaiting for FUOTA completion (timeout: {timeout_minutes} min)...")
    print("Device will check in during LTE-M PSM wake cycle (15-60 min)")

    last_status = None

    while time.time() - start_time < timeout_s:
        # Check progress
        resp = fuota_client._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={device_id}"
        )

        if resp.status_code == 200:
            prog = resp.json()
            if prog:
                state = prog.get('state', 'unknown')
                pct = prog.get('percentComplete', 0)
                status = f"state={state}, progress={pct}%"

                if status != last_status:
                    elapsed = (time.time() - start_time) / 60
                    print(f"  [{elapsed:.1f}m] FUOTA: {status}")
                    last_status = status

                # Check for completion
                if state.lower() == 'completed' and pct == 100:
                    print("  FUOTA COMPLETED!")
                    return True

                # Check for failure
                if state.lower() in ('failed', 'error', 'aborted'):
                    print(f"  FUOTA FAILED: {state}")
                    return False

        elif resp.status_code == 404:
            # No active transfer yet - device hasn't checked in
            elapsed = (time.time() - start_time) / 60
            if last_status != "waiting":
                print(f"  [{elapsed:.1f}m] Waiting for device check-in...")
                last_status = "waiting"

        time.sleep(poll_interval)

    print(f"  FUOTA TIMEOUT after {timeout_minutes} minutes")
    return False


def verify_firmware_version(fuota_client, device_id: str, expected_version: str) -> bool:
    """Verify device reports expected firmware version.

    Checks CoreCloud device status for firmware version.
    """
    # Query device status from CoreCloud
    resp = fuota_client._api_request(
        "GET", "System/Devices/Status",
        json={"deviceIds": [device_id]}
    )

    if resp.status_code != 200:
        print(f"Failed to query device status: {resp.status_code}")
        return False

    data = resp.json()
    devices = data.get('devices', [])

    for d in devices:
        if d.get('deviceId') == device_id:
            # Check firmware version fields
            app_version = d.get('appFirmwareVersion', '')
            comms_version = d.get('commsFirmwareVersion', '')

            print(f"Device firmware: app={app_version}, comms={comms_version}")

            # Both should match target version
            if expected_version in str(app_version) and expected_version in str(comms_version):
                return True
            else:
                print(f"Version mismatch: expected {expected_version}")
                return False

    print(f"Device {device_id} not found in status response")
    return False


# ============================================================================
# Tests
# ============================================================================

class TestFuota:
    """FUOTA validation tests."""

    @pytest.mark.order(1)
    def test_flash_base_firmware(self, mtib_client, firmware_files):
        """Flash v0.5.0 base firmware to device."""
        flash_firmware(
            mtib_client,
            firmware_files["app_hex"],
            firmware_files["comms_hex"],
        )

        # Power cycle and verify boot
        power_cycle_dut(mtib_client, wait_s=5)

        # Verify boot via total current (ch0 + ch1)
        # After charger takeover (~4s), ch0→~0mA and ch1→17-33mA
        from corekinect.mtib_client.v1.client.types import PowerChannel
        r0, err0 = mtib_client.PowerRead(channel=PowerChannel.DUT)
        r1, err1 = mtib_client.PowerRead(channel=PowerChannel.CHARGER)
        assert err0 is None, f"PowerRead ch0 failed: {err0}"
        assert err1 is None, f"PowerRead ch1 failed: {err1}"

        total_ma = r0.current_ma + r1.current_ma
        assert total_ma > 5, f"DUT not booted: total current={total_ma:.1f}mA (ch0={r0.current_ma:.1f}, ch1={r1.current_ma:.1f})"

        print(f"Device booted: ch0={r0.current_ma:.1f}mA ch1={r1.current_ma:.1f}mA total={total_ma:.1f}mA")

    @pytest.mark.order(2)
    def test_personalize_device(self, mtib_client, device_snr, device_id_override):
        """Personalize device and verify CoreCloud registration."""
        result = personalize_device(mtib_client, device_snr, device_id=device_id_override)

        # Store for subsequent tests
        pytest.device_id = result["device_id"]

        print(f"Device personalized: ID={result['device_id']}")

    @pytest.mark.order(3)
    def test_upload_cfw(self, fuota_client, firmware_files):
        """Upload target CFW files to CoreCloud."""
        upload_cfw_files(
            fuota_client,
            firmware_files["cfw_108"],
            firmware_files["cfw_109"],
        )
        print("CFW files uploaded to CoreCloud")

    @pytest.mark.order(4)
    def test_create_fuota_plan(self, fuota_client):
        """Create FUOTA plan and assign device."""
        plan_id = create_fuota_plan(
            fuota_client,
            device_id=pytest.device_id,
            target_version=TARGET_VERSION,
        )

        # Store for monitoring
        pytest.fuota_plan_id = plan_id

        print(f"FUOTA plan created: {plan_id}")

    @pytest.mark.order(5)
    @pytest.mark.timeout(FUOTA_TIMEOUT_MINUTES * 60 + 60)  # Add buffer
    def test_wait_for_fuota(self, fuota_client):
        """Wait for FUOTA to complete."""
        success = wait_for_fuota_completion(
            fuota_client,
            device_id=pytest.device_id,
            timeout_minutes=FUOTA_TIMEOUT_MINUTES,
        )

        assert success, "FUOTA did not complete successfully"

    @pytest.mark.order(6)
    def test_verify_firmware_version(self, fuota_client):
        """Verify device reports target firmware version."""
        verified = verify_firmware_version(
            fuota_client,
            device_id=pytest.device_id,
            expected_version=TARGET_VERSION,
        )

        assert verified, f"Device did not report firmware v{TARGET_VERSION}"
        print(f"Device successfully updated to v{TARGET_VERSION}")


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_addoption(parser):
    """Add custom command line options.

    NOTE: --device-id is already defined in conftest.py — don't re-add here.
    """
    parser.addoption(
        "--mtib-addr",
        action="store",
        default=os.environ.get("MTIB_ADDR", "10.4.45.33"),
        help="MTIB address",
    )
    parser.addoption(
        "--device-snr",
        action="store",
        default=os.environ.get("DEVICE_SNR", "09J5"),
        help="Device serial number (J-Link probe SNR)",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
