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
# MANIFEST HELPERS
# =============================================================================


def host_type_from_manifest(host_type_str: str):
    """Convert manifest hostType string to protobuf HostType enum.

    Args:
        host_type_str: e.g., "HOST_TYPE_NRF52840", "HOST_TYPE_NRF9151"

    Returns:
        HostType enum value.
    """
    from protocols.mtib.mtib_pb2 import HostType

    mapping = {
        "HOST_TYPE_NRF52840": HostType.HOST_TYPE_NRF52840,
        "HOST_TYPE_NRF9151": HostType.HOST_TYPE_NRF9151,
        "HOST_TYPE_NRF9160": HostType.HOST_TYPE_NRF9160,
        "HOST_TYPE_NRF9151_MODEM": HostType.HOST_TYPE_NRF9151_MODEM,
        "HOST_TYPE_NRF9160_MODEM": HostType.HOST_TYPE_NRF9160_MODEM,
    }
    result = mapping.get(host_type_str)
    if result is None:
        raise ValueError(
            f"Unknown hostType: {host_type_str}. "
            f"Valid: {list(mapping.keys())}"
        )
    return result


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
    max_retries: int = 3,
) -> Dict[str, str]:
    """Personalize device: EC keygen + key upload to CoreCloud.

    Wraps DevicePersonalizer with pre-known IMEI/ICCIDs to skip modem read
    (UART byte-by-byte latency makes modem read unreliable).

    Retries up to max_retries times on UART timeout failures (intermittent
    due to MTIB byte-by-byte UART delivery at 115200 baud).

    Returns:
        Dict with "device_id" and "public_key" on success.

    Raises:
        AssertionError: On personalization failure after all retries.
    """
    from corekinect.test.device_personalizer import DevicePersonalizer

    last_err = None
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"  Personalization retry {attempt}/{max_retries} (previous: UART timeout)")
            time.sleep(5)

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

        if err is None and result and result.device_id and result.pub_key_base64:
            if attempt > 1:
                print(f"  Personalization succeeded on attempt {attempt}")
            return {
                "device_id": result.device_id,
                "public_key": result.pub_key_base64,
            }

        last_err = err
        # Only retry on UART timeout, not on other errors
        if err and "Timeout" in str(err):
            print(f"  UART timeout on attempt {attempt}/{max_retries}")
            continue
        break  # Non-timeout error, don't retry

    assert False, f"Personalization failed after {max_retries} attempts: {last_err}"

    return {  # unreachable but keeps type checker happy
        "device_id": "",
        "public_key": "",
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

    Also verifies the upload was accepted by attempting a delete-check
    (CoreCloud has no list-images endpoint, but delete returns 404 if
    the image doesn't exist).

    Raises:
        RuntimeError: If any upload fails (except already-exists).
    """
    for cfw_path in cfw_paths:
        name = Path(cfw_path).name
        print(f"Uploading {name}...")
        fuota_client.upload_cfw(cfw_path)

        # Verify upload: check if the image exists via a HEAD-like probe
        # (CoreCloud has no list endpoint, so we check via the delete endpoint
        # with a GET — if it would return 404, the upload didn't register)
        try:
            resp = fuota_client._singleton_request(
                "GET", f"firmwareimages?name={name}",
            )
            # 401/404 means not found or no list support — just log status
            print(f"  Upload verify: {name} -> HTTP {resp.status_code}")
        except Exception:
            pass  # Verification is best-effort


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

    # ── Verify plan exists and targets match ──
    # CoreCloud STRIPS the 'D' (debug) flag from plan targets. If our CFW was
    # uploaded with -BD flags but the plan stores -B, the firmware image version
    # won't match the plan target → delivery never starts. Catch this NOW.
    # NOTE: list endpoint is paginated (50 max), use ?planId= query instead.
    resp = fuota_client._singleton_request(
        "GET", f"firmwareupdates/plans?planId={plan_id}"
    )
    if resp.status_code == 200:
        stored_plan = resp.json()
        stored_stages = stored_plan.get("stages", [])
        for i, stage in enumerate(stored_stages):
            stored_targets = sorted(stage.get("targets", []))
            submitted = sorted(stages[i]["targets"]) if i < len(stages) else []
            if stored_targets != submitted:
                pytest.fail(
                    f"FUOTA plan target MISMATCH — CoreCloud modified our targets!\n"
                    f"  Submitted: {submitted}\n"
                    f"  Stored:    {stored_targets}\n"
                    f"CoreCloud strips the 'D' (debug) flag from targets. The uploaded "
                    f"CFW has version '{submitted[0]}' but the plan expects "
                    f"'{stored_targets[0]}'. FUOTA delivery will NEVER start.\n"
                    f"Fix: use release firmware (no -D flag) so targets match."
                )
            print(f"  Plan targets verified: {stored_targets}")
    else:
        print(f"  WARNING: Could not verify plan {plan_id} (HTTP {resp.status_code})")

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


def _completed_app_ids(completed_versions: set, expected_app_id_strs: set) -> set:
    """Find which expected app IDs have completed versions."""
    found = set()
    for aid_str in expected_app_id_strs:
        if any(aid_str in v for v in completed_versions):
            found.add(aid_str)
    return found


def _all_app_ids_completed(completed_versions: set, expected_app_id_strs: set) -> bool:
    """Check if all expected app IDs have at least one completed version."""
    return _completed_app_ids(completed_versions, expected_app_id_strs) == expected_app_id_strs


def wait_for_fuota_completion(
    fuota_client,
    device_id: str,
    timeout_s: int = 5400,
    mtib_client=None,
    power_cycle_interval_s: int = 180,
    max_stale_minutes: int = 5,
    expected_app_ids: Optional[set] = None,
) -> None:
    """Wait for FUOTA delivery to complete for all target processors.

    Args:
        expected_app_ids: Set of app IDs to wait for (e.g., {108, 109}).
            If None, defaults to {108, 109} for backwards compatibility.

    Polls CoreCloud progress endpoint. Handles:
    - Stale 100% from previous plans (only accepts 100% if seen < 100% first)
    - UART monitoring for FUOTA-related log lines
    - Periodic power cycles to force CoreCloud check-in
    - Auto-fail after max_stale_minutes of pure stale data (no new progress ever started)

    Raises:
        pytest.fail: If timeout expires without completion or stale limit hit.
    """

    # Default to legacy alpha app IDs for backwards compatibility
    if expected_app_ids is None:
        expected_app_ids = {108, 109}
    expected_app_id_strs = {str(aid) for aid in expected_app_ids}

    start = time.time()
    completed = set()
    seen_active = set()
    last_status = None
    last_pages_by_ver = {}   # track pages per version for smart power cycling
    last_progress_time = start  # when pages last advanced
    max_stale_s = max_stale_minutes * 60  # hard limit for pure stale data

    print(f"FUOTA delivery started (device={device_id})")
    print(f"Targets: app IDs {sorted(expected_app_ids)}")
    print(f"Timeout: {timeout_s // 60:.0f} minutes (stale limit: {max_stale_minutes}m)")
    print(f"Power cycle: only if stalled for 3+ minutes")
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
            # Only reset stale timer if we've seen real progress.
            # If seen_active is empty, we're stuck on stale data from a
            # previous plan — don't reset, let the hard stale limit trigger.
            if seen_active:
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
                        chip = ver  # Show version string as-is (product-agnostic)
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

                    # Track page advancement PER VERSION for smart power cycling.
                    # Only count as real progress if pct < 100 — stale 100% from
                    # a previous plan should NOT reset the stale timer.
                    prev_pages = last_pages_by_ver.get(ver, 0)
                    if pages > prev_pages and pct < 100:
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
                            # Stale 100% counts as stall — CoreCloud hasn't started new plan yet
                            stall_cycles += 1

                        if _all_app_ids_completed(completed, expected_app_id_strs):
                            elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s"
                            print(f"[{elapsed_str}] DONE: All targets complete ({sorted(expected_app_ids)})")
                            return

            elif resp.status_code == 404:
                elapsed_str = f"{int(elapsed_min)}m{int((elapsed_min % 1) * 60):02d}s" if elapsed_min >= 1 else f"{int(elapsed_min * 60)}s"

                if _all_app_ids_completed(completed, expected_app_id_strs):
                    print(f"[{elapsed_str}] DONE: All targets complete")
                    return
                elif completed:
                    completed_ids = _completed_app_ids(completed, expected_app_id_strs)
                    remaining = expected_app_id_strs - completed_ids
                    status_key = f"wait_{sorted(remaining)}"
                    if last_status != status_key:
                        print(f"[{elapsed_str}] Delivered: {sorted(completed_ids)}. Awaiting: {sorted(remaining)}...")
                        last_status = status_key
                elif not completed:
                    if last_status != "wait_start":
                        print(f"[{elapsed_str}] Awaiting first CoreCloud check-in to begin FUOTA download...")
                        last_status = "wait_start"
                    stall_cycles += 1

            # Smart power cycle: if no progress for 3 minutes
            stall_duration = time.time() - last_progress_time
            if mtib_client and stall_duration > 180 and stall_cycles >= 18:
                _force_power_cycle(f"no page progress for {int(stall_duration)}s ({stall_cycles} stale polls)")

            # Hard fail: if we've NEVER seen real progress and stale limit exceeded
            if not seen_active and stall_duration > max_stale_s:
                elapsed_min = (time.time() - start) / 60
                pytest.fail(
                    f"FUOTA delivery never started after {elapsed_min:.1f} min. "
                    f"CoreCloud progress endpoint only returns stale data from a previous plan. "
                    f"The device may need to be power-cycled manually, or CoreCloud "
                    f"may not be delivering the new plan. "
                    f"Completed: {completed or 'none'}"
                )

            time.sleep(10)

        # Timeout
        if _all_app_ids_completed(completed, expected_app_id_strs):
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

    # Wait for BOTH versions (APP may take longer after FUOTA — MCUboot swap)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        both_found = found["comms"].is_set() and found["app"].is_set()
        if both_found:
            time.sleep(2)  # Let a few more lines flow
            break
        # If only COMMS found, keep waiting for APP (MCUboot swap may be in progress)
        if found["comms"].is_set() and not found["app"].is_set():
            elapsed = int(time.time() - (deadline - timeout_s))
            if elapsed % 10 == 0 and elapsed > 0:
                print(f"  COMMS version detected, waiting for APP (MCUboot swap may be in progress)... {elapsed}s")
        time.sleep(0.5)

    stop.set()
    for t in threads:
        t.join(timeout=5)

    return versions


def verify_firmware_version(
    client,
    expected_version: str,
    timeout_s: float = 180.0,
    require_both: bool = True,
    max_boot_cycles: int = 3,
) -> Dict[str, Optional[str]]:
    """Power cycle and verify firmware version via UART boot logs.

    After FUOTA delivery, the firmware update process is:
      1. First boot: FUOTA handler copies pages from external flash → MCUboot secondary slot
      2. FUOTA handler sets the pending swap flag
      3. Second boot: MCUboot sees pending flag, swaps primary ↔ secondary
      4. Third boot (if needed): MCUboot confirms the swap

    The APP and COMMS processors may swap on different boot cycles.
    This function retries up to max_boot_cycles to give both processors
    time to complete the swap.

    Args:
        client: MTIB V1 client.
        expected_version: Expected version string (e.g., "0.5.14").
        timeout_s: Max seconds to wait PER boot cycle for version detection.
        require_both: If True, fail if either processor's version is missing.
        max_boot_cycles: Max power cycles to attempt before failing.

    Returns:
        Detected versions dict.

    Raises:
        AssertionError: If versions don't match after all retries.
    """
    print(f"Verifying firmware version (expecting v{expected_version})...")
    print(f"  Max boot cycles: {max_boot_cycles}, timeout per cycle: {int(timeout_s)}s")

    best_versions: Dict[str, Optional[str]] = {"comms": None, "app": None}

    for cycle in range(1, max_boot_cycles + 1):
        print(f"  Boot cycle {cycle}/{max_boot_cycles}...")

        # Wait longer on first cycle (FUOTA processing + MCUboot swap)
        cycle_timeout = timeout_s if cycle == 1 else 60.0
        versions = capture_boot_versions(client, timeout_s=cycle_timeout)

        print(f"    COMMS: {versions['comms'] or 'NOT DETECTED'}")
        print(f"    APP:   {versions['app'] or 'NOT DETECTED'}")

        # Track best result across cycles
        if versions["comms"]:
            best_versions["comms"] = versions["comms"]
        if versions["app"]:
            best_versions["app"] = versions["app"]

        # Check if we have the expected version on both
        comms_ok = best_versions["comms"] == expected_version
        app_ok = best_versions["app"] == expected_version if require_both else True

        if comms_ok and app_ok:
            print(f"  Both processors verified at v{expected_version} (cycle {cycle})")
            return best_versions

        # If a processor updated but the other didn't, try another cycle
        if cycle < max_boot_cycles:
            if not comms_ok:
                print(f"    COMMS not yet at v{expected_version}, power cycling again...")
            if require_both and not app_ok:
                print(f"    APP not yet at v{expected_version}, power cycling again...")
            time.sleep(5)  # Brief pause before next cycle

    # Final result after all cycles
    print(f"  Final versions after {max_boot_cycles} cycles:")
    print(f"    COMMS: {best_versions['comms'] or 'NOT DETECTED'}")
    print(f"    APP:   {best_versions['app'] or 'NOT DETECTED'}")

    assert best_versions["comms"] is not None, (
        f"COMMS version not detected after {max_boot_cycles} boot cycles"
    )
    assert best_versions["comms"] == expected_version, (
        f"COMMS version mismatch: expected {expected_version}, "
        f"got {best_versions['comms']} after {max_boot_cycles} boot cycles. "
        f"The COMMS MCUboot may not have swapped the secondary image."
    )

    if require_both:
        assert best_versions["app"] is not None, (
            f"APP version not detected after {max_boot_cycles} boot cycles. "
            f"The APP processor may be in a boot loop (firmware crash after FUOTA)."
        )
        assert best_versions["app"] == expected_version, (
            f"APP version mismatch: expected {expected_version}, "
            f"got {best_versions['app']} after {max_boot_cycles} boot cycles."
        )

    return best_versions
