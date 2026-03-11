#!/usr/bin/env python3
"""FUOTA Setup Script - Automated Stage 4 FUOTA workflow.

Sets up a device for FUOTA testing:
1. Connects to MTIB
2. (Optional) Flashes MFG firmware
3. Power cycles and verifies boot
4. Personalizes device
5. Uploads CFW files to CoreCloud
6. Cleans up existing FUOTA assignments
7. Creates FUOTA plan
8. Assigns device to plan
9. Verifies setup

Usage:
    # Full setup with flash
    python fuota_setup.py --mtib 10.4.45.33 --snr 09J5 --flash

    # Setup without flash (device already has MFG firmware)
    python fuota_setup.py --mtib 10.4.45.33 --snr 09J5

    # Specify device identity manually
    python fuota_setup.py --mtib 10.4.45.33 --snr 09J5 \
        --device-id 70B3D584C01E1DDD \
        --imei 355025931651952 \
        --iccids "89148000009808560116,89457300000037581199"

Environment variables (from K8s secret corecloud-validation):
    VAL_1_0_API_KEY
    VAL_1_0_API_AUTH_SERVER_HOST_NAME
    VAL_1_0_API_REST_SERVER_HOST_NAME
    VAL_1_0_API_AUTH_USERNAME
    VAL_1_0_API_AUTH_PASSWORD
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Ensure proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/python"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/protocols"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs"))

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Default paths
DEFAULT_CFW_DIR = Path(__file__).parent.parent.parent.parent.parent / "apps/firmware/products/alpha/artifacts/cfw"
DEFAULT_FIXTURE_PROFILE = Path(__file__).parent.parent / "fixtures/alpha_b0.json"


def log(msg: str, level: str = "INFO"):
    """Simple logging with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    symbol = {"INFO": " ", "OK": "+", "WARN": "!", "ERR": "X"}[level]
    print(f"[{ts}] [{symbol}] {msg}")


def load_fixture_profile(path: Path) -> dict:
    """Load fixture profile JSON."""
    with open(path) as f:
        return json.load(f)


def connect_mtib(addr: str, port: int = 50053):
    """Connect to MTIB."""
    from corekinect.mtib_client.v1.client.core import MtibV1Client
    from corekinect.mtib_client.v1.client.config import NetConfig

    log(f"Connecting to MTIB {addr}:{port}...")
    cfg = MtibV1Client.Config(net=NetConfig(addr=addr, port=port))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        raise RuntimeError(f"MTIB connect failed: {err}")
    log("MTIB connected", "OK")
    return client


def power_cycle(client, wait_s: float = 5.0):
    """Power cycle the DUT."""
    from corekinect.mtib_client.v1.client.types import (
        PowerChannel, GpioDirection, GpioResistorConfig
    )

    log("Power cycling DUT...")

    # Power off both channels
    client.PowerDisable(channel=PowerChannel.DUT)
    client.PowerDisable(channel=PowerChannel.CHARGER)
    time.sleep(2)

    # Configure GPIO 0+1 as output LOW
    client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioWrite(gpio=0, state=False)
    client.GpioWrite(gpio=1, state=False)

    # Power on both channels
    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)

    log(f"Waiting {wait_s}s for boot...")
    time.sleep(wait_s)

    # Verify power draw
    result, err = client.DutPowerRead()
    if err:
        log(f"Power read error: {err}", "WARN")
    else:
        log(f"Current: {result.current_ma:.1f}mA", "OK")


def flash_firmware(client, app_hex: Path, comms_hex: Path):
    """Flash MFG firmware via J-Link."""
    log(f"Flashing nRF52840: {app_hex.name}...")
    err = client.alpha_flash_nrf52840(str(app_hex))
    if err:
        raise RuntimeError(f"nRF52840 flash failed: {err}")
    log("nRF52840 flashed", "OK")

    log(f"Flashing nRF9151: {comms_hex.name}...")
    err = client.alpha_flash_nrf9151(str(comms_hex))
    if err:
        raise RuntimeError(f"nRF9151 flash failed: {err}")
    log("nRF9151 flashed", "OK")


def personalize_device(
    client,
    snr: str,
    device_id: Optional[str] = None,
    imei: Optional[str] = None,
    iccids: Optional[List[str]] = None,
    coreops_url: str = "http://coreops-proxy"
) -> dict:
    """Personalize device and upload keys to CoreCloud."""
    from corekinect.test.validation.device_personalizer import DevicePersonalizer

    log(f"Personalizing device SNR={snr}...")

    personalizer = DevicePersonalizer(
        mtib=client,
        coreops_url=coreops_url,
        device_snr=snr,
        device_id=device_id,
        device_imei=imei,
        device_iccids=iccids or [],
    )

    result = personalizer.personalize()
    log(f"Device ID: {result.device_id}", "OK")
    log(f"Public key uploaded", "OK")

    return {
        "device_id": result.device_id,
        "public_key": result.public_key_b64,
    }


def setup_fuota(
    device_id: str,
    source_version: str = "0.5.0",
    target_version: str = "0.5.1",
    cfw_dir: Path = DEFAULT_CFW_DIR,
) -> int:
    """Set up FUOTA plan and assign device."""
    from corekinect.test.validation.fuota_client import FuotaClient

    fuota = FuotaClient(api_env="VAL_1_0")

    # Step 1: Ensure device is registered
    log("Ensuring device is registered in CoreCloud...")
    fuota.ensure_device_registered(device_id, device_type_id=2, device_variant_id=3)
    log("Device registered", "OK")

    # Step 2: Upload CFW files
    target_cfws = [
        cfw_dir / f"108.{target_version}-BMD.cfw",
        cfw_dir / f"109.{target_version}-BMD.cfw",
    ]
    for cfw_path in target_cfws:
        if cfw_path.exists():
            log(f"Uploading CFW: {cfw_path.name}...")
            fuota.upload_cfw(str(cfw_path))
            log(f"CFW uploaded: {cfw_path.name}", "OK")
        else:
            log(f"CFW not found: {cfw_path}", "WARN")

    # Step 3: Check for existing assignment
    log("Checking existing FUOTA assignments...")
    resp = fuota._singleton_request("GET", "firmwareupdates/settings/devices")
    devices = resp.json().get('devicesFound', [])

    for d in devices:
        if d.get('deviceId') == device_id:
            old_plan = d.get('planId')
            log(f"Device in plan {old_plan}, disabling...", "WARN")
            fuota.disable_device(device_id, old_plan)
            log("Previous assignment disabled", "OK")
            break

    # Step 4: Create new plan
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stages = [
        {
            "targets": [f"108.{target_version}-BMD", f"109.{target_version}-BMD"],
            "description": f"Stage 1: MFG v{source_version} → v{target_version}",
            "isSkippable": False
        }
    ]

    log("Creating FUOTA plan...")
    plan_id = fuota.create_plan(
        stages=stages,
        description=f"Stage4 FUOTA {timestamp}",
        device_type_id=2,
        device_variant_id=3
    )
    log(f"Plan created: ID={plan_id}", "OK")

    # Step 5: Assign device
    log(f"Assigning device {device_id} to plan {plan_id}...")
    result = fuota.assign_device(
        plan_id=plan_id,
        device_ids=[device_id],
        max_stage=0,
        enable=True
    )
    log(f"Device assigned: {result}", "OK")

    # Step 6: Verify
    log("Verifying assignment...")
    resp = fuota._singleton_request("GET", "firmwareupdates/settings/devices")
    devices = resp.json().get('devicesFound', [])

    for d in devices:
        if d.get('deviceId') == device_id:
            log(f"Verified: plan={d.get('planId')} enabled={d.get('enableFuota')}", "OK")
            break
    else:
        log("Device not found in settings (may need time to sync)", "WARN")

    return plan_id


def main():
    parser = argparse.ArgumentParser(description="FUOTA Setup Script")
    parser.add_argument("--mtib", required=True, help="MTIB address")
    parser.add_argument("--snr", required=True, help="Device SNR")
    parser.add_argument("--device-id", help="Device ID (optional, resolved from SNR)")
    parser.add_argument("--imei", help="Device IMEI (optional, skips modem read)")
    parser.add_argument("--iccids", help="Device ICCIDs (comma-separated)")
    parser.add_argument("--flash", action="store_true", help="Flash MFG firmware first")
    parser.add_argument("--app-hex", help="nRF52840 hex path")
    parser.add_argument("--comms-hex", help="nRF9151 hex path")
    parser.add_argument("--source-version", default="0.5.0", help="Source FW version")
    parser.add_argument("--target-version", default="0.5.1", help="Target FW version")
    parser.add_argument("--coreops-url", default="http://coreops-proxy", help="CoreOps URL")
    args = parser.parse_args()

    print("=" * 65)
    print("  FUOTA Setup Script - Stage 4 Validation")
    print("=" * 65)
    print(f"  MTIB: {args.mtib}")
    print(f"  SNR: {args.snr}")
    print(f"  Flash: {args.flash}")
    print(f"  Source: MFG v{args.source_version}")
    print(f"  Target: MFG v{args.target_version}")
    print("=" * 65 + "\n")

    try:
        # Connect to MTIB
        client = connect_mtib(args.mtib)

        # Flash if requested
        if args.flash:
            if not args.app_hex or not args.comms_hex:
                log("--app-hex and --comms-hex required with --flash", "ERR")
                sys.exit(1)
            flash_firmware(client, Path(args.app_hex), Path(args.comms_hex))

        # Power cycle
        power_cycle(client)

        # Personalize
        iccids = args.iccids.split(",") if args.iccids else None
        result = personalize_device(
            client,
            snr=args.snr,
            device_id=args.device_id,
            imei=args.imei,
            iccids=iccids,
            coreops_url=args.coreops_url
        )
        device_id = result["device_id"]

        # Setup FUOTA
        plan_id = setup_fuota(
            device_id=device_id,
            source_version=args.source_version,
            target_version=args.target_version,
        )

        print("\n" + "=" * 65)
        print("  FUOTA Setup Complete")
        print("=" * 65)
        print(f"  Device ID: {device_id}")
        print(f"  SNR: {args.snr}")
        print(f"  Plan ID: {plan_id}")
        print(f"  Transition: MFG v{args.source_version} → v{args.target_version}")
        print("\n  Device will check for updates on LTE-M wake (15-60 min)")
        print("=" * 65)

    except Exception as e:
        log(f"Setup failed: {e}", "ERR")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
