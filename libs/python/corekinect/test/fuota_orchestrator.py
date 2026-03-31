"""FUOTA workflow orchestration — high-level operations for OTA testing.

Wraps FuotaClient with orchestration logic that any product needs:
- CFW upload with idempotency
- Plan creation + device assignment + verification
- Progress polling with stall detection and power cycling
- Cloud check-in polling

Usage:
    from corekinect.test.fuota_orchestrator import FuotaOrchestrator

    orchestrator = FuotaOrchestrator(fuota_client, fixture_controller)
    orchestrator.upload_cfw_files(cfw_paths)
    plan_id = orchestrator.create_and_assign_plan(device_id, targets, ...)
    orchestrator.wait_for_completion(device_id, expected_app_ids)
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pytest

from corekinect.utils import Logger

log = Logger(log_name="fuota.orchestrator")


class FuotaOrchestrator:
    """High-level FUOTA workflow operations.

    Wraps FuotaClient with retry logic, progress monitoring, stall detection,
    and smart power cycling. Product-agnostic — works with any device that
    uses CoreCloud FUOTA delivery.
    """

    def __init__(self, fuota_client, fixture_controller=None, logger=None):
        """
        Args:
            fuota_client: FuotaClient instance (authenticated).
            fixture_controller: Optional FixtureController for power cycling
                during stalls. If None, power cycling is skipped.
            logger: Optional logger. Defaults to module logger.
        """
        self._client = fuota_client
        self._fixture = fixture_controller
        self._log = logger or log

    def upload_cfw_files(self, cfw_paths: List[str]) -> None:
        """Upload CFW files to CoreCloud. Handles 'already exists' gracefully.

        Args:
            cfw_paths: List of local paths to .cfw files.

        Raises:
            RuntimeError: If any upload fails (except already-exists).
        """
        for cfw_path in cfw_paths:
            name = Path(cfw_path).name
            self._log.info("Uploading %s...", name)
            self._client.upload_cfw(cfw_path)

            # Best-effort verification
            try:
                resp = self._client._singleton_request(
                    "GET", f"firmwareimages?name={name}",
                )
                self._log.info("  Upload verify: %s -> HTTP %d", name, resp.status_code)
            except Exception:
                pass

    def create_and_assign_plan(
        self,
        device_id: str,
        target_strings: List[str],
        description: str,
        device_type_id: int,
        device_variant_id: int,
    ) -> int:
        """Create FUOTA plan, assign device, verify assignment.

        Steps:
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
        self._log.info("Ensuring device %s is registered...", device_id)
        self._client.ensure_device_registered(
            device_id=device_id,
            device_type_id=device_type_id,
            device_variant_id=device_variant_id,
        )

        # Remove from any existing FUOTA plan
        self._log.info("Checking for existing FUOTA assignments...")
        try:
            resp = self._client._singleton_request(
                "GET", "firmwareupdates/settings/devices"
            )
            for d in resp.json().get("devicesFound", []):
                if d.get("deviceId") == device_id:
                    old_plan = d.get("planId")
                    self._log.info("Removing from existing plan %s", old_plan)
                    self._client.disable_device(device_id, old_plan)
        except Exception as e:
            self._log.warning("Could not check existing assignments: %s", e)

        # Create plan
        stages = [{
            "targets": target_strings,
            "description": description,
            "isSkippable": False,
        }]

        self._log.info("Creating plan: targets=%s", target_strings)
        plan_id = self._client.create_plan(
            stages=stages,
            description=description,
            device_type_id=device_type_id,
            device_variant_id=device_variant_id,
        )
        self._log.info("Plan created: id=%d", plan_id)

        # Verify plan targets match (CoreCloud strips 'D' flag)
        resp = self._client._singleton_request(
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
                self._log.info("  Plan targets verified: %s", stored_targets)
        else:
            self._log.warning(
                "Could not verify plan %d (HTTP %d)", plan_id, resp.status_code
            )

        # Assign device
        self._log.info("Assigning device %s to plan %d...", device_id, plan_id)
        self._client.assign_device(
            plan_id=plan_id,
            device_ids=[device_id],
            max_stage=0,
            enable=True,
            device_type_id=device_type_id,
            device_variant_id=device_variant_id,
        )

        # Verify assignment
        resp = self._client._singleton_request(
            "GET", "firmwareupdates/settings/devices"
        )
        devices = resp.json().get("devicesFound", [])
        found = False
        for d in devices:
            if d.get("deviceId") == device_id:
                assert d.get("planId") == plan_id, (
                    f"Device assigned to wrong plan: expected {plan_id}, "
                    f"got {d.get('planId')}"
                )
                assert d.get("enableFuota") is True, (
                    "FUOTA not enabled after assignment"
                )
                found = True
                break

        assert found, (
            f"Device {device_id} not found in FUOTA settings after assignment"
        )
        self._log.info("Assignment verified: planId=%d, enabled=True", plan_id)

        return plan_id

    def wait_for_completion(
        self,
        device_id: str,
        expected_app_ids: Set[int],
        timeout_s: int = 5400,
        power_cycle_interval_s: int = 180,
        max_stale_minutes: int = 5,
    ) -> None:
        """Wait for FUOTA delivery to complete for all target processors.

        Polls CoreCloud progress endpoint. Handles:
        - Stale 100% from previous plans (only accepts if seen < 100% first)
        - Periodic power cycles to force CoreCloud check-in when stalled
        - Auto-fail after max_stale_minutes of pure stale data

        Args:
            device_id: CoreCloud device ID.
            expected_app_ids: Set of app IDs to wait for (e.g., {108, 109}).
            timeout_s: Maximum wait time in seconds.
            power_cycle_interval_s: Minimum seconds between power cycles.
            max_stale_minutes: Fail after this many minutes of no real progress.

        Raises:
            pytest.fail: If timeout or stale limit is reached.
        """
        expected_strs = {str(aid) for aid in expected_app_ids}

        start = time.time()
        completed: Set[str] = set()
        seen_active: Set[str] = set()
        last_status = None
        last_pages_by_ver: Dict[str, int] = {}
        last_progress_time = start
        max_stale_s = max_stale_minutes * 60
        stall_cycles = 0

        self._log.info("FUOTA delivery started (device=%s)", device_id)
        self._log.info("Targets: app IDs %s", sorted(expected_app_ids))
        self._log.info(
            "Timeout: %dm (stale limit: %dm)",
            timeout_s // 60, max_stale_minutes,
        )

        def _force_power_cycle(reason: str):
            nonlocal last_progress_time, stall_cycles
            if not self._fixture:
                return
            elapsed = (time.time() - start) / 60
            self._log.info("[%.1fm] Power cycling — %s", elapsed, reason)
            try:
                self._fixture.power_off()
                time.sleep(2)
                self._fixture.power_on()
                time.sleep(5)
                if seen_active:
                    last_progress_time = time.time()
                stall_cycles = 0
            except Exception as e:
                self._log.warning("[%.1fm] Power cycle failed: %s", elapsed, e)

        while time.time() - start < timeout_s:
            elapsed_min = (time.time() - start) / 60

            try:
                resp = self._client._singleton_request(
                    "GET",
                    f"firmwareupdates/progress?deviceId={device_id}",
                )
            except Exception as e:
                self._log.warning("[%.1fm] Progress API error: %s", elapsed_min, e)
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

                    # Log progress on change
                    status = f"{ver}: {pct:.1f}% ({pages}/{total})"
                    if status != last_status:
                        bar_len = 30
                        filled = int(bar_len * pct / 100)
                        bar = "#" * filled + "-" * (bar_len - filled)
                        self._log.info(
                            "[%.1fm] %s [%s] %.1f%% (%d/%d pages)",
                            elapsed_min, ver, bar, pct, pages, total,
                        )
                        last_status = status

                    # Track page advancement per version
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
                                self._log.info(
                                    "[%.1fm] DONE: %s -- %d pages", elapsed_min, ver, total,
                                )
                        else:
                            if ver not in completed:
                                self._log.info(
                                    "[%.1fm] %s at 100%% (stale from previous plan)",
                                    elapsed_min, ver,
                                )
                            stall_cycles += 1

                        if self._all_completed(completed, expected_strs):
                            self._log.info(
                                "[%.1fm] All targets complete (%s)",
                                elapsed_min, sorted(expected_app_ids),
                            )
                            return

            elif resp.status_code == 404:
                if self._all_completed(completed, expected_strs):
                    self._log.info("[%.1fm] All targets complete", elapsed_min)
                    return
                elif not completed:
                    if last_status != "wait_start":
                        self._log.info(
                            "[%.1fm] Awaiting first CoreCloud check-in...",
                            elapsed_min,
                        )
                        last_status = "wait_start"
                    stall_cycles += 1

            # Smart power cycle on stall
            stall_duration = time.time() - last_progress_time
            if self._fixture and stall_duration > 180 and stall_cycles >= 18:
                _force_power_cycle(
                    f"no page progress for {int(stall_duration)}s "
                    f"({stall_cycles} stale polls)"
                )

            # Hard fail on never-started
            if not seen_active and stall_duration > max_stale_s:
                pytest.fail(
                    f"FUOTA delivery never started after {elapsed_min:.1f} min. "
                    f"CoreCloud progress endpoint only returns stale data. "
                    f"Completed: {completed or 'none'}"
                )

            time.sleep(10)

        # Timeout
        if self._all_completed(completed, expected_strs):
            return

        pytest.fail(
            f"FUOTA did not complete within {timeout_s / 60:.0f} min. "
            f"Completed: {completed or 'none'}"
        )

    def wait_for_cloud_checkin(
        self,
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
            resp = self._client._api_request(
                "GET", "/System/Devices/Status",
                json={"deviceIds": [device_id]},
            )
            devices = resp.json().get("devices", [])
            if devices:
                initial_record_id = (
                    devices[0].get("positionInfo", {}).get("recordId", 0)
                )
            self._log.info("Baseline recordId: %d", initial_record_id)
        except Exception as e:
            self._log.warning("Could not read baseline status: %s", e)

        # Poll for change
        start = time.time()
        deadline = start + timeout_s

        while time.time() < deadline:
            elapsed = int(time.time() - start)
            try:
                resp = self._client._api_request(
                    "GET", "/System/Devices/Status",
                    json={"deviceIds": [device_id]},
                )
                devices = resp.json().get("devices", [])
                if devices:
                    current = (
                        devices[0].get("positionInfo", {}).get("recordId", 0)
                    )
                    if current > initial_record_id:
                        self._log.info(
                            "[%ds] Device checked in: recordId %d -> %d",
                            elapsed, initial_record_id, current,
                        )
                        return current
                    self._log.info("[%ds] Waiting... (recordId=%d)", elapsed, current)
            except Exception as e:
                self._log.warning("[%ds] Status check error: %s", elapsed, e)

            time.sleep(poll_interval_s)

        pytest.fail(
            f"Device {device_id} did not check into CoreCloud within {timeout_s}s "
            f"(last recordId={initial_record_id})"
        )

    @staticmethod
    def _all_completed(completed: Set[str], expected_strs: Set[str]) -> bool:
        """Check if all expected app IDs have at least one completed version."""
        for aid_str in expected_strs:
            if not any(aid_str in v for v in completed):
                return False
        return True


def personalize_with_retry(
    client,
    snr: str,
    device_id: Optional[str] = None,
    imei: Optional[str] = None,
    iccids: Optional[List[str]] = None,
    max_retries: int = 3,
    db_env: str = "VAL_1_0",
) -> Dict[str, str]:
    """Personalize device with retry logic for UART timeout failures.

    Wraps DevicePersonalizer with pre-known IMEI/ICCIDs to skip modem read
    (UART byte-by-byte latency makes modem read unreliable).

    Retries on UART timeout failures (intermittent due to MTIB
    byte-by-byte UART delivery at 115200 baud).

    Returns:
        Dict with "device_id" and "public_key" on success.

    Raises:
        AssertionError: On personalization failure after all retries.
    """
    from corekinect.test.device_personalizer import DevicePersonalizer

    last_err = None
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            log.info(
                "Personalization retry %d/%d (previous: UART timeout)",
                attempt, max_retries,
            )
            time.sleep(5)

        personalizer = DevicePersonalizer(
            mtib=client,
            snr=snr,
            imei=imei,
            iccids=iccids,
            known_device_id=device_id,
            db_env=db_env,
            require_corecloud_key=True,
        )

        result, err = personalizer.repersonalize(
            power_cycle=True, lock_shells=True,
        )

        if err is None and result and result.device_id and result.pub_key_base64:
            if attempt > 1:
                log.info("Personalization succeeded on attempt %d", attempt)
            return {
                "device_id": result.device_id,
                "public_key": result.pub_key_base64,
            }

        last_err = err
        # Only retry on UART timeout, not on other errors
        if err and "Timeout" in str(err):
            log.info("UART timeout on attempt %d/%d", attempt, max_retries)
            continue
        break  # Non-timeout error, don't retry

    assert False, (
        f"Personalization failed after {max_retries} attempts: {last_err}"
    )
