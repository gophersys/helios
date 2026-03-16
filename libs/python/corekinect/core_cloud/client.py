"""Consolidated CoreCloud REST client.

Merges device management (search, register, status polling, key upload)
and FUOTA operations (plan create, CFW upload, device assignment, progress
monitoring) into a single client backed by CoreCloudRestInterface.

Usage:
    # From env vars (test context)
    with CoreCloudClient(env_namespace="VAL_1_0") as client:
        devices = client.search_devices(["70B3D584C01E1FCC"])

    # Explicit creds
    with CoreCloudClient(
        auth_url="https://auth.office.corekinect.cloud:2013",
        api_url="https://val.office.corekinect.cloud:2018",
        username="user@example.com",
        password="...",
        api_key="..."
    ) as client:
        client.upload_device_key(device_id, pub_key_b64)
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from corekinect.core_cloud.api_interface import (
    ApiConfig,
    AuthConfig,
    CoreCloudRestInterface,
    _ensure_scheme,
)

# Default poll intervals
_DEVICE_POLL_INTERVAL_S = 2.0
_FUOTA_POLL_INTERVAL_S = 30.0

# TLS verification — overridable for self-signed certs in local dev
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


class CoreCloudClient:
    """Unified CoreCloud REST client for device and FUOTA operations.

    Wraps ``CoreCloudRestInterface`` for authenticated ``/api/`` requests
    and adds direct session calls for ``/singleton/`` FUOTA endpoints
    (which live outside the ``/api`` prefix).

    Parameters
    ----------
    env_namespace : str, optional
        Reads creds from env vars prefixed with this namespace
        (e.g. ``VAL_1_0_API_AUTH_USERNAME``).  Mutually exclusive with
        explicit credential arguments.
    auth_url : str, optional
        Auth server URL (e.g. ``https://auth.office.corekinect.cloud:2013``).
    api_url : str, optional
        REST API URL (e.g. ``https://val.office.corekinect.cloud:2018``).
    username : str, optional
        Auth username.
    password : str, optional
        Auth password.
    api_key : str, optional
        X-API-KEY value.
    logger : logging.Logger, optional
        Logger instance. Falls back to module-level logger.
    """

    def __init__(
        self,
        *,
        env_namespace: Optional[str] = None,
        auth_url: Optional[str] = None,
        api_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.log = logger or logging.getLogger("CoreCloudClient")

        # Build the internal interface from either explicit creds or env
        if auth_url or api_url or username or password or api_key:
            # Explicit credential mode
            auth_cfg = AuthConfig.__new__(AuthConfig)
            auth_cfg.server_host_name = auth_url
            auth_cfg.username = username
            auth_cfg.password = password
            auth_cfg.path = "/authentication/tokens/request"

            api_cfg = ApiConfig.__new__(ApiConfig)
            api_cfg.rest_server_host_name = api_url
            api_cfg.key = api_key
            api_cfg.timeout = 30.0
            api_cfg.verify_ssl = _TLS_VERIFY
            api_cfg.rate_limit_qps = 0.0
            api_cfg.default_scheme = "https"
            api_cfg.gps_config_path = "/System/Devices/Configurations/Gps"

            self._iface = CoreCloudRestInterface(
                env_namespace=None,
                auth=auth_cfg,
                api=api_cfg,
                logger=self.log,
            )
        else:
            ns = env_namespace or "VAL_1_0"
            self._iface = CoreCloudRestInterface(
                env_namespace=ns,
                logger=self.log,
            )

        # Base URL for /singleton/ endpoints (strip trailing /api if present)
        self._singleton_base: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "CoreCloudClient":
        self._iface.__enter__()
        host = str(self._iface.api.rest_server_host_name or "")
        base = _ensure_scheme(host, default_scheme=self._iface.api.default_scheme)
        # Strip /api suffix — singleton endpoints sit outside it
        self._singleton_base = base.rstrip("/").removesuffix("/api")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return self._iface.__exit__(exc_type, exc, tb)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_request(self, method: str, path: str, **kwargs) -> Any:
        """Authenticated request via CoreCloudRestInterface (``/api/`` prefix)."""
        return self._iface.request(method, path, **kwargs)

    def _singleton_request(self, method: str, path: str, **kwargs) -> Any:
        """Authenticated request to ``/singleton/`` endpoints (no /api prefix).

        Uses the underlying session + token from the interface directly.
        """
        sess = self._iface._require_session()
        token = self._iface._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-API-KEY": str(self._iface.api.key),
        }
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"
        url = f"{self._singleton_base}/singleton/{path.lstrip('/')}"
        resp = sess.request(
            method, url,
            headers=headers,
            verify=self._iface.api.verify_ssl,
            timeout=float(self._iface.api.timeout),
            **kwargs,
        )
        return resp

    # ==================================================================
    # Device methods
    # ==================================================================

    def search_devices(self, device_ids: List[str]) -> dict:
        """Search devices by ID.

        ``GET /api/System/Devices/Search`` with JSON body.

        Args:
            device_ids: List of DevEUI hex strings.

        Returns:
            Response JSON (typically ``{"devices": [...]}``)
        """
        resp = self._api_request(
            "GET", "/System/Devices/Search",
            json={"deviceIds": device_ids},
        )
        resp.raise_for_status()
        return resp.json()

    def get_device_status(self, device_ids: List[str]) -> dict:
        """Get device status (boot, position, HW failures).

        ``GET /api/System/Devices/Status`` with JSON body.

        Args:
            device_ids: List of DevEUI hex strings.

        Returns:
            Response JSON (typically ``{"devices": [...]}``)
        """
        resp = self._api_request(
            "GET", "/System/Devices/Status",
            json={"deviceIds": device_ids},
        )
        resp.raise_for_status()
        return resp.json()

    def register_devices(self, devices: List[dict]) -> dict:
        """Register devices in CoreCloud.

        ``POST /api/System/Devices/Register``

        Each dict in *devices* should have keys: ``DeviceId``,
        ``DeviceType``, ``DeviceVariantId``.

        Returns:
            Response JSON with ``registeredDevices`` and
            ``devicesAlreadyRegistered`` lists.
        """
        resp = self._api_request(
            "POST", "/System/Devices/Register",
            json={"Devices": devices},
        )
        resp.raise_for_status()
        return resp.json()

    def ensure_device_registered(
        self,
        device_id: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> bool:
        """Ensure a device is registered; register if missing.

        Returns True if newly registered, False if already existed.
        """
        data = self.search_devices([device_id])
        devices = data.get("devices", data if isinstance(data, list) else [])
        for d in devices:
            if d.get("deviceId") == device_id:
                self.log.info("Device %s already registered", device_id)
                return False

        self.log.info(
            "Registering device %s (type=%d, variant=%d)",
            device_id, device_type_id, device_variant_id,
        )
        result = self.register_devices([{
            "DeviceId": device_id,
            "DeviceType": device_type_id,
            "DeviceVariantId": device_variant_id,
        }])
        registered = result.get("registeredDevices", [])
        already = result.get("devicesAlreadyRegistered", [])
        if registered:
            self.log.info("Device %s registered successfully", device_id)
            return True
        if already:
            self.log.info("Device %s was already registered", device_id)
            return False
        raise RuntimeError(f"Unexpected registration result: {result}")

    def upload_device_key(self, device_id: str, pub_key_b64: str) -> bool:
        """Upload device EC public key (raw EC point, base64-encoded).

        ``POST /api/System/Devices/Sessions/Profiles``

        The key MUST be raw EC point bytes (starts with 0x04 uncompressed
        prefix, base64 starts with ``B``). NOT DER/SubjectPublicKeyInfo
        format (which starts with ``MFkw``).

        Args:
            device_id: DevEUI hex string.
            pub_key_b64: Base64-encoded raw EC point.

        Returns:
            True if upload succeeded (204), False otherwise.
        """
        resp = self._api_request(
            "POST", "/System/Devices/Sessions/Profiles",
            json={"deviceId": device_id, "publicKey": pub_key_b64},
        )
        if resp.status_code in (200, 204):
            self.log.info("Key uploaded for %s", device_id)
            return True
        self.log.warning(
            "Key upload failed for %s: %d %s",
            device_id, resp.status_code, resp.text[:200],
        )
        return False

    def poll_device_status(
        self,
        device_id: str,
        section: str = "bootInfo",
        baseline_record_id: int = 0,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        timeout_s: float = 120,
        poll_interval_s: float = _DEVICE_POLL_INTERVAL_S,
    ) -> Dict[str, Any]:
        """Poll device status until a section's recordId changes.

        Monitors ``/api/System/Devices/Status`` for a recordId increase in
        the given *section* (e.g. ``bootInfo``, ``positionInfo``).  Returns
        the new section data when detected.

        Args:
            device_id: DevEUI hex string.
            section: Status section key.
            baseline_record_id: recordId to compare against (0 = any).
            predicate: Optional filter on the new section data.
            timeout_s: Maximum wait time.
            poll_interval_s: Polling interval.

        Raises:
            TimeoutError: If no matching change within *timeout_s*.
        """
        deadline = time.monotonic() + timeout_s
        last_err = None

        while time.monotonic() < deadline:
            try:
                data = self.get_device_status([device_id])
                devices = data.get("devices", [])
                if devices:
                    section_data = devices[0].get(section, {})
                    rid = section_data.get("recordId", 0)
                    if rid > baseline_record_id:
                        if predicate is None or predicate(section_data):
                            self.log.info(
                                "%s changed (recordId %d -> %d)",
                                section, baseline_record_id, rid,
                            )
                            return section_data
            except Exception as e:
                last_err = e
                self.log.warning("Poll error for %s: %s", section, e)

            time.sleep(poll_interval_s)

        detail = f" (last error: {last_err})" if last_err else ""
        raise TimeoutError(
            f"No {section} change for device {device_id} "
            f"within {timeout_s}s{detail}"
        )

    # ==================================================================
    # FUOTA methods
    # ==================================================================

    def list_fuota_plans(self) -> List[dict]:
        """List all FUOTA plans.

        ``GET /singleton/firmwareupdates/plans``

        Returns:
            List of plan dicts.
        """
        resp = self._singleton_request("GET", "firmwareupdates/plans")
        resp.raise_for_status()
        return resp.json().get("fuotaPlans", [])

    def create_fuota_plan(
        self,
        stages: List[dict],
        description: str = "",
        device_type_id: int = 2,
        device_variant_id: int = 3,
        ignore_target_app_ids: bool = False,
    ) -> dict:
        """Create a FUOTA plan.

        ``POST /singleton/firmwareupdates/plans``

        Each stage dict should have:
        - ``targets``: list of CFW version strings (e.g. ``["108.0.8.2-BMD"]``)
        - ``description``: human-readable label
        - ``isSkippable``: bool

        Returns:
            Plan dict including ``planId``.
        """
        payload = {
            "stages": stages,
            "description": description,
            "deviceTypeId": device_type_id,
            "deviceVariantId": device_variant_id,
            "ignoreTargetAppIds": ignore_target_app_ids,
        }
        self.log.info("Creating FUOTA plan: %s (%d stages)", description, len(stages))
        resp = self._singleton_request("POST", "firmwareupdates/plans", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Plan creation failed: {resp.status_code} {resp.text[:300]}"
            )
        plan = resp.json()
        self.log.info("Plan created: id=%d", plan.get("planId", "?"))
        return plan

    def upload_firmware_image(self, cfw_path: str) -> bool:
        """Upload a .cfw firmware image to CoreCloud.

        ``POST /singleton/firmwareimages`` (multipart, field: ``image``)

        Args:
            cfw_path: Local path to ``.cfw`` file.

        Returns:
            True if uploaded (or already exists), False on failure.
        """
        p = Path(cfw_path)
        if not p.exists():
            raise FileNotFoundError(f"CFW file not found: {cfw_path}")

        self.log.info("Uploading CFW: %s (%d bytes)", p.name, p.stat().st_size)

        with open(p, "rb") as f:
            resp = self._singleton_request(
                "POST", "firmwareimages",
                files={"image": (p.name, f, "application/octet-stream")},
            )

        if resp.status_code == 400 and "already exists" in resp.text:
            self.log.info("CFW already uploaded: %s (skipping)", p.name)
            return True
        if resp.status_code in (200, 204):
            self.log.info("CFW uploaded: %s", p.name)
            return True
        self.log.warning(
            "CFW upload failed: %d %s", resp.status_code, resp.text[:200],
        )
        return False

    def delete_firmware_image(self, cfw_name: str) -> bool:
        """Delete a .cfw firmware image from CoreCloud.

        ``DELETE /singleton/firmwareimages?name=<name>``

        Returns:
            True if deleted, False if not found.
        """
        resp = self._singleton_request(
            "DELETE", f"firmwareimages?name={cfw_name}",
        )
        if resp.status_code == 404:
            self.log.info("CFW not found: %s", cfw_name)
            return False
        if resp.status_code in (200, 204):
            self.log.info("CFW deleted: %s", cfw_name)
            return True
        raise RuntimeError(
            f"CFW delete failed: {resp.status_code} {resp.text[:200]}"
        )

    def get_fuota_progress(self, device_id: str) -> Optional[dict]:
        """Get FUOTA progress for a device.

        ``GET /singleton/firmwareupdates/progress?deviceId=<id>``

        Returns:
            Progress dict (percentComplete, pagesApplied, totalPages, etc.)
            or None if no active transfer (404).
        """
        resp = self._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={device_id}",
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def assign_device_to_plan(
        self,
        device_id: str,
        plan_id: int,
        max_stage: int = 1000,
        enable: bool = True,
    ) -> dict:
        """Assign a device to a FUOTA plan.

        ``POST /singleton/firmwareupdates/settings/devices``

        Automatically ensures the device is registered first (FUOTA
        assignment fails on unregistered devices).

        Args:
            device_id: DevEUI hex string.
            plan_id: Plan ID from :meth:`create_fuota_plan`.
            max_stage: Maximum stage index the device should reach.
            enable: True to enable, False to disable FUOTA.

        Returns:
            Response dict with ``numDevicesUpdated``.
        """
        self.ensure_device_registered(device_id)

        payload = {
            "planId": plan_id,
            "enableFuota": enable,
            "maxStage": max_stage,
            "deviceIds": [device_id],
        }
        action = "Assigning" if enable else "Disabling"
        self.log.info("%s %s to plan %d", action, device_id, plan_id)

        resp = self._singleton_request(
            "POST", "firmwareupdates/settings/devices", json=payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Device assignment failed: {resp.status_code} {resp.text[:300]}"
            )
        result = resp.json()
        self.log.info("Assignment result: %s", result)
        return result

    def get_device_fuota_settings(self, device_ids: Optional[List[str]] = None) -> dict:
        """Get FUOTA settings for devices.

        ``GET /singleton/firmwareupdates/settings/devices``

        CRITICAL: uses ``/settings/devices`` NOT ``/settings`` — the latter
        returns empty results (known CoreCloud bug).

        Args:
            device_ids: Optional list of device IDs to filter. If None,
                returns all enrolled devices.

        Returns:
            Response JSON (typically ``{"devicesFound": [...]}``)
        """
        kwargs: Dict[str, Any] = {}
        if device_ids:
            kwargs["json"] = {"deviceIds": device_ids}
        resp = self._singleton_request(
            "GET", "firmwareupdates/settings/devices", **kwargs,
        )
        resp.raise_for_status()
        return resp.json()

    def wait_for_fuota_complete(
        self,
        device_id: str,
        timeout_s: float = 7200,
        poll_interval_s: float = _FUOTA_POLL_INTERVAL_S,
    ) -> bool:
        """Poll FUOTA progress until 100% or timeout.

        Args:
            device_id: DevEUI hex string.
            timeout_s: Maximum wait time (default 2h for LTE-M PSM wake).
            poll_interval_s: Polling interval.

        Returns:
            True if FUOTA completed (100%), False never (raises on timeout).

        Raises:
            TimeoutError: If progress does not reach 100% within *timeout_s*.
        """
        deadline = time.monotonic() + timeout_s
        t0 = time.monotonic()
        last_pages = 0

        while time.monotonic() < deadline:
            progress = self.get_fuota_progress(device_id)

            if progress:
                pages = progress.get("pagesApplied", 0)
                total = progress.get("totalPages", 1)
                pct = progress.get("percentComplete", 0)
                ver = progress.get("version", "?")

                if pages != last_pages:
                    elapsed = time.monotonic() - t0
                    self.log.info(
                        "FUOTA %s: %d/%d pages (%d%%) [%.0fs]",
                        ver, pages, total, pct, elapsed,
                    )
                    last_pages = pages

                if pct >= 100:
                    elapsed = time.monotonic() - t0
                    self.log.info(
                        "FUOTA complete: %s in %.0fs", ver, elapsed,
                    )
                    return True
            else:
                self.log.debug("No FUOTA progress (404) — transfer may not have started")

            time.sleep(poll_interval_s)

        raise TimeoutError(
            f"FUOTA for device {device_id} did not complete "
            f"within {timeout_s}s (last: {last_pages} pages)"
        )

    # ------------------------------------------------------------------
    # High-level FUOTA helper
    # ------------------------------------------------------------------

    def execute_fuota_transition(
        self,
        device_id: str,
        from_targets: List[str],
        to_targets: List[str],
        description: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
        timeout_s: float = 7200,
    ) -> int:
        """Execute a full FUOTA transition: plan creation, assignment, and wait.

        Creates a 2-stage plan (from -> to), assigns the device, and polls
        until the firmware delivery reaches 100%.

        Args:
            device_id: DevEUI hex string.
            from_targets: Stage 0 targets (current FW version strings).
            to_targets: Stage 1 targets (target FW version strings).
            description: Plan description.
            device_type_id: CoreCloud device type (2 = Alpha).
            device_variant_id: CoreCloud device variant (3 = B0).
            timeout_s: Max wait for stage completion.

        Returns:
            ``planId`` of the created plan.
        """
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

        plan = self.create_fuota_plan(
            stages, description, device_type_id, device_variant_id,
        )
        plan_id = plan["planId"]

        self.assign_device_to_plan(device_id, plan_id, max_stage=1, enable=True)

        self.log.info("Waiting for FUOTA page delivery...")
        self.wait_for_fuota_complete(device_id, timeout_s=timeout_s)

        return plan_id
