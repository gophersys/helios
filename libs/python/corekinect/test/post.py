"""Shared POST (Power-On Self-Test) — hardware verification after flash.

Runs chip ID, BMS, charger, GPS, modem, IMEI/ICCID, and external flash
verification on both processors. Used by both manufacturing and validation.

Usage:
    from corekinect.test.post import run_post, PostResult

    result = run_post(mtib_client)
    assert result.passed, result.summary()

    # Access individual results
    print(f"IMEI: {result.imei}")
    print(f"ICCIDs: {result.iccids}")
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional

from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell


@dataclass
class PostStepResult:
    """Result of a single POST step."""
    name: str
    passed: bool
    message: str
    duration_ms: int = 0


@dataclass
class PostResult:
    """Aggregate result of the full POST suite."""
    passed: bool = False
    steps: List[PostStepResult] = field(default_factory=list)
    # Collected data from POST (used by subsequent validation steps)
    imei: Optional[str] = None
    iccids: List[str] = field(default_factory=list)
    modem_fw_version: Optional[str] = None
    comms_ext_flash_id: Optional[str] = None
    app_ext_flash_id: Optional[str] = None
    app_ble_mac: Optional[str] = None

    def summary(self) -> str:
        lines = []
        for s in self.steps:
            status = "PASS" if s.passed else "FAIL"
            lines.append(f"[{status}] {s.name}: {s.message} ({s.duration_ms}ms)")
        passed = sum(1 for s in self.steps if s.passed)
        total = len(self.steps)
        lines.append(f"\n{passed}/{total} steps passed")
        return "\n".join(lines)


def _step(result: PostResult, name: str, passed: bool, message: str, duration_ms: int = 0):
    """Record a step result and print it."""
    step = PostStepResult(name=name, passed=passed, message=message, duration_ms=duration_ms)
    result.steps.append(step)
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: {message} ({duration_ms}ms)")
    return passed


def run_post(mtib_client, skip_ext_flash: bool = False) -> PostResult:
    """Run the full POST suite on both processors.

    Sequence:
        1. Boot + lock shells (comms + app)
        2. Comms chip IDs (external flash)
        3. App chip IDs (external flash + BLE MAC)
        4. BMS (gas gauge)
        5. Charger (BQ25180)
        6. GPS module
        7. Modem firmware version
        8. IMEI + ICCIDs
        9. External flash (comms + app) [optional]

    Personalization and IPC rekey are NOT included — those are separate
    steps in the validation flow that depend on POST passing first.

    Args:
        mtib_client: Connected MtibV1Client.
        skip_ext_flash: Skip external flash test (faster, for debug runs).

    Returns:
        PostResult with pass/fail status and collected device data.
    """
    result = PostResult()

    comms = CommsCoprocShell(mtib_client)
    app = AlphaAppShell(mtib_client)

    try:
        # ── Step 1: Boot + lock shells ─────────────────────────────────
        t0 = time.time()
        print("Starting UART streams...")

        comms.start()
        app.start()
        time.sleep(0.5)  # Let streams initialize

        print("Locking manufacturing shells...")
        comms_locked = comms.lock(timeout_s=10)
        app_locked = app.lock(timeout_s=10)

        if not comms_locked or not app_locked:
            msg = f"comms={'locked' if comms_locked else 'FAILED'}, app={'locked' if app_locked else 'FAILED'}"
            _step(result, "Boot + lock shells", False, msg, int((time.time() - t0) * 1000))
            return result

        # Silence debug output
        comms.debug_off()
        app.debug_off()

        # Reset streams after lock+debug_off to clear buffered noise
        comms.reset_stream()
        app.reset_stream()

        _step(result, "Boot + lock shells", True,
              "Both shells locked, debug disabled",
              int((time.time() - t0) * 1000))

        # ── Step 2: Comms chip IDs ─────────────────────────────────────
        t0 = time.time()
        ids, err = comms.get_chip_ids()
        if err:
            _step(result, "Comms chip IDs", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            expected = "0xef 0x40 0x17"
            ok = ids.ext_flash_id == expected
            result.comms_ext_flash_id = ids.ext_flash_id
            msg = f"Ext flash: {ids.ext_flash_id}"
            if not ok:
                msg += f" (expected {expected})"
            _step(result, "Comms chip IDs", ok, msg, int((time.time() - t0) * 1000))

        # ── Step 3: App chip IDs ───────────────────────────────────────
        t0 = time.time()
        ids, err = app.get_chip_ids()
        if err:
            _step(result, "App chip IDs", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            result.app_ext_flash_id = ids.ext_flash_id
            result.app_ble_mac = ids.ble_mac
            msg = f"Ext flash: {ids.ext_flash_id}, BLE MAC: {ids.ble_mac}"
            _step(result, "App chip IDs", True, msg, int((time.time() - t0) * 1000))

        # ── Step 4: BMS (gas gauge) ────────────────────────────────────
        t0 = time.time()
        bms, err = app.test_bms()
        if err:
            _step(result, "BMS (gas gauge)", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            ok = bms.connected
            msg = f"connected={bms.connected}, chip_id={bms.chip_id}, charge={bms.charge_percent}%"
            _step(result, "BMS (gas gauge)", ok, msg, int((time.time() - t0) * 1000))

        # ── Step 5: Charger (BQ25180) ──────────────────────────────────
        t0 = time.time()
        charger, err = app.test_charger()
        if err:
            _step(result, "Charger (BQ25180)", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            msg = f"chip_id={charger.chip_id}, voltage={charger.battery_voltage_mv}mV, on_charger={charger.on_charger}"
            _step(result, "Charger (BQ25180)", True, msg, int((time.time() - t0) * 1000))

        # ── Step 6: GPS module ─────────────────────────────────────────
        t0 = time.time()
        gps, err = app.test_gps()
        if err:
            _step(result, "GPS module", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            ok = not gps.in_shutdown
            msg = f"shutdown={gps.in_shutdown}, comms_ok={gps.comms_ok}"
            if gps.in_shutdown:
                msg += " (GPS is in shutdown — communication failed)"
            _step(result, "GPS module", ok, msg, int((time.time() - t0) * 1000))

        # ── Step 7: Modem firmware version ─────────────────────────────
        t0 = time.time()
        modem, err = comms.get_modem_fw()
        if err:
            _step(result, "Modem firmware", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            result.modem_fw_version = modem.version
            msg = f"version={modem.version}"
            _step(result, "Modem firmware", True, msg, int((time.time() - t0) * 1000))

        # ── Step 8: IMEI + ICCIDs ──────────────────────────────────────
        t0 = time.time()
        sim, err = comms.get_sim_info()
        if err:
            _step(result, "IMEI + ICCIDs", False, f"Error: {err}", int((time.time() - t0) * 1000))
        else:
            result.imei = sim.imei
            result.iccids = sim.iccids
            ok = bool(sim.imei and sim.iccids)
            msg = f"IMEI={sim.imei}, ICCIDs={sim.iccids}"
            if not ok:
                msg += " (missing IMEI or ICCIDs)"
            _step(result, "IMEI + ICCIDs", ok, msg, int((time.time() - t0) * 1000))

        # ── Step 9: External flash ─────────────────────────────────────
        if skip_ext_flash:
            _step(result, "External flash", True, "Skipped (skip_ext_flash=True)", 0)
        else:
            t0 = time.time()
            errors = []

            # Comms ext flash
            flash_result, err = comms.write_ext_flash("0x100000", "UFBPU1RfVEVTVA==")  # "POST_TEST" b64
            if err:
                errors.append(f"comms write: {err}")

            # App ext flash
            flash_result, err = app.test_ext_flash()
            if err:
                errors.append(f"app: {err}")
            elif not flash_result.data_match:
                errors.append(f"app: data mismatch (write_ok={flash_result.write_ok}, read_ok={flash_result.read_ok})")

            ok = len(errors) == 0
            msg = "Both processors OK" if ok else "; ".join(errors)
            _step(result, "External flash", ok, msg, int((time.time() - t0) * 1000))

        # ── Final result ───────────────────────────────────────────────
        result.passed = all(s.passed for s in result.steps)

    finally:
        # Always stop streams
        try:
            comms.stop()
        except Exception:
            pass
        try:
            app.stop()
        except Exception:
            pass

    return result
