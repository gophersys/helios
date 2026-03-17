"""Shared FUOTA test helpers — hardware and API operations.

Every function in this module is designed to:
1. Raise on failure (no silent errors)
2. Print human-readable status (captured by reporter for live streaming)
3. Be reusable across all FUOTA flow test files

These are NOT pytest fixtures — they are plain functions called from test methods.
"""

import os
import re
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest


# =============================================================================
# POWER CONTROL
# =============================================================================


def power_off(client) -> None:
    """Disable both power channels and wait for discharge."""
    from corekinect.mtib_client.v1.client.types import PowerChannel

    client.PowerDisable(channel=PowerChannel.DUT)
    client.PowerDisable(channel=PowerChannel.CHARGER)
    time.sleep(2)


def power_on(client) -> None:
    """Configure GPIOs and enable both power channels.

    GPIO 0+1 must be output LOW for DUT to boot (see mtib-hardware rules).
    Ch0 (DUT) at 4.5V, Ch1 (charger) at 5.0V.
    """
    from corekinect.mtib_client.v1.client.types import (
        PowerChannel, GpioDirection, GpioResistorConfig,
    )

    for gpio in (0, 1):
        client.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.GpioWrite(gpio, False)

    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)


def power_cycle(client, off_s: float = 2.0, settle_s: float = 5.0) -> None:
    """Full power cycle: off → wait → on → settle."""
    power_off(client)
    time.sleep(max(0, off_s - 2.0))  # power_off already sleeps 2s
    power_on(client)
    time.sleep(settle_s)


def read_total_current_ma(client, samples: int = 10, interval_s: float = 0.5) -> float:
    """Read average total current (ch0 + ch1) over multiple samples.

    Returns average current in mA. Raises if all reads fail.
    """
    from corekinect.mtib_client.v1.client.types import PowerChannel

    readings = []
    for _ in range(samples):
        try:
            ch0, err0 = client.PowerRead(channel=PowerChannel.DUT)
            ch1, err1 = client.PowerRead(channel=PowerChannel.CHARGER)

            current = 0.0
            if not err0 and ch0:
                current += ch0.current_ma
            if not err1 and ch1:
                current += ch1.current_ma

            readings.append(current)
        except Exception:
            pass
        time.sleep(interval_s)

    if not readings:
        raise RuntimeError("All power reads failed — no current measurements")

    return sum(readings) / len(readings)


# =============================================================================
# FIRMWARE FLASHING
# =============================================================================


def flash_processor(client, hex_path: str, host_type) -> int:
    """Upload hex file to MTIB and flash one processor via J-Link.

    Args:
        client: Connected MTIB V1 client.
        hex_path: Local path to .hex file.
        host_type: protobuf HostType enum (HOST_TYPE_NRF52840 or HOST_TYPE_NRF9151).

    Returns:
        Flash duration in milliseconds.

    Raises:
        AssertionError: On upload, list, or flash failure.
    """
    name = Path(hex_path).name

    # Upload
    err = client.UploadFwFile(hex_path, host_type)
    assert err is None, f"Upload failed for {name}: {err}"

    # Find the uploaded file in server listing
    files_list, err = client.ListFwFiles()
    assert err is None, f"ListFwFiles failed: {err}"
    fw_file = next((f for f in files_list if f.name == name), None)
    assert fw_file is not None, f"Uploaded file not found on server: {name}"

    # Flash with recovery (clears APPROTECT)
    flash_ms, err = client.FlashFwFile(fw_file, recover=True)
    assert err is None, f"Flash failed for {name}: {err}"

    # Clean up uploaded file to prevent MTIB disk fill
    from corekinect.mtib_client.v1.client.types import FwFileInfo
    try:
        client.DeleteFwFile(FwFileInfo(name=fw_file.name, target=fw_file.target))
    except Exception:
        pass  # Non-critical

    return flash_ms


def flash_both_processors(client, app_hex: str, comms_hex: str) -> Tuple[int, int]:
    """Flash nRF52840 (app) and nRF9151 (comms) via J-Link.

    DUT must be powered before calling this.

    Returns:
        (app_flash_ms, comms_flash_ms) tuple.
    """
    from protocols.mtib.mtib_pb2 import HostType

    print(f"Flashing nRF52840: {Path(app_hex).name}")
    app_ms = flash_processor(client, app_hex, HostType.HOST_TYPE_NRF52840)
    print(f"nRF52840 flashed in {app_ms}ms")

    print(f"Flashing nRF9151: {Path(comms_hex).name}")
    comms_ms = flash_processor(client, comms_hex, HostType.HOST_TYPE_NRF9151)
    print(f"nRF9151 flashed in {comms_ms}ms")

    return app_ms, comms_ms


# =============================================================================
# PERSONALIZATION
# =============================================================================


def personalize_device(
    client,
    snr: str,
    device_id: Optional[str] = None,
    imei: Optional[str] = None,
    iccids: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Personalize device: EC keygen + key upload to CoreCloud.

    Wraps DevicePersonalizer with pre-known IMEI/ICCIDs to skip modem read
    (UART byte-by-byte latency makes modem read unreliable).

    Returns:
        Dict with "device_id" and "public_key" on success.

    Raises:
        AssertionError: On personalization failure.
    """
    from corekinect.test.device_personalizer import DevicePersonalizer

    personalizer = DevicePersonalizer(
        mtib=client,
        snr=snr,
        imei=imei,
        iccids=iccids,
        known_device_id=device_id,
        db_env="VAL_1_0",
        require_corecloud_key=True,
    )

    result, err = personalizer.repersonalize(power_cycle=True, lock_shells=True)

    assert err is None, f"Personalization failed: {err}"
    assert result is not None, "Personalization returned no result"
    assert result.device_id, "No device ID assigned"
    assert result.pub_key_base64, "No public key generated"

    return {
        "device_id": result.device_id,
        "public_key": result.pub_key_base64,
    }


# =============================================================================
# CORECLOUD: DEVICE STATUS
# =============================================================================


def wait_for_cloud_checkin(
    fuota_client,
    device_id: str,
    timeout_s: int = 150,
    poll_interval_s: int = 10,
) -> int:
    """Wait for device to check into CoreCloud (recordId change).

    Polls /System/Devices/Status until recordId increases from baseline.

    Returns:
        New recordId.

    Raises:
        AssertionError: If timeout expires without check-in.
    """
    # Get baseline recordId
    initial_record_id = 0
    try:
        resp = fuota_client._api_request(
            "GET", "/System/Devices/Status",
            json={"deviceIds": [device_id]},
        )
        devices = resp.json().get("devices", [])
        if devices:
            initial_record_id = devices[0].get("positionInfo", {}).get("recordId", 0)
        print(f"Baseline recordId: {initial_record_id}")
    except Exception as e:
        print(f"Warning: could not read baseline status: {e}")

    # Poll for change
    start = time.time()
    deadline = start + timeout_s

    while time.time() < deadline:
        elapsed = int(time.time() - start)
        try:
            resp = fuota_client._api_request(
                "GET", "/System/Devices/Status",
                json={"deviceIds": [device_id]},
            )
            devices = resp.json().get("devices", [])
            if devices:
                current = devices[0].get("positionInfo", {}).get("recordId", 0)
                if current > initial_record_id:
                    print(f"[{elapsed}s] Device checked in: recordId {initial_record_id} -> {current}")
                    return current
                print(f"[{elapsed}s] Waiting... (recordId={current})")
        except Exception as e:
            print(f"[{elapsed}s] Status check error: {e}")

        time.sleep(poll_interval_s)

    pytest.fail(
        f"Device {device_id} did not check into CoreCloud within {timeout_s}s "
        f"(last recordId={initial_record_id})"
    )


# =============================================================================
# CORECLOUD: FUOTA DELIVERY
# =============================================================================


def upload_cfw_files(fuota_client, cfw_paths: List[str]) -> None:
    """Upload CFW files to CoreCloud. Handles 'already exists' gracefully.

    Raises:
        RuntimeError: If any upload fails (except already-exists).
    """
    for cfw_path in cfw_paths:
        name = Path(cfw_path).name
        print(f"Uploading {name}...")
        fuota_client.upload_cfw(cfw_path)


def create_and_assign_fuota_plan(
    fuota_client,
    device_id: str,
    target_strings: List[str],
    description: str,
    device_type_id: int = 2,
    device_variant_id: int = 3,
) -> int:
    """Create FUOTA plan, assign device, verify assignment.

    1. Ensure device is registered in CoreCloud
    2. Remove from any existing FUOTA plan
    3. Create new plan with target CFW versions
    4. Assign device to plan
    5. Verify assignment

    Returns:
        Plan ID.

    Raises:
        RuntimeError: On plan creation or assignment failure.
        AssertionError: If post-assignment verification fails.
    """
    # Ensure device is registered (FUOTA fails on unregistered devices)
    print(f"Ensuring device {device_id} is registered...")
    fuota_client.ensure_device_registered(
        device_id=device_id,
        device_type_id=device_type_id,
        device_variant_id=device_variant_id,
    )

    # Remove from any existing FUOTA plan
    print("  Checking for existing FUOTA assignments...")
    try:
        resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
        for d in resp.json().get("devicesFound", []):
            if d.get("deviceId") == device_id:
                old_plan = d.get("planId")
                print(f"Removing from existing plan {old_plan}")
                fuota_client.disable_device(device_id, old_plan)
    except Exception as e:
        print(f"Warning: could not check existing assignments: {e}")

    # Create plan
    stages = [{
        "targets": target_strings,
        "description": description,
        "isSkippable": False,
    }]

    print(f"Creating plan: targets={target_strings}")
    plan_id = fuota_client.create_plan(
        stages=stages,
        description=description,
        device_type_id=device_type_id,
        device_variant_id=device_variant_id,
    )
    print(f"Plan created: id={plan_id}")

    # Assign device
    print(f"Assigning device {device_id} to plan {plan_id}...")
    fuota_client.assign_device(
        plan_id=plan_id,
        device_ids=[device_id],
        max_stage=0,
        enable=True,
        device_type_id=device_type_id,
        device_variant_id=device_variant_id,
    )

    # Verify assignment
    resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
    devices = resp.json().get("devicesFound", [])
    found = False
    for d in devices:
        if d.get("deviceId") == device_id:
            assert d.get("planId") == plan_id, (
                f"Device assigned to wrong plan: expected {plan_id}, got {d.get('planId')}"
            )
            assert d.get("enableFuota") is True, "FUOTA not enabled after assignment"
            found = True
            break

    assert found, f"Device {device_id} not found in FUOTA settings after assignment"
    print(f"Assignment verified: planId={plan_id}, enabled=True")

    return plan_id


def wait_for_fuota_completion(
    fuota_client,
    device_id: str,
    timeout_s: int = 5400,
    mtib_client=None,
    power_cycle_interval_s: int = 180,
) -> None:
    """Wait for FUOTA delivery to complete for both processors (108 + 109).

    Polls CoreCloud progress endpoint. Handles:
    - Stale 100% from previous plans (only accepts 100% if seen < 100% first)
    - UART monitoring for FUOTA-related log lines
    - Periodic power cycles to force CoreCloud check-in

    Raises:
        pytest.fail: If timeout expires without completion.
    """

    start = time.time()
    completed = set()
    seen_active = set()
    last_status = None
    last_pages_by_ver = {}   # track pages per version for smart power cycling
    last_progress_time = start  # when pages last advanced

    print(f"FUOTA delivery started (device={device_id})")
    print(f"Targets: comms (108) + app (109)")
    print(f"Timeout: {timeout_s // 60:.0f} minutes")
    print(f"Power cycle: only if stalled for 5+ minutes")
    print(f"---")
    stall_cycles = 0         # consecutive polls with no progress

    # NOTE: UART output is captured by UartDemuxer → telemetry → UART terminals.
    # No separate UART monitor thread needed here — keeps test step output clean.

    def _force_power_cycle(reason: str):
        nonlocal last_progress_time, stall_cycles
        if not mtib_client:
            return
        elapsed = (time.time() - start) / 60
        print(f"[{elapsed:.1f}m] Power cycling — {reason}")
        try:
            power_off(mtib_client)
            power_on(mtib_client)
            time.sleep(5)
            last_progress_time = time.time()
            stall_cycles = 0
        except Exception as e:
            print(f"[{elapsed:.1f}m] Power cycle failed: {e}")

    try:
        while time.time() - start < timeout_s:
            elapsed_min = (time.time() - start) / 60

            try:
                resp = fuota_client._singleton_request(
                    "GET", f"firmwareupdates/progress?deviceId={device_id}"
                )
            except Exception as e:
                print(f"[{elapsed_min:.1f}m] Progress API error: {e}")
                time.sleep(10)
                continue

            if resp.status_code == 200:
                prog = resp.json()
                if prog:
                    ver = prog.get("version", "?")
                    pct = prog.get("percentComplete", 0)
                    pages = prog.get("pagesApplied", 0)
                    total = prog.get("totalPages", 1)

                    if pct < 100:
                        seen_active.add(ver)

                    # Announce when a processor first starts downloading
                    if ver not in seen_active and pct < 100:
                        chip = "comms (nRF9151)" if "108" in ver else "app (nRF52840)" if "109" in ver else ver
                        elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s" if elapsed_min >= 1 else f"{int(elapsed_min * 60)}s"
                        print(f"[{elapsed_str}] Starting download: {chip} -> {ver} ({total} pages)")

                    # Log progress on every change
                    status = f"{ver}: {pct:.1f}% ({pages}/{total})"
                    if status != last_status:
                        bar_len = 30
                        filled = int(bar_len * pct / 100)
                        bar = "#" * filled + "-" * (bar_len - filled)
                        elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s" if elapsed_min >= 1 else f"{int(elapsed_min * 60)}s"
                        print(f"[{elapsed_str}] {ver} [{bar}] {pct:.1f}% ({pages}/{total} pages)")
                        last_status = status

                    # Track page advancement PER VERSION for smart power cycling
                    prev_pages = last_pages_by_ver.get(ver, 0)
                    if pages > prev_pages:
                        last_pages_by_ver[ver] = pages
                        last_progress_time = time.time()
                        stall_cycles = 0
                    elif pct < 100:
                        stall_cycles += 1

                    if pct >= 100:
                        if ver in seen_active:
                            if ver not in completed:
                                completed.add(ver)
                                elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s"
                                print(f"[{elapsed_str}] DONE: {ver} -- {total} pages in {elapsed_str}")
                        else:
                            if ver not in completed:
                                print(f"[{int(elapsed_min * 60)}s] {ver} at 100% (stale from previous plan, skipping)")

                        if any("108" in v for v in completed) and any("109" in v for v in completed):
                            elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s"
                            print(f"[{elapsed_str}] DONE: Both 108 (comms) + 109 (app) complete")
                            return

            elif resp.status_code == 404:
                has_108 = any("108" in v for v in completed)
                has_109 = any("109" in v for v in completed)
                elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s" if elapsed_min >= 1 else f"{int(elapsed_min * 60)}s"

                if has_108 and has_109:
                    print(f"[{elapsed_str}] DONE: Both processors complete")
                    return
                elif has_108 and not has_109:
                    if last_status != "wait_109":
                        print(f"[{elapsed_str}] Comms (108) delivered. Awaiting app (109) download to begin...")
                        last_status = "wait_109"
                elif has_109 and not has_108:
                    if last_status != "wait_108":
                        print(f"[{elapsed_str}] App (109) delivered. Awaiting comms (108) download to begin...")
                        last_status = "wait_108"
                elif not completed:
                    if last_status != "wait_start":
                        print(f"[{elapsed_str}] Awaiting first CoreCloud check-in to begin FUOTA download...")
                        last_status = "wait_start"
                    stall_cycles += 1

            # Smart power cycle: only if pages haven't advanced in 5 minutes
            stall_duration = time.time() - last_progress_time
            if mtib_client and stall_duration > 300 and stall_cycles >= 6:
                _force_power_cycle(f"no page progress for {int(stall_duration)}s ({stall_cycles} stale polls)")

            time.sleep(10)

        # Timeout
        has_108 = any("108" in v for v in completed)
        has_109 = any("109" in v for v in completed)
        if has_108 and has_109:
            return

        timeout_min = timeout_s / 60
        pytest.fail(
            f"FUOTA did not complete within {timeout_min:.0f} min. "
            f"Completed: {completed or 'none'}"
        )

    finally:
        pass  # Cleanup handled by TestContext


# =============================================================================
# BOOT LOG CAPTURE + VERSION VERIFICATION
# =============================================================================


def capture_boot_versions(
    client,
    timeout_s: float = 90.0,
) -> Dict[str, Optional[str]]:
    """Power cycle DUT and capture firmware versions from UART boot logs.

    Opens UART streams BEFORE power-on (mandatory — MCUs boot in milliseconds).
    Parses version strings from both APP and COMMS boot output.

    Returns:
        {"comms": "0.5.1" or None, "app": "0.8.3" or None}
    """
    from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

    power_off(client)

    versions = {"comms": None, "app": None}
    stop = threading.Event()
    found = {"comms": threading.Event(), "app": threading.Event()}

    version_patterns = [
        re.compile(r"application\s+(\d+)\s+launched.*Version\s+(\d+\.\d+\.\d+)"),
        re.compile(r"Running FW version\s+(\d+)\.(\d+\.\d+\.\d+)"),
    ]

    def _capture(target, key):
        partial = ""

        def req_gen():
            yield UartStreamRequest(target=target, data=b"")
            while not stop.is_set():
                time.sleep(0.05)
                yield UartStreamRequest(target=target, data=b"")

        try:
            for resp in client.UartStream(target, req_gen()):
                if stop.is_set():
                    break
                if resp.data:
                    partial += resp.data.decode("utf-8", errors="replace")
                    while "\n" in partial:
                        line, partial = partial.split("\n", 1)
                        if versions[key] is None:
                            for pat in version_patterns:
                                m = pat.search(line)
                                if m:
                                    versions[key] = m.group(2)
                                    found[key].set()
                                    break
        except Exception:
            pass

    # Start UART capture threads BEFORE power-on
    threads = []
    for target, key in [
        (HostType.HOST_TYPE_NRF9151, "comms"),
        (HostType.HOST_TYPE_NRF52840, "app"),
    ]:
        t = threading.Thread(target=_capture, args=(target, key), daemon=True)
        t.start()
        threads.append(t)

    time.sleep(1)  # Let UART threads initialize

    # Power on
    power_on(client)

    # Wait for at least COMMS version (more reliable than APP for MFG firmware)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if found["comms"].is_set():
            time.sleep(2)  # Let a few more lines flow
            break
        time.sleep(0.5)

    stop.set()
    for t in threads:
        t.join(timeout=5)

    return versions


def verify_firmware_version(
    client,
    expected_version: str,
    timeout_s: float = 90.0,
) -> Dict[str, Optional[str]]:
    """Power cycle, capture boot logs, verify firmware version.

    Asserts COMMS version matches expected. APP version is best-effort
    (MFG firmware may not output it in a parseable format).

    Returns:
        Detected versions dict.

    Raises:
        AssertionError: If COMMS version doesn't match expected.
    """
    print(f"Capturing boot logs (expecting v{expected_version})...")
    versions = capture_boot_versions(client, timeout_s=timeout_s)

    print(f"Detected versions: comms={versions['comms']}, app={versions['app']}")

    # COMMS version is ground truth (MFG nRF52840 doesn't always print version)
    if versions["comms"] is not None:
        assert versions["comms"] == expected_version, (
            f"COMMS version mismatch: expected {expected_version}, got {versions['comms']}"
        )
    else:
        print(f"WARNING: COMMS version not detected from boot logs")
        print(f"(MFG firmware may not log version — continuing without verification)")

    return versions
