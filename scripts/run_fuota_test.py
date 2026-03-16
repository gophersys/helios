#!/usr/bin/env python3
"""Standalone FUOTA test — flash v0.5.2, personalize, FUOTA to v0.5.4.

Uses the POST test's concurrent shell locking pattern (threading) instead
of DevicePersonalizer's sequential approach, which misses the ~7s shell
activation window due to MTIB byte-by-byte UART latency.

Usage:
    PYTHONPATH=libs/python:libs/protocols:libs python3 -u scripts/run_fuota_test.py
"""

import os
import sys
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "libs/python")
sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.environ.setdefault("TLS_VERIFY", "false")
os.environ.setdefault("VAL_1_0_API_URL", "https://val.office.corekinect.cloud:2018/api")
os.environ.setdefault("VAL_1_0_AUTH_URL", "https://auth.office.corekinect.cloud:2013/authentication/tokens/request")
os.environ.setdefault("VAL_1_0_API_KEY", "KWh0dHBzOi8vdmFsLm9mZmljZS5jb3Jla2luZWN0LmNsb3VkOjIwMTgvABQAAAAAAAAABAAAAAAAAAACaahyopKZcpXyK7zqUWGY2biB/UXKhV7/7+6CUpAz2xMUklU8yc2vOsfX1Y5jbY5M2F9vHjFi73M75cQZ6Fc+l8AzWLQ=")

# Build VAL_1_0_AUTH_BASIC from username/password if not set directly
# (K8s secret has separate auth-username and auth-password fields)
if not os.environ.get("VAL_1_0_AUTH_BASIC"):
    _user = os.environ.get("VAL_1_0_AUTH_USERNAME", "mateo@corekinect.com")
    _pass = os.environ.get("VAL_1_0_AUTH_PASSWORD", "5<jZm7e~}nvO37n@oWD,")
    import base64
    _creds = base64.b64encode(f"{_user}:{_pass}".encode()).decode()
    os.environ["VAL_1_0_AUTH_BASIC"] = f"Basic {_creds}"

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.test.fuota_client import FuotaClient
from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell
from protocols.mtib.mtib_pb2 import HostType

# ── Config (env vars override for K8s container) ────────
MTIB_HOST = os.environ.get("MTIB_HOST", os.environ.get("MTIB_ADDRESS", "10.4.45.33"))
MTIB_PORT = int(os.environ.get("MTIB_PORT", "50053"))
DEVICE_ID = os.environ.get("DEVICE_ID", "70B3D584C01E1FCC")
DEVICE_SNR = os.environ.get("DEVICE_SNR", "0964")
DEVICE_TYPE_ID = 2
DEVICE_VARIANT_ID = 3

# Firmware paths — container uses /app/firmware/alpha_mfg_fw/,
# local dev uses repo path
_CONTAINER_ARTIFACTS = Path("/app/firmware/alpha_mfg_fw")
_LOCAL_ARTIFACTS = Path("apps/firmware/products/alpha/artifacts/alpha_mfg_fw/alpha_b0")
ARTIFACTS = _CONTAINER_ARTIFACTS if _CONTAINER_ARTIFACTS.exists() else _LOCAL_ARTIFACTS
BASE_APP_HEX = ARTIFACTS / "0.5.2_app_nrf52840.hex"
BASE_COMMS_HEX = ARTIFACTS / "0.5.2_comms_nrf9151.hex"

# FUOTA targets — already on CoreCloud
TARGET_CFWS = ["108.0.5.4-BM", "109.0.5.4-BM"]
FUOTA_TIMEOUT_MIN = 45
REPEAT_COUNT = int(os.environ.get("FUOTA_REPEAT", "1"))


def power_on(client):
    """Power on DUT with correct GPIO config."""
    for gpio in (0, 1):
        client.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.GpioWrite(gpio, False)
    client.GpioConfig(gpio=2, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioWrite(gpio=2, state=True)
    client.PowerEnable(channel=0, voltage_v=4.5)
    client.PowerEnable(channel=1, voltage_v=5.0)


def power_off(client):
    """Power off DUT."""
    client.PowerDisable(channel=0)
    client.PowerDisable(channel=1)


def flash_firmware(client):
    """Flash v0.5.2 firmware via J-Link."""
    # Power on for flashing
    power_on(client)
    time.sleep(2)

    # APP (nRF52840)
    print(f"  Uploading {BASE_APP_HEX.name}...")
    err = client.UploadFwFile(str(BASE_APP_HEX), HostType.HOST_TYPE_NRF52840)
    if err:
        return f"APP upload failed: {err}"
    files, err = client.ListFwFiles()
    if err:
        return f"ListFwFiles failed: {err}"
    app_file = next((f for f in files if f.name == BASE_APP_HEX.name), None)
    if not app_file:
        return "APP file not found after upload"
    ms, err = client.FlashFwFile(app_file, recover=True)
    if err:
        return f"APP flash failed: {err}"
    print(f"  APP flashed in {ms}ms")

    # COMMS (nRF9151)
    print(f"  Uploading {BASE_COMMS_HEX.name}...")
    err = client.UploadFwFile(str(BASE_COMMS_HEX), HostType.HOST_TYPE_NRF9151)
    if err:
        return f"COMMS upload failed: {err}"
    files, err = client.ListFwFiles()
    if err:
        return f"ListFwFiles failed: {err}"
    comms_file = next((f for f in files if f.name == BASE_COMMS_HEX.name), None)
    if not comms_file:
        return "COMMS file not found after upload"
    ms, err = client.FlashFwFile(comms_file, recover=True)
    if err:
        return f"COMMS flash failed: {err}"
    print(f"  COMMS flashed in {ms}ms")
    return None


def _try_lock_and_personalize(client, max_attempts=3):
    """Power cycle → lock shells → debug off → personalize.

    If lock fails, power cycle and retry immediately (up to max_attempts).
    Lock timeout is 10s — if the shell doesn't lock in the ~7s window,
    it's not going to. Fail fast and retry with a fresh boot.
    """
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")

        # Power cycle
        power_off(client)
        time.sleep(2)

        # Open UART streams BEFORE power-on
        app = AlphaAppShell(client)
        comms = CommsCoprocShell(client)
        app.start()
        comms.start()

        # Power on
        power_on(client)
        time.sleep(0.5)

        # Concurrent lock — 10s timeout, fail fast
        lock_results = {}
        def _lock(shell, name):
            lock_results[name] = shell.lock(timeout_s=10)

        t_app = threading.Thread(target=_lock, args=(app, "APP"))
        t_comms = threading.Thread(target=_lock, args=(comms, "COMMS"))
        t_app.start()
        t_comms.start()
        t_app.join(timeout=15)
        t_comms.join(timeout=15)

        app_locked = lock_results.get("APP", False)
        comms_locked = lock_results.get("COMMS", False)
        print(f"    APP: {'locked' if app_locked else 'FAILED'}, COMMS: {'locked' if comms_locked else 'FAILED'}")

        if not app_locked or not comms_locked:
            failed = []
            if not app_locked: failed.append("APP")
            if not comms_locked: failed.append("COMMS")
            print(f"    {'+'.join(failed)} lock failed — retrying with fresh power cycle...")
            app.stop()
            comms.stop()
            continue

        # Both (or at least COMMS) locked — disable debug immediately
        comms.debug_off()
        if app_locked:
            app.debug_off()
        else:
            # APP not locked — spam raw debug_enable 0
            for _ in range(3):
                app._cmd._stream.write(b"\rdebug_enable 0\r")
                time.sleep(0.3)

        # Quick drain — just clear whatever's buffered
        print("    Draining backlog...")
        for i in range(20):  # 10s max
            app._cmd._stream.clear()
            comms._cmd._stream.clear()
            time.sleep(0.5)
            if len(comms._cmd._stream._buffer) < 10:
                break
        comms._cmd._stream.clear()
        app._cmd._stream.clear()

        return app, comms, app_locked, comms_locked

    return None, None, False, False


def personalize_with_concurrent_lock(client):
    """Power cycle, concurrent lock, personalize, upload key to CoreCloud.

    Uses fast fail-and-retry: 10s lock timeout, power cycle on failure,
    up to 3 attempts. Much faster than waiting 120s for a lock that
    will never come.
    """
    print("  Locking shells...")
    app, comms, app_locked, comms_locked = _try_lock_and_personalize(client)

    if not app_locked or not comms_locked:
        return None, "Shell lock failed after 3 attempts (APP=%s, COMMS=%s)" % (app_locked, comms_locked)

    # Personalize on COMMS shell
    print("  Running personalize command...")
    result, err = comms.personalize(DEVICE_ID, timeout_s=60)
    app.stop()
    comms.stop()

    if err:
        return None, f"Personalize command failed: {err}"
    if not result.base64_key:
        return None, "No public key returned"

    print(f"  Public key: {result.base64_key[:30]}...")

    # Upload key to CoreCloud via REST API
    print("  Uploading key to CoreCloud...")
    import json as json_mod
    from corekinect.core_cloud.api_interface import CoreCloudRestInterface
    import requests as req_mod

    with CoreCloudRestInterface(env_namespace="VAL_1_0") as api:
        token = api._ensure_token()
        key_str = str(api.api.key)
        base_url = api.api.rest_server_host_name

    sess = req_mod.Session()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-API-KEY": key_str,
        "Content-Type": "application/json",
    }
    url = f"{base_url}/System/Devices/Sessions/Profiles"
    body = {"Profiles": [{"DeviceId": DEVICE_ID, "PublicKey": result.base64_key}]}
    resp = sess.post(url, data=json_mod.dumps(body), headers=headers, verify=False, timeout=30)
    if resp.status_code not in (200, 204):
        return None, f"Key upload failed: {resp.status_code} {resp.text[:200]}"
    print(f"  Key uploaded (HTTP {resp.status_code})")

    return result, None


def wait_for_fuota(fc, timeout_min=45):
    """Poll FUOTA progress until both 108 and 109 complete.

    Handles stale progress data: after creating a new plan, the progress
    endpoint may return 100% from a PREVIOUS plan. We detect staleness by
    checking lastUpdated timestamp — if it's older than our start time,
    it's stale and we ignore it.
    """
    from datetime import datetime, timezone
    start = time.time()
    start_dt = datetime.now(timezone.utc)
    timeout_s = timeout_min * 60
    completed = set()
    last_status = None
    saw_fresh_data = False

    print(f"Waiting for device to check in with CoreCloud (PSM wakeup 2-10 min)...")
    print(f"Target: {', '.join(TARGET_CFWS)}")

    while time.time() - start < timeout_s:
        try:
            prog = fc.get_progress(DEVICE_ID)
        except Exception as e:
            print(f"[{time.time()-start:.0f}s] Progress error: {e}")
            time.sleep(30)
            continue

        elapsed = time.time() - start

        if prog:
            ver = prog.get("version", "?")
            pct = prog.get("percentComplete", 0)
            pages = prog.get("pagesApplied", 0)
            total = prog.get("totalPages", 1)
            last_updated = prog.get("lastUpdated", "")

            # Detect stale data from previous plan
            is_stale = False
            if last_updated and not saw_fresh_data:
                try:
                    updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    if updated_dt < start_dt:
                        is_stale = True
                except (ValueError, TypeError):
                    pass

            if is_stale:
                if last_status != "stale":
                    print(f"[{elapsed:.0f}s] Ignoring stale progress (lastUpdated={last_updated[:19]})")
                    last_status = "stale"
                time.sleep(30)
                continue

            saw_fresh_data = True
            status = f"{ver}: {pct:.1f}% ({pages}/{total} pages)"

            if status != last_status:
                print(f"[{elapsed:.0f}s] {status}")
                last_status = status

            if pct >= 100 and ver not in completed:
                completed.add(ver)
                print(f"  Stage complete: {ver}")

                has_108 = any("108" in v for v in completed)
                has_109 = any("109" in v for v in completed)
                if has_108 and has_109:
                    print(f"[{elapsed:.0f}s] Both stages DONE!")
                    return True
        else:
            # 404 = no active transfer
            has_108 = any("108" in v for v in completed)
            has_109 = any("109" in v for v in completed)
            if has_108 and has_109:
                print(f"[{elapsed:.0f}s] Both stages completed!")
                return True
            if has_108 and not has_109:
                if last_status != "waiting_109":
                    print(f"[{elapsed:.0f}s] 108 done, waiting for 109...")
                    last_status = "waiting_109"
            elif not completed:
                if last_status != "waiting":
                    print(f"[{elapsed:.0f}s] Waiting for check-in...")
                    last_status = "waiting"

        time.sleep(30)

    print(f"[{time.time()-start:.0f}s] TIMEOUT")
    return False


def run_once(iteration: int = 1) -> int:
    """Run a single FUOTA cycle. Returns 0 on success, 1 on failure."""
    t0 = time.time()
    print("=" * 60)
    print(f"FUOTA TEST (run {iteration}/{REPEAT_COUNT}): Flash v0.5.2 → Personalize → FUOTA to v0.5.4")
    print(f"Device: {DEVICE_ID} (SNR: {DEVICE_SNR})")
    print(f"MTIB: {MTIB_HOST}:{MTIB_PORT}")
    print(f"Artifacts: {ARTIFACTS}")
    print("=" * 60)

    if not BASE_APP_HEX.exists() or not BASE_COMMS_HEX.exists():
        print(f"ERROR: Missing hex files in {ARTIFACTS}")
        return 1

    # Connect to MTIB
    print(f"\n[1/5] Connecting to MTIB...")
    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"  FAILED: {err}")
        return 1
    print("  Connected")

    try:
        # Flash base firmware
        print(f"\n[2/5] Flashing v0.5.2 firmware [{time.time()-t0:.0f}s]...")
        err = flash_firmware(client)
        if err:
            print(f"  FAILED: {err}")
            return 1
        print("  Flash complete")

        # Personalize with concurrent lock
        print(f"\n[3/5] Personalizing [{time.time()-t0:.0f}s]...")
        result, err = personalize_with_concurrent_lock(client)
        if err:
            print(f"  FAILED: {err}")
            return 1
        print("  Personalization complete")

        # Warm-up: let the modem complete LTE-M attach before creating
        # the FUOTA plan. After chip erase, the modem does a cold network
        # scan (~5-10 min). By waiting here, the modem attaches and caches
        # network params. When we later power cycle for FUOTA check-in,
        # the modem reconnects in ~1-2 min (warm attach).
        print(f"\n[3.5] Modem warm-up — waiting for LTE-M attach [{time.time()-t0:.0f}s]...")
        print("  (Cold attach after chip erase takes 2-5 min, subsequent cycles ~1 min)")
        time.sleep(180)  # 3 min for cold LTE-M attach

        # Create FUOTA plan
        print(f"\n[4/5] Creating FUOTA plan [{time.time()-t0:.0f}s]...")
        fc = FuotaClient(api_env="VAL_1_0")

        # Disable existing assignment
        settings = fc.get_device_settings(DEVICE_ID)
        if settings and settings.get("enableFuota"):
            fc.disable_device(DEVICE_ID, settings["planId"])
            print(f"  Disabled old plan {settings['planId']}")
            time.sleep(1)

        fc.ensure_device_registered(DEVICE_ID, DEVICE_TYPE_ID, DEVICE_VARIANT_ID)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        plan_id = fc.create_plan(
            stages=[{
                "targets": TARGET_CFWS,
                "description": "v0.5.2 → v0.5.4 (108+109)",
                "isSkippable": False,
            }],
            description=f"FUOTA Test {ts}: v0.5.2 → v0.5.4",
            device_type_id=DEVICE_TYPE_ID,
            device_variant_id=DEVICE_VARIANT_ID,
        )
        print(f"  Plan ID: {plan_id}")

        fc.assign_device(plan_id, [DEVICE_ID], max_stage=0, enable=True)
        print(f"  Device assigned")

        # Power cycle to trigger CoreCloud check-in.
        # After the warm-up, the modem has cached network params and
        # reconnects in ~1-2 min (warm attach) instead of 5-10 min.
        print(f"\n[4.5] Power cycling for check-in [{time.time()-t0:.0f}s]...")
        power_off(client)
        time.sleep(3)
        power_on(client)
        time.sleep(5)

        result, err = client.PowerRead(channel=1)
        if not err and result:
            print(f"  ch1: {result.current_ma:.1f}mA @ {result.voltage_v:.2f}V")

        # Wait for FUOTA
        print(f"\n[5/5] Monitoring FUOTA [{time.time()-t0:.0f}s]...")
        success = wait_for_fuota(fc, timeout_min=FUOTA_TIMEOUT_MIN)

        elapsed = time.time() - t0
        print(f"\n{'=' * 60}")
        if success:
            print(f"FUOTA TEST PASSED (run {iteration}, {elapsed:.0f}s / {elapsed/60:.1f}m)")
        else:
            print(f"FUOTA TEST FAILED (run {iteration}, {elapsed:.0f}s)")
        print(f"{'=' * 60}")
        return 0 if success else 1

    except Exception as e:
        print(f"\nERROR: {e}")
        traceback.print_exc()
        return 1

    finally:
        print("\n--- Cleanup ---")
        try:
            power_off(client)
        except Exception:
            pass
        print("Done.")


def main():
    """Run FUOTA test REPEAT_COUNT times. Fail on first failure."""
    overall_start = time.time()
    print(f"\n{'#' * 60}")
    print(f"# FUOTA REPEATABILITY TEST — {REPEAT_COUNT} run(s)")
    print(f"{'#' * 60}\n")

    for i in range(1, REPEAT_COUNT + 1):
        rc = run_once(iteration=i)
        if rc != 0:
            print(f"\nFATAL: Run {i}/{REPEAT_COUNT} FAILED. Stopping.")
            return 1
        if i < REPEAT_COUNT:
            print(f"\n--- Run {i} complete, starting run {i+1} ---\n")

    total = time.time() - overall_start
    print(f"\n{'#' * 60}")
    print(f"# ALL {REPEAT_COUNT} RUNS PASSED ({total:.0f}s / {total/60:.1f}m total)")
    print(f"{'#' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
