"""FUOTA plan management for Stage 4 validation.

Creates, assigns, and monitors FUOTA plans via CoreCloud REST API
(/singleton/ endpoints). Used by the validation framework to orchestrate
firmware transitions on test DUTs.

Base URL: https://val.office.corekinect.cloud:2018
Auth: Same Bearer token + X-API-KEY as /api/ endpoints.
Endpoints use /singleton/ prefix (not /api/).
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from corekinect.errors import CloudError
from corekinect.utils import Logger

# TLS verification — enabled by default, can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")

log = Logger(log_name="fuota_client")

# Default poll interval — FUOTA progress depends on device uplink cycle
# (LTE-M PSM wake: 15-60 min), so polling faster than 30s is wasteful.
DEFAULT_POLL_INTERVAL_S = 30.0


class FuotaClient:
    """FUOTA plan management for Stage 4 validation.

    Wraps the CoreCloud /singleton/ REST API for firmware update operations:
    - Upload CFW files
    - Create FUOTA plans (stage definitions)
    - Assign devices to plans
    - Monitor progress
    - Cleanup (disable FUOTA for device)

    Args:
        api_env: CoreCloud API namespace (default: "VAL_1_0").
        logger: Parent Logger instance.
    """

    def __init__(self, api_env: str = "VAL_1_0", logger: Optional[Logger] = None):
        self._api_env = api_env
        self._log = logger.from_parent("fuota") if logger else log
        self._api = None
        self._base_url: Optional[str] = None

    def _get_api(self):
        """Lazily initialize CoreCloudRestInterface."""
        if self._api is None:
            from corekinect.core_cloud.api_interface import CoreCloudRestInterface
            self._api = CoreCloudRestInterface(env_namespace=self._api_env)
            self._api.__enter__()
            # /singleton/ endpoints use the base URL without /api suffix
            self._base_url = self._api.api.rest_server_host_name.replace("/api", "")
            self._log.info("FUOTA API connected (env=%s)", self._api_env)
        return self._api

    def _singleton_request(self, method: str, path: str, **kwargs) -> Any:
        """Make a request to /singleton/ endpoints using the API session."""
        api = self._get_api()
        sess = api._require_session()
        token = api._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-API-KEY": str(api.api.key),
        }
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"
        url = f"{self._base_url}/singleton/{path.lstrip('/')}"
        resp = sess.request(method, url, headers=headers, verify=_TLS_VERIFY, timeout=30, **kwargs)
        return resp

    def _safe_json(self, resp, context: str) -> dict:
        """Parse JSON response with validation.

        Raises CloudError if response body is not valid JSON or not a dict.
        """
        try:
            data = resp.json()
        except Exception as exc:
            raise CloudError(f"{context}: invalid JSON response: {exc}")
        if not isinstance(data, dict):
            raise CloudError(f"{context}: expected dict, got {type(data).__name__}")
        return data

    # ------------------------------------------------------------------
    # Device Registration
    # ------------------------------------------------------------------

    def _api_request(self, method: str, path: str, **kwargs) -> Any:
        """Make a request to /api/ endpoints using the API session."""
        api = self._get_api()
        sess = api._require_session()
        token = api._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-API-KEY": str(api.api.key),
        }
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"
        # /api/ endpoints use the full rest_server_host_name (includes /api)
        url = f"{api.api.rest_server_host_name.rstrip('/')}/{path.lstrip('/')}"
        resp = sess.request(method, url, headers=headers, verify=_TLS_VERIFY, timeout=30, **kwargs)
        return resp

    def ensure_device_registered(
        self,
        device_id: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> bool:
        """Ensure device is registered in CoreCloud. Registers if not present.

        MUST be called before assign_device() — FUOTA assignment fails on
        unregistered devices with "Device not found".

        Args:
            device_id: DevEUI hex string (e.g., "70B3D584C01E1DDD").
            device_type_id: CoreCloud device type (2 = Alpha).
            device_variant_id: CoreCloud device variant (3 = Alpha B0).

        Returns:
            True if device was newly registered, False if already registered.
        """
        # Check if already registered via Search endpoint
        resp = self._api_request(
            "GET", "System/Devices/Search",
            json={"deviceIds": [device_id]},
        )
        if resp.status_code == 200:
            data = self._safe_json(resp, "Device search")
            devices = data.get("devices", data if isinstance(data, list) else [])
            for d in devices:
                if d.get("deviceId") == device_id:
                    self._log.info(
                        "Device %s already registered (type=%s, variant=%s)",
                        device_id, d.get("deviceType"), d.get("deviceVariantId"),
                    )
                    return False

        # Register the device
        self._log.info(
            "Registering device %s (type=%d, variant=%d)",
            device_id, device_type_id, device_variant_id,
        )
        payload = {
            "Devices": [{
                "DeviceId": device_id,
                "DeviceType": device_type_id,
                "DeviceVariantId": device_variant_id,
            }]
        }
        resp = self._api_request("POST", "System/Devices/Register", json=payload)

        if resp.status_code != 200:
            raise CloudError(
                f"Device registration failed: {resp.status_code} {resp.text[:300]}"
            )

        result = self._safe_json(resp, "Device registration")
        registered = result.get("registeredDevices", [])
        already = result.get("devicesAlreadyRegistered", [])

        if registered:
            self._log.info("Device %s registered successfully", device_id)
            return True
        elif already:
            self._log.info("Device %s was already registered", device_id)
            return False
        else:
            raise CloudError(f"Unexpected registration result: {result}")

    # ------------------------------------------------------------------
    # CFW Upload
    # ------------------------------------------------------------------

    def upload_cfw(self, cfw_path: str) -> None:
        """Upload .cfw firmware package to CoreCloud.

        POST /singleton/firmwareimages (multipart/form-data, field: image)
        Server parses CFW v2 header to extract version metadata.
        Returns 204 on success.

        Args:
            cfw_path: Path to .cfw file.

        Raises:
            FileNotFoundError: If cfw_path doesn't exist.
            RuntimeError: If upload fails.
        """
        p = Path(cfw_path)
        if not p.exists():
            raise FileNotFoundError(f"CFW file not found: {cfw_path}")

        self._log.info("Uploading CFW: %s (%d bytes)", p.name, p.stat().st_size)

        with open(p, "rb") as f:
            resp = self._singleton_request(
                "POST", "firmwareimages",
                files={"image": (p.name, f, "application/octet-stream")},
            )

        if resp.status_code == 400 and "already exists" in resp.text:
            self._log.info("CFW already uploaded: %s (skipping)", p.name)
            return
        if resp.status_code not in (200, 204):
            raise CloudError(
                f"CFW upload failed: {resp.status_code} {resp.text[:200]}"
            )
        self._log.info("CFW uploaded: %s", p.name)

    def delete_cfw(self, cfw_name: str) -> bool:
        """Delete .cfw firmware package from CoreCloud.

        DELETE /singleton/firmwareimages?name=<cfw_name>

        Args:
            cfw_name: CFW filename (e.g., "108.0.5.2-BM.cfw").

        Returns:
            True if deleted, False if not found.

        Raises:
            RuntimeError: If deletion fails.
        """
        self._log.info("Deleting CFW: %s", cfw_name)

        resp = self._singleton_request(
            "DELETE", f"firmwareimages?name={cfw_name}",
        )

        if resp.status_code == 404:
            self._log.info("CFW not found (already deleted?): %s", cfw_name)
            return False
        if resp.status_code not in (200, 204):
            raise CloudError(
                f"CFW delete failed: {resp.status_code} {resp.text[:200]}"
            )
        self._log.info("CFW deleted: %s", cfw_name)
        return True

    # ------------------------------------------------------------------
    # Plan Management
    # ------------------------------------------------------------------

    def create_plan(
        self,
        stages: List[Dict[str, Any]],
        description: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> int:
        """Create FUOTA plan. Returns planId.

        POST /singleton/firmwareupdates/plans

        Each stage dict must have:
            - targets: list of CFW version strings, e.g. ["108.0.8.0-P", "109.0.8.0-P"]
            - description: human-readable stage description
            - isSkippable: bool

        Args:
            stages: List of stage definitions.
            description: Plan description (include run ID for traceability).
            device_type_id: CoreCloud device type (2 = Alpha).
            device_variant_id: CoreCloud device variant (3 = Alpha B0).

        Returns:
            planId (integer).
        """
        payload = {
            "stages": stages,
            "description": description,
            "deviceTypeId": device_type_id,
            "deviceVariantId": device_variant_id,
        }

        self._log.info("Creating FUOTA plan: %s", description)
        resp = self._singleton_request("POST", "firmwareupdates/plans", json=payload)

        if resp.status_code != 200:
            raise CloudError(
                f"Plan creation failed: {resp.status_code} {resp.text[:300]}"
            )

        plan = self._safe_json(resp, "Plan creation")
        plan_id = plan.get("planId")
        if plan_id is None:
            raise CloudError(f"Plan creation response missing 'planId': {plan}")
        self._log.info(
            "Plan created: id=%d, stages=%d (raw response: %s)",
            plan_id, len(stages), str(plan)[:200],
        )
        return plan_id

    def list_plans(self) -> List[Dict[str, Any]]:
        """List all FUOTA plans.

        GET /singleton/firmwareupdates/plans
        """
        resp = self._singleton_request("GET", "firmwareupdates/plans")
        resp.raise_for_status()
        return resp.json().get("fuotaPlans", [])

    # ------------------------------------------------------------------
    # Device Assignment
    # ------------------------------------------------------------------

    def assign_device(
        self,
        plan_id: int,
        device_ids: List[str],
        max_stage: int,
        enable: bool = True,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> Dict[str, Any]:
        """Assign device(s) to FUOTA plan.

        POST /singleton/firmwareupdates/settings/devices

        SAFETY: Only pass test DUT device IDs. Never production devices.

        Auto-registers devices if not already registered (required for assignment).

        Args:
            plan_id: Plan to assign (from create_plan).
            device_ids: List of DevEUI hex strings.
            max_stage: 0-indexed max stage the device should reach.
            enable: Enable FUOTA (True) or disable (False).
            device_type_id: CoreCloud device type (default 2 = Alpha).
            device_variant_id: CoreCloud device variant (default 3 = Alpha B0).

        Returns:
            Response dict with numDevicesUpdated.
        """
        # CRITICAL: Ensure devices are registered before assigning.
        # FUOTA assignment fails with "Device not found" on unregistered devices.
        for device_id in device_ids:
            self.ensure_device_registered(device_id, device_type_id, device_variant_id)

        payload = {
            "planId": plan_id,
            "enableFuota": enable,
            "maxStage": max_stage,
            "deviceIds": device_ids,
        }

        action = "Assigning" if enable else "Disabling"
        self._log.info(
            "%s device(s) %s to plan %d (maxStage=%d)",
            action, device_ids, plan_id, max_stage,
        )

        resp = self._singleton_request(
            "POST", "firmwareupdates/settings/devices", json=payload,
        )

        if resp.status_code != 200:
            raise CloudError(
                f"Device assignment failed: {resp.status_code} {resp.text[:300]}"
            )

        result = self._safe_json(resp, "Device assignment")
        self._log.info("Assignment result: %s", result)
        return result

    def disable_device(self, device_id: str, plan_id: int = 0) -> Dict[str, Any]:
        """Disable FUOTA for a device.

        Convenience wrapper around assign_device with enable=False.
        plan_id should be the device's current plan (use get_device_settings).
        """
        return self.assign_device(plan_id, [device_id], max_stage=0, enable=False)

    def get_device_settings(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get FUOTA settings for a specific device.

        Returns:
            Device settings dict with planId, enableFuota, maxStage,
            or None if device has no FUOTA assignment.
        """
        resp = self._singleton_request("GET", "firmwareupdates/settings/devices")
        resp.raise_for_status()
        data = resp.json()
        devices = data.get("devicesFound", data if isinstance(data, list) else [])
        for d in devices:
            if d.get("deviceId") == device_id:
                return d
        return None

    # ------------------------------------------------------------------
    # Progress Monitoring
    # ------------------------------------------------------------------

    def get_progress(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current FUOTA progress for a device.

        GET /singleton/firmwareupdates/progress?deviceId=<DevEUI>

        Returns:
            Progress dict with: deviceId, version, percentComplete,
            pagesApplied, totalPages, timeStarted, lastUpdated.
            None if no FUOTA transfer is active (404).
        """
        resp = self._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={device_id}",
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._safe_json(resp, "FUOTA progress")

    def wait_for_stage_complete(
        self,
        device_id: str,
        timeout_s: float = 7200,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> Dict[str, Any]:
        """Poll progress until percentComplete reaches 100 or timeout.

        FUOTA depends on device uplink cycle (LTE-M PSM: 15-60 min).
        Default timeout is 2 hours.

        Args:
            device_id: DevEUI hex string.
            timeout_s: Maximum wait time in seconds.
            poll_interval_s: Polling interval in seconds.

        Returns:
            Final progress dict.

        Raises:
            TimeoutError: If stage doesn't complete within timeout.
        """
        deadline = time.monotonic() + timeout_s
        t0 = time.monotonic()
        last_pages = 0

        while time.monotonic() < deadline:
            progress = self.get_progress(device_id)

            if progress:
                pages = progress.get("pagesApplied", 0)
                total = progress.get("totalPages", 1)
                pct = progress.get("percentComplete", 0)
                ver = progress.get("version", "?")

                if pages != last_pages:
                    elapsed = time.monotonic() - t0
                    self._log.info(
                        "FUOTA %s: %d/%d pages (%d%%) [%.0fs]",
                        ver, pages, total, pct, elapsed,
                    )
                    last_pages = pages

                if pct >= 100:
                    elapsed = time.monotonic() - t0
                    self._log.info(
                        "FUOTA stage complete: %s in %.0fs", ver, elapsed,
                    )
                    return progress
            else:
                self._log.debug("No FUOTA progress (404) — transfer may not have started")

            time.sleep(poll_interval_s)

        raise TimeoutError(
            f"FUOTA stage for device {device_id} did not complete "
            f"within {timeout_s}s (last: {last_pages} pages)"
        )

    def wait_for_fuota_boot(
        self,
        cloud_client,
        timeout_s: float = 3600,
    ) -> Dict[str, Any]:
        """Wait for device to reboot with boot_reason=Fuota after FUOTA apply.

        After all pages are delivered, the device applies the update and reboots.
        This method polls the CloudClient for a boot event with reason "Fuota".

        Args:
            cloud_client: CloudClient instance for the device.
            timeout_s: Maximum wait time.

        Returns:
            Boot info dict from CloudClient.
        """
        cloud_client.mark_test_start()
        return cloud_client.wait_for_boot(boot_reason=2, timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def execute_fuota_transition(
        self,
        device_id: str,
        from_targets: List[str],
        to_targets: List[str],
        description: str,
        cloud_client=None,
        device_type_id: int = 2,
        device_variant_id: int = 3,
        timeout_s: float = 7200,
    ) -> int:
        """Execute a complete FUOTA transition: create plan, assign, wait.

        Creates a 2-stage plan (from → to), assigns the device, and waits
        for completion. Optionally waits for FUOTA boot confirmation.

        Args:
            device_id: DevEUI hex string.
            from_targets: Stage 0 targets (current firmware version strings).
            to_targets: Stage 1 targets (target firmware version strings).
            description: Plan description.
            cloud_client: Optional CloudClient to verify FUOTA boot.
            device_type_id: CoreCloud device type ID.
            device_variant_id: CoreCloud device variant ID.
            timeout_s: Max wait for stage completion.

        Returns:
            planId of the created plan.
        """
        # CRITICAL: Ensure device is registered before FUOTA operations.
        # assign_device() fails with "Device not found" on unregistered devices.
        self.ensure_device_registered(device_id, device_type_id, device_variant_id)

        stages = [
            {
                "targets": from_targets,
                "description": f"From: {', '.join(from_targets)}",
                "isSkippable": False,
            },
            {
                "targets": to_targets,
                "description": f"To: {', '.join(to_targets)}",
                "isSkippable": False,
            },
        ]

        plan_id = self.create_plan(
            stages, description, device_type_id, device_variant_id,
        )

        if cloud_client:
            cloud_client.mark_test_start()

        self.assign_device(plan_id, [device_id], max_stage=1, enable=True)

        self._log.info("Waiting for FUOTA page delivery (LTE-M PSM cycle)...")
        self.wait_for_stage_complete(device_id, timeout_s=timeout_s)

        if cloud_client:
            self._log.info("Waiting for FUOTA reboot confirmation...")
            self.wait_for_fuota_boot(cloud_client, timeout_s=600)

        return plan_id
