#!/usr/bin/env python3
"""
Stage 4 FUOTA Validation Test - Step by Step

This script runs FUOTA validation on the active MTIB bench, with detailed
logging of each step. Can be run interactively or automated.

Usage:
    # Interactive mode (pause between steps)
    python scripts/fuota_stage4_test.py --interactive

    # Automated mode
    python scripts/fuota_stage4_test.py

    # Skip CFW upload (already on server)
    python scripts/fuota_stage4_test.py --skip-upload

Environment:
    Requires VAL_1_0_API_* env vars in .env
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add libs to path
sys.path.insert(0, str(Path(__file__).parent.parent / "libs" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs" / "protocols"))
sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from dotenv import load_dotenv
load_dotenv(override=False)

from corekinect.utils import Logger
from corekinect.test.validation.fuota_client import FuotaClient
from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import HostType

# Configuration
DEVICE_ID = "70B3D584C01E1FCC"  # bench-33 DUT
MTIB_ADDR = "10.4.45.33"
MTIB_PORT = 50053

# CFW files for MFG firmware v0.5.1
CFW_DIR = Path(__file__).parent.parent / "apps/firmware/products/alpha/artifacts/cfw"
MFG_CFW_FILES = [
    CFW_DIR / "108.0.5.1-BMD.cfw",  # comms
    CFW_DIR / "109.0.5.1-BMD.cfw",  # app
]

log = Logger(log_name="fuota_test")


def step(name: str, interactive: bool = False):
    """Print step header and optionally wait for user."""
    print()
    print("=" * 60)
    print(f"STEP: {name}")
    print("=" * 60)
    if interactive:
        input("Press Enter to continue...")


def check_device_status(api: CoreCloudRestInterface) -> dict:
    """Get current device status from CoreCloud."""
    resp = api.request("GET", "/System/Devices/Status", json={"deviceIds": [DEVICE_ID]})
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get device status: {resp.status_code}")

    data = resp.json()
    devices = data.get("devices", [])
    if not devices:
        raise RuntimeError(f"Device {DEVICE_ID} not found in CoreCloud")

    return devices[0]


def get_uart_snapshot(mtib: MtibV1Client, target: HostType, duration: float = 2.0) -> str:
    """Capture UART output for a duration."""
    import threading
    import queue

    output_queue = queue.Queue()
    stop_event = threading.Event()

    def reader():
        def req_gen():
            from mtib.mtib_pb2 import UartStreamRequest
            yield UartStreamRequest(target=target)
            while not stop_event.is_set():
                time.sleep(0.05)
                yield UartStreamRequest(target=target)

        try:
            for resp in mtib.UartStream(target, req_gen()):
                if resp.data:
                    output_queue.put(resp.data.decode('utf-8', errors='replace'))
                if stop_event.is_set():
                    break
        except Exception as e:
            output_queue.put(f"[ERROR: {e}]")

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(duration)
    stop_event.set()
    thread.join(timeout=1.0)

    output = []
    while not output_queue.empty():
        output.append(output_queue.get_nowait())

    return "".join(output)


def run_fuota_test(args):
    """Main FUOTA test sequence."""
    interactive = args.interactive
    skip_upload = args.skip_upload

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_name = f"Alpha B0 Stage4 FUOTA Test — {timestamp}"

    print()
    print("=" * 60)
    print("STAGE 4 FUOTA VALIDATION TEST")
    print("=" * 60)
    print(f"Device ID:  {DEVICE_ID}")
    print(f"MTIB:       {MTIB_ADDR}:{MTIB_PORT}")
    print(f"Plan name:  {plan_name}")
    print(f"CFW files:  {[f.name for f in MFG_CFW_FILES]}")
    print(f"Mode:       {'Interactive' if interactive else 'Automated'}")
    print()

    # Verify CFW files exist
    for cfw in MFG_CFW_FILES:
        if not cfw.exists():
            log.error(f"CFW file not found: {cfw}")
            return 1

    # Initialize clients
    step("1. Initialize Clients", interactive)

    log.info("Connecting to CoreCloud...")
    api = CoreCloudRestInterface(env_namespace="VAL_1_0", test_auth_on_enter=True)
    api.__enter__()
    log.info("CoreCloud connected")

    log.info("Initializing FUOTA client...")
    fuota = FuotaClient(api_env="VAL_1_0")
    log.info("FUOTA client ready")

    log.info("Connecting to MTIB...")
    mtib_cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_ADDR, port=MTIB_PORT))
    mtib = MtibV1Client(mtib_cfg)
    err = mtib.connect()
    if err:
        log.error(f"MTIB connection failed: {err}")
        return 1
    log.info("MTIB connected")

    try:
        # Check initial device status
        step("2. Check Device Status", interactive)

        dev_status = check_device_status(api)
        boot_info = dev_status.get("bootInfo", {})
        log.info(f"Last boot: {boot_info.get('timeOfBoot')}")
        log.info(f"Boot reason: {boot_info.get('bootReason')}")

        # Check current FUOTA settings
        settings = fuota.get_device_settings(DEVICE_ID)
        if settings:
            log.info(f"Current FUOTA plan: {settings.get('planId')}")
            log.info(f"FUOTA enabled: {settings.get('enableFuota')}")
        else:
            log.info("Device has no FUOTA assignment")

        # Upload CFW files (if needed)
        step("3. Upload CFW Files", interactive)

        if skip_upload:
            log.info("Skipping CFW upload (--skip-upload)")
        else:
            for cfw in MFG_CFW_FILES:
                log.info(f"Uploading {cfw.name}...")
                try:
                    fuota.upload_cfw(str(cfw))
                    log.info(f"Uploaded {cfw.name}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        log.info(f"{cfw.name} already on server")
                    else:
                        raise

        # Create FUOTA plan
        step("4. Create FUOTA Plan", interactive)

        # Single stage with both CFW targets
        stages = [
            {
                "targets": ["108.0.5.1-BMD", "109.0.5.1-BMD"],
                "description": "MFG firmware v0.5.1 (comms + app)",
                "isSkippable": False,
            }
        ]

        log.info(f"Creating plan: {plan_name}")
        plan_id = fuota.create_plan(
            stages=stages,
            description=plan_name,
            device_type_id=2,    # Alpha
            device_variant_id=3,  # B0
        )
        log.info(f"Plan created: ID={plan_id}")

        # Assign device to plan
        step("5. Assign Device to Plan", interactive)

        log.info(f"Assigning device {DEVICE_ID} to plan {plan_id}...")
        result = fuota.assign_device(
            plan_id=plan_id,
            device_ids=[DEVICE_ID],
            max_stage=0,  # 0-indexed, so stage 0 = first stage
            enable=True,
        )
        log.info(f"Device assigned: {result}")

        # Verify assignment
        settings = fuota.get_device_settings(DEVICE_ID)
        log.info(f"Verified - Plan: {settings.get('planId')}, Enabled: {settings.get('enableFuota')}")

        # Power cycle to trigger FUOTA check
        step("6. Power Cycle Device", interactive)

        log.info("Disabling power...")
        mtib.PowerDisable(channel=0)
        time.sleep(2)

        log.info("Enabling power (4.5V)...")
        mtib.PowerEnable(channel=0, voltage_v=4.5)
        time.sleep(5)  # Wait for boot

        # Check power
        pwr, err = mtib.DutPowerRead()
        if err:
            log.warning(f"Power read error: {err}")
        else:
            log.info(f"Power: {pwr.current_ma:.1f}mA @ {pwr.voltage_v:.2f}V")

        # Monitor FUOTA progress
        step("7. Monitor FUOTA Progress", interactive)

        log.info("Waiting for device to check in and start FUOTA...")
        log.info("This may take 1-5 minutes depending on device sleep cycle...")

        max_wait = 300  # 5 minutes
        poll_interval = 10
        start_time = time.time()

        last_progress = None
        while time.time() - start_time < max_wait:
            elapsed = int(time.time() - start_time)

            # Check FUOTA progress
            progress = fuota.get_progress(DEVICE_ID)
            if progress and progress != last_progress:
                log.info(f"[{elapsed}s] FUOTA progress: {json.dumps(progress, indent=2)}")
                last_progress = progress

                # Check if complete
                if progress.get("isComplete"):
                    log.info("FUOTA COMPLETE!")
                    break
            else:
                log.info(f"[{elapsed}s] Waiting for FUOTA activity...")

            time.sleep(poll_interval)
        else:
            log.warning("FUOTA did not complete within timeout")

        # Check final device status
        step("8. Verify Final State", interactive)

        dev_status = check_device_status(api)
        boot_info = dev_status.get("bootInfo", {})
        log.info(f"Final boot time: {boot_info.get('timeOfBoot')}")
        log.info(f"Final boot reason: {boot_info.get('bootReason')}")

        # Get UART output to see firmware version
        log.info("Capturing UART output...")
        app_uart = get_uart_snapshot(mtib, HostType.HOST_TYPE_NRF52840, duration=3.0)
        if app_uart:
            log.info(f"APP UART:\n{app_uart[:500]}")

        # Disable FUOTA for device (cleanup)
        step("9. Cleanup - Disable FUOTA", interactive)

        log.info("Disabling FUOTA for device...")
        fuota.disable_device(DEVICE_ID, plan_id)
        log.info("FUOTA disabled")

        print()
        print("=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print(f"Plan ID: {plan_id}")
        print(f"Device: {DEVICE_ID}")
        print("Review logs above for FUOTA progress")
        print()

        return 0

    except Exception as e:
        log.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        api.__exit__(None, None, None)
        mtib.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Stage 4 FUOTA Validation Test")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Pause between steps for manual verification")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip CFW upload (use if already on server)")
    args = parser.parse_args()

    return run_fuota_test(args)


if __name__ == "__main__":
    sys.exit(main())
