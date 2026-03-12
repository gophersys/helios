#!/usr/bin/env python3
"""Run FUOTA test 5 consecutive times with timing collection.

Each run:
1. Flash base firmware (0.5.1)
2. Personalize device
3. Upload CFW files
4. Create FUOTA plan
5. Wait for FUOTA delivery (both 108 and 109)
6. Power cycle and verify 0.5.2

Collects timing for each phase and compares across runs.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/python"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/protocols"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs"))

import urllib3
urllib3.disable_warnings()

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import PowerChannel, GpioDirection, GpioResistorConfig, HostType
from corekinect.test.validation.fuota_client import FuotaClient
from corekinect.test.validation.device_personalizer import DevicePersonalizer

# Config
MTIB_ADDR = os.environ.get("MTIB_ADDR", "10.4.45.33")
DEVICE_SNR = os.environ.get("DEVICE_SNR", "09J5")
DEVICE_ID = os.environ.get("DEVICE_ID", "70B3D584C01E1FCC")
DEVICE_IMEI = os.environ.get("DEVICE_IMEI", "355025931735979")

SOURCE_VERSION = "0.5.1"
TARGET_VERSION = "0.5.2"
CFW_TRACK = "-BM"

LOCAL_ARTIFACTS = Path("/workspaces/concord/apps/firmware/products/alpha/artifacts/alpha_mfg_fw/alpha_b0")

DEVICE_TYPE_ID = 2
DEVICE_VARIANT_ID = 3

NUM_RUNS = 5


def get_mtib_client():
    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_ADDR, port=50053))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        raise Exception(f"MTIB connect failed: {err}")
    return client


def get_fuota_client():
    return FuotaClient()


def power_off(client):
    client.PowerDisable(channel=PowerChannel.DUT)
    client.PowerDisable(channel=PowerChannel.CHARGER)
    time.sleep(2)


def power_on(client):
    for gpio in (0, 1):
        client.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.GpioWrite(gpio, False)
    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)


def flash_firmware(client, app_hex: Path, comms_hex: Path):
    """Flash firmware via J-Link."""
    from corekinect.mtib_client.v1.client.types import FwFileInfo

    # Upload files to MTIB
    files_before = {f.name for f in client.ListFwFiles()[0]}

    with open(app_hex, 'rb') as f:
        client.UploadFwFile(app_hex.name, f.read(), HostType.HOST_TYPE_NRF52840)
    with open(comms_hex, 'rb') as f:
        client.UploadFwFile(comms_hex.name, f.read(), HostType.HOST_TYPE_NRF9151)

    # Power on for flashing
    power_on(client)
    time.sleep(2)

    # Get programmer
    programmers, err = client.ListProgrammers()
    if err or not programmers:
        raise Exception(f"No programmers found: {err}")

    probe_snr = programmers[0].serial_number

    # Flash APP (nRF52840)
    result, err = client.FlashFirmware(
        target=HostType.HOST_TYPE_NRF52840,
        file_name=app_hex.name,
        probe_serial=probe_snr,
    )
    if err:
        raise Exception(f"APP flash failed: {err}")

    # Flash COMMS (nRF9151)
    result, err = client.FlashFirmware(
        target=HostType.HOST_TYPE_NRF9151,
        file_name=comms_hex.name,
        probe_serial=probe_snr,
    )
    if err:
        raise Exception(f"COMMS flash failed: {err}")

    # Cleanup uploaded files
    files_after, _ = client.ListFwFiles()
    for f in files_after:
        if f.name not in files_before:
            client.DeleteFwFile(FwFileInfo(name=f.name, target=f.target))


def personalize_device(client):
    """Personalize device and upload key to CoreCloud."""
    personalizer = DevicePersonalizer(
        mtib_client=client,
        device_snr=DEVICE_SNR,
        imei=DEVICE_IMEI,
        iccids=None,  # Not needed for FUOTA
    )
    result = personalizer.personalize()
    return result


def upload_cfw_files(fuota_client, cfw_108: Path, cfw_109: Path):
    """Upload CFW files to CoreCloud."""
    with open(cfw_108, 'rb') as f:
        fuota_client.upload_cfw(cfw_108.name, f.read())
    with open(cfw_109, 'rb') as f:
        fuota_client.upload_cfw(cfw_109.name, f.read())


def create_fuota_plan(fuota_client, device_id: str, target_version: str) -> int:
    """Create FUOTA plan and assign device."""
    # Ensure registered
    fuota_client.ensure_device_registered(
        device_id=device_id,
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )

    # Remove from any existing plan
    settings = fuota_client.get_device_settings([device_id])
    for d in settings.get('devicesFound', []):
        if d.get('deviceId') == device_id and d.get('planId'):
            fuota_client.assign_device(d['planId'], [device_id], max_stage=0, enable=False)

    # Create plan
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stages = [{
        "targets": [f"108.{target_version}{CFW_TRACK}", f"109.{target_version}{CFW_TRACK}"],
        "description": f"FUOTA {SOURCE_VERSION} -> {target_version}",
        "isSkippable": False
    }]

    plan_id = fuota_client.create_plan(
        stages=stages,
        description=f"5x Test Run {timestamp}",
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )

    # Assign device
    fuota_client.assign_device(plan_id, [device_id], max_stage=0, enable=True)

    return plan_id


def wait_for_fuota(fuota_client, device_id: str, timeout_minutes: int = 30) -> dict:
    """Wait for FUOTA and return timing info."""
    start = time.time()
    completed = set()
    timing = {
        "108_start": None, "108_end": None,
        "109_start": None, "109_end": None,
    }

    poll_interval = 5
    timeout_s = timeout_minutes * 60

    while time.time() - start < timeout_s:
        resp = fuota_client._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={device_id}"
        )

        if resp.status_code == 200:
            p = resp.json()
            ver = p.get('version', '')
            pct = p.get('percentComplete', 0)

            # Track timing
            if '108' in ver:
                if timing['108_start'] is None:
                    timing['108_start'] = time.time() - start
                if pct >= 100 and '108' not in completed:
                    timing['108_end'] = time.time() - start
                    completed.add('108')
                    print(f"  108 complete: {timing['108_end']:.1f}s")
            elif '109' in ver:
                if timing['109_start'] is None:
                    timing['109_start'] = time.time() - start
                if pct >= 100 and '109' not in completed:
                    timing['109_end'] = time.time() - start
                    completed.add('109')
                    print(f"  109 complete: {timing['109_end']:.1f}s")

            elapsed = time.time() - start
            print(f"  [{elapsed:.0f}s] {ver}: {pct:.1f}%")

            if '108' in completed and '109' in completed:
                timing['total'] = time.time() - start
                return timing

        elif resp.status_code == 404:
            if '108' in completed and '109' not in completed:
                print(f"  [{time.time()-start:.0f}s] Waiting for 109 to start...")

        time.sleep(poll_interval)

    raise Exception(f"FUOTA timeout after {timeout_minutes} min")


def verify_firmware_version(client, expected_version: str) -> bool:
    """Power cycle and verify firmware via UART boot logs."""
    import threading
    from libs.protocols.mtib.mtib_pb2 import UartStreamRequest

    power_off(client)
    time.sleep(2)

    # Capture UART
    lines = []
    stop = threading.Event()

    def capture():
        def req_gen():
            yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9151)
            while not stop.is_set():
                time.sleep(0.03)
                yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9151)
        try:
            for resp in client.UartStream(HostType.HOST_TYPE_NRF9151, req_gen()):
                if stop.is_set():
                    break
                if resp.data:
                    lines.extend(resp.data.decode('utf-8', errors='replace').split('\n'))
        except:
            pass

    t = threading.Thread(target=capture, daemon=True)
    t.start()
    time.sleep(0.5)

    power_on(client)
    time.sleep(15)
    stop.set()
    time.sleep(1)

    # Check version
    import re
    for line in lines:
        m = re.search(r'application\s+108\s+launched.*Version\s+(\d+\.\d+\.\d+)', line)
        if m:
            found = m.group(1)
            print(f"  Found COMMS version: {found}")
            return found == expected_version

    print(f"  Could not detect version from {len(lines)} lines")
    return False


def run_single_test(run_num: int) -> dict:
    """Run a single FUOTA test and return timing."""
    print(f"\n{'='*60}")
    print(f"RUN {run_num}/{NUM_RUNS}")
    print(f"{'='*60}")

    timing = {"run": run_num, "start": datetime.now().isoformat()}

    mtib = get_mtib_client()
    fuota = get_fuota_client()

    try:
        # 1. Flash base firmware
        print(f"\n[1/6] Flashing base firmware v{SOURCE_VERSION}...")
        t0 = time.time()
        flash_firmware(
            mtib,
            LOCAL_ARTIFACTS / f"{SOURCE_VERSION}_app_nrf52840.hex",
            LOCAL_ARTIFACTS / f"{SOURCE_VERSION}_comms_nrf9151.hex",
        )
        timing['flash_s'] = time.time() - t0
        print(f"  Flash complete: {timing['flash_s']:.1f}s")

        # 2. Personalize
        print(f"\n[2/6] Personalizing device...")
        t0 = time.time()
        power_off(mtib)
        time.sleep(2)
        power_on(mtib)
        time.sleep(5)
        result = personalize_device(mtib)
        timing['personalize_s'] = time.time() - t0
        print(f"  Personalize complete: {timing['personalize_s']:.1f}s")
        print(f"  Device ID: {result['device_id']}")

        # 3. Upload CFW (skip if already uploaded)
        print(f"\n[3/6] Uploading CFW files...")
        t0 = time.time()
        try:
            upload_cfw_files(
                fuota,
                LOCAL_ARTIFACTS / f"108.{TARGET_VERSION}{CFW_TRACK}.cfw",
                LOCAL_ARTIFACTS / f"109.{TARGET_VERSION}{CFW_TRACK}.cfw",
            )
        except Exception as e:
            if "400" in str(e):
                print("  CFW already uploaded (OK)")
            else:
                raise
        timing['upload_cfw_s'] = time.time() - t0
        print(f"  Upload complete: {timing['upload_cfw_s']:.1f}s")

        # 4. Create plan
        print(f"\n[4/6] Creating FUOTA plan...")
        t0 = time.time()
        plan_id = create_fuota_plan(fuota, DEVICE_ID, TARGET_VERSION)
        timing['create_plan_s'] = time.time() - t0
        print(f"  Plan {plan_id} created: {timing['create_plan_s']:.1f}s")

        # 5. Power cycle to trigger check-in
        print(f"\n[5/6] Power cycling for FUOTA...")
        power_off(mtib)
        time.sleep(2)
        power_on(mtib)

        # Wait for FUOTA
        print("  Waiting for FUOTA delivery...")
        fuota_timing = wait_for_fuota(fuota, DEVICE_ID, timeout_minutes=20)
        timing['fuota_108_s'] = fuota_timing.get('108_end', 0) - fuota_timing.get('108_start', 0) if fuota_timing.get('108_end') else None
        timing['fuota_109_s'] = fuota_timing.get('109_end', 0) - fuota_timing.get('109_start', 0) if fuota_timing.get('109_end') else None
        timing['fuota_total_s'] = fuota_timing.get('total', 0)
        print(f"  FUOTA complete: {timing['fuota_total_s']:.1f}s total")

        # 6. Verify
        print(f"\n[6/6] Verifying firmware v{TARGET_VERSION}...")
        t0 = time.time()
        verified = verify_firmware_version(mtib, TARGET_VERSION)
        timing['verify_s'] = time.time() - t0

        if not verified:
            raise Exception(f"Firmware verification failed - expected v{TARGET_VERSION}")

        print(f"  Verified: {timing['verify_s']:.1f}s")

        timing['success'] = True
        timing['end'] = datetime.now().isoformat()

    except Exception as e:
        timing['success'] = False
        timing['error'] = str(e)
        print(f"\nERROR: {e}")

    return timing


def main():
    print("="*60)
    print("FUOTA 5x CONSECUTIVE TEST")
    print(f"Source: v{SOURCE_VERSION} -> Target: v{TARGET_VERSION}")
    print(f"Device: {DEVICE_ID} (SNR: {DEVICE_SNR})")
    print("="*60)

    results = []

    for i in range(1, NUM_RUNS + 1):
        timing = run_single_test(i)
        results.append(timing)

        # Save intermediate results
        with open('/tmp/fuota_5x_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        if not timing.get('success'):
            print(f"\n*** RUN {i} FAILED - stopping ***")
            break

        print(f"\nRun {i} complete. Waiting 10s before next run...")
        time.sleep(10)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    successes = [r for r in results if r.get('success')]
    failures = [r for r in results if not r.get('success')]

    print(f"Successes: {len(successes)}/{len(results)}")
    print(f"Failures: {len(failures)}")

    if successes:
        print("\nTiming (seconds):")
        print(f"{'Phase':<20} {'Min':>8} {'Max':>8} {'Avg':>8}")
        print("-"*48)

        for phase in ['flash_s', 'personalize_s', 'fuota_total_s', 'verify_s']:
            vals = [r.get(phase, 0) for r in successes if r.get(phase)]
            if vals:
                print(f"{phase:<20} {min(vals):>8.1f} {max(vals):>8.1f} {sum(vals)/len(vals):>8.1f}")

    print(f"\nResults saved to /tmp/fuota_5x_results.json")

    return len(failures) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
