#!/usr/bin/env python3
"""FUOTA Chain Test — Validates upgrade chains with successive OTAs.

Tests the real-world upgrade path: one J-Link flash, then successive OTA
updates through different firmware variants. This proves the full FUOTA
pipeline works end-to-end without re-flashing between transitions.

Chain A (MFG -> Debug):
  test_01  Flash MFG_BASE + personalize
  test_02  FUOTA: MFG v0.5.x -> MFG v0.5.y   (same code, version bump)
  test_03  FUOTA: MFG v0.5.y -> DEBUG v0.8.x  (cross-variant upgrade)
  test_04  FUOTA: DEBUG v0.8.x -> DEBUG v0.8.y (debug build version bump)

Chain B (MFG -> Release):
  test_05  Re-flash MFG_BASE + re-personalize (CoreCloud can't downgrade)
  test_06  FUOTA: MFG v0.5.x -> RELEASE v0.8.x (cross-variant upgrade)
  test_07  FUOTA: RELEASE v0.8.x -> RELEASE v0.8.y (release version bump)

NOTE: Chain B requires a re-flash because after Chain A the device is at
DEBUG v0.8.y, and CoreCloud enforces strictly-increasing versions. A true
single-flash chain would need monotonically increasing versions across all
variants (e.g., MFG 0.5.x, DEBUG 0.6.x, RELEASE 0.7.x).

Requirements:
    PIPELINE_ID     Pipeline with all 8 FUOTA stage builds
    MTIB_ADDRESS    MTIB network address (e.g., 10.4.45.33)
    DEVICE_SNR      Device serial number (e.g., 0964)
    DEVICE_ID       Device EUI (e.g., 70B3D584C01E1FCC)
    DEVICE_IMEI     Device IMEI
    DEVICE_ICCIDS   Comma-separated ICCIDs
    VAL_1_0_*       CoreCloud auth credentials
    STORAGE_*       MinIO credentials
    CONCORD_API_*   Concord API credentials

Usage:
    # Via K8s job (all env vars set automatically):
    pytest tests/fuota/test_fuota_chain.py -v -s

    # Manual:
    PIPELINE_ID=<id> MTIB_ADDRESS=10.4.45.33 DEVICE_SNR=0964 \\
        pytest tests/fuota/test_fuota_chain.py -v -s
"""

import os
import re
import sys
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Ensure lib imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/python"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs/protocols"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "libs"))

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Force unbuffered output for K8s log streaming
import builtins
_original_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault("flush", True)
    _original_print(*args, **kwargs)


# ============================================================================
# Constants
# ============================================================================

DEVICE_TYPE_ID = 2
DEVICE_VARIANT_ID = 3
FUOTA_TIMEOUT_MINUTES = 30
POWER_CYCLE_INTERVAL_S = 180


# ============================================================================
# Shared State
# ============================================================================

class _ChainState:
    """Mutable state shared across ordered tests within a chain."""
    device_id: Optional[str] = None
    current_version: Optional[str] = None
    chain_a_failed: bool = False
    chain_b_failed: bool = False


_state = _ChainState()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def assets(request):
    """Load pipeline builds from Concord API."""
    from corekinect.test.firmware import PipelineAssets

    pipeline_id = (
        request.config.getoption("--pipeline-id")
        or os.environ.get("PIPELINE_ID")
    )
    if not pipeline_id:
        pytest.skip("PIPELINE_ID not set")

    pa = PipelineAssets(pipeline_id=pipeline_id)
    print(f"\n{pa.summary()}")

    if not pa.has_all_builds():
        available = {k: v.status for k, v in pa.builds.items()}
        pytest.fail(f"Pipeline missing builds or builds not complete: {available}")

    yield pa
    pa.cleanup()


@pytest.fixture(scope="module")
def mtib(request):
    """Connect to MTIB test interface board."""
    from corekinect.mtib_client.v1.client.core import MtibV1Client
    from corekinect.mtib_client.v1.client.config import NetConfig

    addr = (
        request.config.getoption("--mtib-addr")
        or os.environ.get("MTIB_ADDRESS")
        or os.environ.get("MTIB_HOST", "10.4.45.33")
    )

    cfg = MtibV1Client.Config(net=NetConfig(addr=addr, port=50053))
    client = MtibV1Client(cfg)
    err = client.connect()
    assert err is None, f"MTIB connect failed: {err}"

    yield client

    from corekinect.mtib_client.v1.client.types import PowerChannel
    try:
        client.PowerDisable(channel=PowerChannel.DUT)
        client.PowerDisable(channel=PowerChannel.CHARGER)
    except Exception:
        pass


@pytest.fixture(scope="module")
def fuota(request):
    """CoreCloud FUOTA client."""
    from corekinect.test.fuota_client import FuotaClient
    return FuotaClient(api_env="VAL_1_0")


@pytest.fixture(scope="module")
def snr(request):
    """Device serial number."""
    val = request.config.getoption("--device-snr") or os.environ.get("DEVICE_SNR")
    if not val:
        pytest.skip("DEVICE_SNR not set")
    return val


# ============================================================================
# Helpers — Flash & Personalize
# ============================================================================

def _power_off(client):
    from corekinect.mtib_client.v1.client.types import PowerChannel
    client.PowerDisable(channel=PowerChannel.DUT)
    client.PowerDisable(channel=PowerChannel.CHARGER)
    time.sleep(2)


def _power_on(client):
    from corekinect.mtib_client.v1.client.types import (
        PowerChannel, GpioDirection, GpioResistorConfig,
    )
    for gpio in (0, 1):
        client.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
        client.GpioWrite(gpio, False)
    client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
    client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)


def flash_and_personalize(client, snr: str, app_hex: str, comms_hex: str,
                          expected_version: str) -> str:
    """Flash firmware via J-Link, personalize, return device_id.

    Full sequence: flash both processors -> power cycle -> verify version
    via UART -> personalize (EC keygen + CoreCloud key upload).
    """
    from protocols.mtib.mtib_pb2 import HostType

    # Ensure DUT is powered for J-Link
    _power_on(client)
    time.sleep(2)

    # Upload and flash APP (nRF52840)
    print(f"  Uploading nRF52840: {Path(app_hex).name}")
    err = client.UploadFwFile(app_hex, HostType.HOST_TYPE_NRF52840)
    assert err is None, f"nRF52840 upload failed: {err}"

    files, err = client.ListFwFiles()
    assert err is None, f"ListFwFiles failed: {err}"
    app_file = next((f for f in files if f.name == Path(app_hex).name), None)
    assert app_file, "Uploaded app file not found"
    ms, err = client.FlashFwFile(app_file, recover=True)
    assert err is None, f"nRF52840 flash failed: {err}"
    print(f"  nRF52840 flashed in {ms}ms")

    # Upload and flash COMMS (nRF9151)
    print(f"  Uploading nRF9151: {Path(comms_hex).name}")
    err = client.UploadFwFile(comms_hex, HostType.HOST_TYPE_NRF9151)
    assert err is None, f"nRF9151 upload failed: {err}"

    files, err = client.ListFwFiles()
    assert err is None, f"ListFwFiles failed: {err}"
    comms_file = next((f for f in files if f.name == Path(comms_hex).name), None)
    assert comms_file, "Uploaded comms file not found"
    ms, err = client.FlashFwFile(comms_file, recover=True)
    assert err is None, f"nRF9151 flash failed: {err}"
    print(f"  nRF9151 flashed in {ms}ms")

    # Clean up uploaded files to prevent MTIB disk fill
    from corekinect.mtib_client.v1.client.types import FwFileInfo
    for fw_file in [app_file, comms_file]:
        try:
            client.DeleteFwFile(FwFileInfo(name=fw_file.name, target=fw_file.target))
        except Exception:
            pass

    # Power cycle and verify firmware version via UART
    print(f"  Verifying firmware version {expected_version}...")
    versions = _capture_and_verify_version(client, expected_version)
    print(f"  Boot versions: {versions}")

    # Personalize
    print(f"  Personalizing device (SNR={snr})...")
    from corekinect.test.device_personalizer import DevicePersonalizer

    imei = os.environ.get("DEVICE_IMEI", "355025931735979")
    iccids = os.environ.get("DEVICE_ICCIDS", "89148000009808558441,89457300000037582833").split(",")
    device_id = os.environ.get("DEVICE_ID")

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
    assert result and result.device_id, "No device_id from personalization"
    assert result.pub_key_base64, "No public key generated"

    print(f"  Device personalized: {result.device_id}")
    return result.device_id


# ============================================================================
# Helpers — UART Version Capture
# ============================================================================

def _capture_and_verify_version(client, expected_version: str) -> Dict[str, str]:
    """Power cycle DUT, capture UART boot logs, verify firmware version."""
    from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest
    from corekinect.mtib_client.v1.client.types import (
        PowerChannel, GpioDirection, GpioResistorConfig,
    )

    _power_off(client)

    versions = {"comms": None, "app": None}
    stop = threading.Event()
    found = {"comms": threading.Event(), "app": threading.Event()}

    version_re = [
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
                            for pat in version_re:
                                m = pat.search(line)
                                if m:
                                    versions[key] = m.group(2)
                                    found[key].set()
                                    break
        except Exception:
            pass

    # Start UART capture threads
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
    _power_on(client)

    # Wait for COMMS version detection (max 60s)
    # Only gate on COMMS — MFG firmware nRF52840 doesn't print version in
    # the same format, so APP version is often None. COMMS is ground truth.
    deadline = time.time() + 60
    while time.time() < deadline:
        if found["comms"].is_set():
            time.sleep(2)  # Let a few more lines flow
            break
        time.sleep(0.5)

    stop.set()
    for t in threads:
        t.join(timeout=5)

    assert versions["comms"] is not None, "Could not detect COMMS version from boot"
    assert versions["comms"] == expected_version, (
        f"Version mismatch: expected {expected_version}, got {versions['comms']}"
    )
    return versions


# ============================================================================
# Helpers — FUOTA Transition
# ============================================================================

def run_fuota_step(
    mtib_client,
    fuota_client,
    device_id: str,
    cfw_files: List[str],
    to_version: str,
    track: str,
    description: str,
) -> None:
    """Execute a single FUOTA transition: upload CFW, create plan, wait, verify.

    This is the core FUOTA step used in chain transitions — no flashing,
    no personalization. The device must already be running and registered.
    """
    # 1. Ensure device is registered in CoreCloud
    print(f"  Ensuring device {device_id} is registered...")
    fuota_client.ensure_device_registered(
        device_id=device_id,
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )

    # 2. Remove from any existing FUOTA plan
    print("  Checking existing FUOTA assignments...")
    resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
    for d in resp.json().get("devicesFound", []):
        if d.get("deviceId") == device_id:
            old_plan = d.get("planId")
            print(f"  Removing from plan {old_plan}")
            fuota_client.disable_device(device_id, old_plan)

    # 3. Upload CFW files (ignore 400 = already exists)
    for path in cfw_files:
        print(f"  Uploading CFW: {Path(path).name}")
        try:
            fuota_client.upload_cfw(path)
        except Exception as e:
            if "400" in str(e) or "already" in str(e).lower():
                print(f"    Already uploaded (OK)")
            else:
                raise

    # 4. Build targets from CFW filenames
    targets = []
    for path in cfw_files:
        m = re.search(r'(10[89])\.(\d+\.\d+\.\d+)\.cfw$', Path(path).name)
        if m:
            targets.append(f"{m.group(1)}.{m.group(2)}{track}")
    if not targets:
        targets = [f"108.{to_version}{track}", f"109.{to_version}{track}"]

    # 5. Create FUOTA plan
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stages = [{
        "targets": targets,
        "description": description,
        "isSkippable": False,
    }]
    print(f"  Creating plan: targets={targets}")
    plan_id = fuota_client.create_plan(
        stages=stages,
        description=f"Chain {ts}: {description}",
        device_type_id=DEVICE_TYPE_ID,
        device_variant_id=DEVICE_VARIANT_ID,
    )
    print(f"  Plan ID: {plan_id}")

    # 6. Assign device
    fuota_client.assign_device(plan_id=plan_id, device_ids=[device_id],
                               max_stage=0, enable=True)

    # Verify assignment
    resp = fuota_client._singleton_request("GET", "firmwareupdates/settings/devices")
    assigned = False
    for d in resp.json().get("devicesFound", []):
        if d.get("deviceId") == device_id:
            assert d.get("planId") == plan_id, f"Wrong plan: {d.get('planId')}"
            assert d.get("enableFuota") is True, "FUOTA not enabled"
            assigned = True
            break
    assert assigned, f"Device {device_id} not found in FUOTA settings"
    print(f"  Device assigned and FUOTA enabled")

    # 7. Power cycle to trigger CoreCloud check-in
    print("  Power cycling for check-in...")
    _capture_and_verify_version(mtib_client, _state.current_version)

    # 8. Wait for FUOTA completion
    print(f"  Waiting for FUOTA delivery (timeout: {FUOTA_TIMEOUT_MINUTES} min)...")
    _wait_for_fuota(fuota_client, device_id, mtib_client)

    # 9. Power cycle and verify new firmware version
    print(f"  Verifying firmware version {to_version}...")
    versions = _capture_and_verify_version(mtib_client, to_version)
    print(f"  Verified: {versions}")

    # 10. Cleanup: disable FUOTA
    try:
        fuota_client.disable_device(device_id, plan_id)
    except Exception as e:
        print(f"  Cleanup warning: {e}")


def _wait_for_fuota(fuota_client, device_id: str, mtib_client=None):
    """Poll FUOTA progress until both 108 and 109 complete."""
    from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

    start = time.time()
    timeout_s = FUOTA_TIMEOUT_MINUTES * 60
    completed = set()
    last_status = None
    last_power_cycle = start

    # UART monitor for FUOTA-related logs + CRC failure detection
    uart_stop = threading.Event()
    crc_failures = []  # timestamps of CRC failures detected via UART

    def _uart_mon():
        if not mtib_client:
            return
        partial = ""
        def req_gen():
            yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9151, data=b"")
            while not uart_stop.is_set():
                time.sleep(0.1)
                yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9151, data=b"")
        try:
            for resp in mtib_client.UartStream(HostType.HOST_TYPE_NRF9151, req_gen()):
                if uart_stop.is_set():
                    break
                if resp.data:
                    partial += resp.data.decode("utf-8", errors="replace")
                    while "\n" in partial:
                        line, partial = partial.split("\n", 1)
                        if any(kw in line.lower() for kw in [
                            "fuota", "cfw", "download", "mcuboot", "swap", "upgrade"
                        ]):
                            elapsed = (time.time() - start) / 60
                            print(f"    [UART {elapsed:.1f}m] {line.strip()}")
                        if "DOWNLOAD FAILED CRC CHECK" in line:
                            crc_failures.append(time.time())
        except Exception:
            pass

    if mtib_client:
        uart_t = threading.Thread(target=_uart_mon, daemon=True)
        uart_t.start()

    # Track which versions we've seen actively progressing (< 100%).
    # The progress API can return STALE 100% from a previous delivery.
    # Only accept 100% if we saw the version at < 100% first.
    seen_active = set()  # versions seen at < 100%

    try:
        while time.time() - start < timeout_s:
            resp = fuota_client._singleton_request(
                "GET", f"firmwareupdates/progress?deviceId={device_id}"
            )
            elapsed = (time.time() - start) / 60

            if resp.status_code == 200:
                p = resp.json()
                if p:
                    ver = p.get("version", "?")
                    pct = p.get("percentComplete", 0)
                    pages = p.get("pagesApplied", 0)
                    total = p.get("totalPages", 1)
                    status = f"{ver}: {pct:.1f}% ({pages}/{total})"

                    if status != last_status:
                        print(f"    [{elapsed:.1f}m] {status}")
                        last_status = status

                    if pct < 100:
                        seen_active.add(ver)

                    if pct >= 100:
                        if ver in seen_active:
                            # Genuine completion — we saw it progress
                            if ver not in completed:
                                completed.add(ver)
                                print(f"    {ver} COMPLETE!")
                        else:
                            # Stale 100% from previous delivery — ignore
                            if ver not in completed:
                                print(f"    [{elapsed:.1f}m] {ver} at 100% (stale from prev run, ignoring)")
                        if any("108" in v for v in completed) and any("109" in v for v in completed):
                            print(f"    [{elapsed:.1f}m] Both processors done!")
                            return

            elif resp.status_code == 404:
                has_108 = any("108" in v for v in completed)
                has_109 = any("109" in v for v in completed)

                if has_108 and has_109:
                    print(f"    [{elapsed:.1f}m] Both done (404 after completion)")
                    return
                elif has_108 and not has_109:
                    if last_status != "wait_109":
                        print(f"    [{elapsed:.1f}m] 108 done, waiting for 109...")
                        last_status = "wait_109"
                elif not completed:
                    if last_status != "wait_start":
                        print(f"    [{elapsed:.1f}m] Waiting for device check-in...")
                        last_status = "wait_start"

            # Fail fast on repeated CRC failures (firmware bug, won't recover)
            if len(crc_failures) >= 2:
                elapsed = (time.time() - start) / 60
                pytest.fail(
                    f"FUOTA CRC failure detected {len(crc_failures)} times "
                    f"(firmware bug: post-reboot CRC check fails on cross-variant). "
                    f"Completed: {completed}"
                )

            # Periodic power cycle — applies to ALL states (200, 404, etc.)
            # Needed when device is stuck (CRC failure, no new progress, etc.)
            if mtib_client and time.time() - last_power_cycle > POWER_CYCLE_INTERVAL_S:
                print(f"    [{elapsed:.1f}m] Power cycling to force check-in...")
                from corekinect.mtib_client.v1.client.types import PowerChannel
                try:
                    mtib_client.PowerDisable(channel=PowerChannel.DUT)
                    mtib_client.PowerDisable(channel=PowerChannel.CHARGER)
                    time.sleep(2)
                    _power_on(mtib_client)
                    time.sleep(5)
                    last_power_cycle = time.time()
                except Exception as e:
                    print(f"    Power cycle failed: {e}")

            time.sleep(10)

        # Timeout
        if any("108" in v for v in completed) and any("109" in v for v in completed):
            return
        pytest.fail(f"FUOTA timeout after {FUOTA_TIMEOUT_MINUTES} min. Completed: {completed}")

    finally:
        uart_stop.set()


def _get_track(label: str) -> str:
    """Derive CFW track suffix from build label.

    Pipeline-built CFWs all use -BM track regardless of debug/release variant.
    The D (debug) flag is in the firmware binary, not the CFW track.
    """
    return "-BM"


# ============================================================================
# Tests — Ordered chain, each test depends on the previous
# ============================================================================

class TestFuotaChain:
    """FUOTA upgrade chain — validates successive OTA transitions.

    Chain A: MFG_BASE -> MFG_BUMP -> DEBUG_A -> DEBUG_B
    Chain B: MFG_BASE -> RELEASE_A -> RELEASE_B
    """

    # ── Chain A: MFG -> Debug upgrade path ──────────────────────────────

    def test_01_flash_mfg_base(self, assets, mtib, fuota, snr):
        """Flash MFG_BASE firmware and personalize device."""
        version = assets.get_version("MFG_BASE")
        assert version, "MFG_BASE has no version"

        app_hex = assets.get_hex("MFG_BASE", "app")
        comms_hex = assets.get_hex("MFG_BASE", "comms")

        print(f"\n[Chain A] Flashing MFG_BASE v{version}")
        device_id = flash_and_personalize(mtib, snr, app_hex, comms_hex, version)

        _state.device_id = device_id
        _state.current_version = version
        print(f"Device ready: {device_id} running MFG v{version}")

    def test_02_fuota_mfg_bump(self, assets, mtib, fuota):
        """FUOTA: MFG base -> MFG bump (same code, version bump)."""
        if _state.chain_a_failed:
            pytest.skip("Chain A failed at earlier step")
        assert _state.device_id, "test_01 must pass first"

        to_version = assets.get_version("MFG_BUMP")
        cfw_files = assets.get_cfw_files("MFG_BUMP")
        track = _get_track("MFG_BUMP")

        print(f"\n[Chain A] FUOTA: MFG {_state.current_version} -> {to_version}")
        try:
            run_fuota_step(
                mtib, fuota, _state.device_id,
                cfw_files, to_version, track,
                f"MFG {_state.current_version} -> {to_version} (version bump)",
            )
            _state.current_version = to_version
        except BaseException:
            _state.chain_a_failed = True
            raise

    @pytest.mark.xfail(
        reason="Firmware CRC bug: post-reboot CRC check fails on cross-variant "
               "upgrades (calculated=0xecb8931e vs expected=0x064f0818). "
               "Pre-reboot CRC passes but post-MCUboot-swap verification reads "
               "wrong flash region. Affects all cross-variant transitions.",
        strict=False,
    )
    def test_03_fuota_mfg_to_debug(self, assets, mtib, fuota):
        """FUOTA: MFG -> DEBUG (cross-variant upgrade)."""
        if _state.chain_a_failed:
            pytest.skip("Chain A failed at earlier step")
        assert _state.device_id, "test_01 must pass first"

        to_version = assets.get_version("FUT_DEBUG_A")
        cfw_files = assets.get_cfw_files("FUT_DEBUG_A")
        track = _get_track("FUT_DEBUG_A")

        print(f"\n[Chain A] FUOTA: MFG {_state.current_version} -> DEBUG {to_version}")
        try:
            run_fuota_step(
                mtib, fuota, _state.device_id,
                cfw_files, to_version, track,
                f"MFG {_state.current_version} -> DEBUG {to_version} (cross-variant)",
            )
            _state.current_version = to_version
        except BaseException:
            _state.chain_a_failed = True
            raise

    def test_04_fuota_debug_bump(self, assets, mtib, fuota):
        """FUOTA: DEBUG A -> DEBUG B (debug build version bump)."""
        if _state.chain_a_failed:
            pytest.skip("Chain A failed at earlier step")
        assert _state.device_id, "test_01 must pass first"

        to_version = assets.get_version("FUT_DEBUG_B")
        cfw_files = assets.get_cfw_files("FUT_DEBUG_B")
        track = _get_track("FUT_DEBUG_B")

        print(f"\n[Chain A] FUOTA: DEBUG {_state.current_version} -> {to_version}")
        try:
            run_fuota_step(
                mtib, fuota, _state.device_id,
                cfw_files, to_version, track,
                f"DEBUG {_state.current_version} -> {to_version} (version bump)",
            )
            _state.current_version = to_version
        except BaseException:
            _state.chain_a_failed = True
            raise

    # ── Chain B: MFG -> Release upgrade path ────────────────────────────

    def test_05_reflash_for_release(self, assets, mtib, fuota, snr):
        """Re-flash MFG_BASE for release chain (CoreCloud can't downgrade)."""
        version = assets.get_version("MFG_BASE")
        app_hex = assets.get_hex("MFG_BASE", "app")
        comms_hex = assets.get_hex("MFG_BASE", "comms")

        print(f"\n[Chain B] Re-flashing MFG_BASE v{version}")
        device_id = flash_and_personalize(mtib, snr, app_hex, comms_hex, version)

        _state.device_id = device_id
        _state.current_version = version
        print(f"Device ready: {device_id} running MFG v{version}")

    @pytest.mark.xfail(
        reason="Firmware CRC bug: post-reboot CRC check fails on cross-variant "
               "upgrades. Same root cause as test_03.",
        strict=False,
    )
    def test_06_fuota_mfg_to_release(self, assets, mtib, fuota):
        """FUOTA: MFG -> RELEASE (cross-variant upgrade)."""
        if _state.chain_b_failed:
            pytest.skip("Chain B failed at earlier step")
        assert _state.device_id, "test_05 must pass first"

        to_version = assets.get_version("FUT_RELEASE_A")
        cfw_files = assets.get_cfw_files("FUT_RELEASE_A")
        track = _get_track("FUT_RELEASE_A")

        print(f"\n[Chain B] FUOTA: MFG {_state.current_version} -> RELEASE {to_version}")
        try:
            run_fuota_step(
                mtib, fuota, _state.device_id,
                cfw_files, to_version, track,
                f"MFG {_state.current_version} -> RELEASE {to_version} (cross-variant)",
            )
            _state.current_version = to_version
        except BaseException:
            _state.chain_b_failed = True
            raise

    def test_07_fuota_release_bump(self, assets, mtib, fuota):
        """FUOTA: RELEASE A -> RELEASE B (release build version bump)."""
        if _state.chain_b_failed:
            pytest.skip("Chain B failed at earlier step")
        assert _state.device_id, "test_05 must pass first"

        to_version = assets.get_version("FUT_RELEASE_B")
        cfw_files = assets.get_cfw_files("FUT_RELEASE_B")
        track = _get_track("FUT_RELEASE_B")

        print(f"\n[Chain B] FUOTA: RELEASE {_state.current_version} -> {to_version}")
        try:
            run_fuota_step(
                mtib, fuota, _state.device_id,
                cfw_files, to_version, track,
                f"RELEASE {_state.current_version} -> {to_version} (version bump)",
            )
            _state.current_version = to_version
        except BaseException:
            _state.chain_b_failed = True
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
