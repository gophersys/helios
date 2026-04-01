"""Consolidated CoreCloud REST client.

Merges device management (search, register, status polling, key upload)
and FUOTA operations (plan create, CFW upload, device assignment, progress
monitoring) into a single client backed by CoreCloudRestInterface.

All public methods return typed dataclass models from ``core_cloud.models``
instead of raw dicts. The raw-dict methods are preserved with ``_raw``
suffix for backward compatibility during migration.

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
from corekinect.core_cloud.models import (
    BootInfo,
    CommsHwFailInfo,
    DeviceInfo,
    DeviceStatus,
    FuotaAssignResult,
    FuotaDeviceSettings,
    FuotaPlan,
    FuotaProgress,
    FuotaStage,
    GroundModeConfig,
    HwFailInfo,
    PositionInfo,
    RegistrationResult,
)

# Default poll intervals
_DEVICE_POLL_INTERVAL_S = 2.0
_FUOTA_POLL_INTERVAL_S = 30.0

# TLS verification -- overridable for self-signed certs in local dev
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


class CoreCloudClient:
    """Unified CoreCloud REST client for device and FUOTA operations.

    Wraps ``CoreCloudRestInterface`` for authenticated ``/api/`` requests
    and adds direct session calls for ``/singleton/`` FUOTA endpoints
    (which live outside the ``/api`` prefix).

    All public methods return typed dataclass models. For backward
    compatibility during migration, raw-dict methods are available
    with a ``_raw`` suffix (e.g. ``search_devices_raw``).

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
        # Strip /api suffix -- singleton endpoints sit outside it
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

    def search_devices(self, device_ids: List[str]) -> List[DeviceInfo]:
        """Search devices by ID, returning typed DeviceInfo objects.

        ``GET /api/System/Devices/Search`` with JSON body.

        Args:
            device_ids: List of DevEUI hex strings.

        Returns:
            List of DeviceInfo objects for found devices.
        """
        data = self.search_devices_raw(device_ids)
        raw_devices = data.get("devices", data if isinstance(data, list) else [])
        return [DeviceInfo.from_api(d) for d in raw_devices]

    def search_devices_raw(self, device_ids: List[str]) -> dict:
        """Search devices by ID (raw dict response).

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

    def get_device_status(self, device_ids: List[str]) -> List[DeviceStatus]:
        """Get device status (boot, position, HW failures) as typed objects.

        ``GET /api/System/Devices/Status`` with JSON body.

        Args:
            device_ids: List of DevEUI hex strings.

        Returns:
            List of DeviceStatus objects.
        """
        data = self.get_device_status_raw(device_ids)
        raw_devices = data.get("devices", [])
        return [DeviceStatus.from_api(d) for d in raw_devices]

    def get_device_status_raw(self, device_ids: List[str]) -> dict:
        """Get device status (raw dict response).

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

    def register_devices(
        self,
        devices: List[dict],
    ) -> RegistrationResult:
        """Register devices in CoreCloud.

        ``POST /api/System/Devices/Register``

        Each dict in *devices* should have keys: ``DeviceId``,
        ``DeviceType``, ``DeviceVariantId``.

        Returns:
            RegistrationResult with registered and already-registered lists.
        """
        resp = self._api_request(
            "POST", "/System/Devices/Register",
            json={"Devices": devices},
        )
        resp.raise_for_status()
        return RegistrationResult.from_api(resp.json())

    def ensure_device_registered(
        self,
        device_id: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> bool:
        """Ensure a device is registered; register if missing.

        Returns True if newly registered, False if already existed.
        """
        found = self.search_devices([device_id])
        for d in found:
            if d.device_id == device_id:
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
        if result.any_newly_registered:
            self.log.info("Device %s registered successfully", device_id)
            return True
        if result.already_registered:
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
                data = self.get_device_status_raw([device_id])
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
    # Configuration methods
    # ==================================================================

    def get_ground_mode_config(self, device_id: str) -> Optional[GroundModeConfig]:
        """Read current GroundModeConfigV2 for a device.

        ``POST /api/System/Devices/Configurations/GroundModeV2/Search``

        Args:
            device_id: DevEUI hex string.

        Returns:
            GroundModeConfig if found, None if device has no config.

        Raises:
            RuntimeError: If API returns non-200 status.
        """
        resp = self._api_request(
            "POST",
            "/System/Devices/Configurations/GroundModeV2/Search",
            json={"deviceIds": [device_id]},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GroundModeConfigV2 query failed: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )

        data = resp.json()
        configs = data.get("groundModeConfigurations", [])
        for cfg in configs:
            if cfg.get("deviceId") == device_id:
                return GroundModeConfig.from_api(cfg)

        self.log.warning("No GroundModeConfigV2 found for device %s", device_id)
        return None

    def set_ground_mode_config(
        self,
        device_id: str,
        config: GroundModeConfig,
    ) -> None:
        """Write GroundModeConfigV2 for a device.

        ``PUT /api/System/Devices/Configurations/GroundModeV2``

        The config object is serialized to the full API payload.
        CoreCloud requires all fields to be present in the PUT.

        Args:
            device_id: DevEUI hex string.
            config: GroundModeConfig with all fields populated.

        Raises:
            RuntimeError: If API returns non-200/204 status.
        """
        payload = config.to_api()
        payload["deviceId"] = device_id

        resp = self._api_request(
            "PUT",
            "/System/Devices/Configurations/GroundModeV2",
            json=payload,
        )
        if resp.status_code not in (200, 204):
            raise RuntimeError(
                f"GroundModeConfigV2 write failed: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )
        self.log.info("Config updated for %s", device_id)

    def update_ground_mode_config(
        self,
        device_id: str,
        **updates: Any,
    ) -> GroundModeConfig:
        """Read-modify-write GroundModeConfigV2 fields.

        Reads the current config, applies the given field updates,
        and writes the full config back. Returns the updated config.

        Args:
            device_id: DevEUI hex string.
            **updates: Field names (snake_case) and new values.
                Example: ``update_ground_mode_config(dev, gps_heartbeat_period=120)``

        Returns:
            The updated GroundModeConfig.

        Raises:
            RuntimeError: If current config cannot be read or write fails.
        """
        current = self.get_ground_mode_config(device_id)
        if current is None:
            raise RuntimeError(
                f"Cannot read current config for {device_id} -- cannot merge changes"
            )
        updated = current.with_updates(**updates)
        self.set_ground_mode_config(device_id, updated)
        return updated

    # ==================================================================
    # FUOTA methods
    # ==================================================================

    def list_fuota_plans(self) -> List[FuotaPlan]:
        """List all FUOTA plans as typed objects.

        ``GET /singleton/firmwareupdates/plans``

        Returns:
            List of FuotaPlan objects.
        """
        resp = self._singleton_request("GET", "firmwareupdates/plans")
        resp.raise_for_status()
        raw_plans = resp.json().get("fuotaPlans", [])
        return [FuotaPlan.from_api(p) for p in raw_plans]

    def create_fuota_plan(
        self,
        stages: List[FuotaStage],
        description: str = "",
        device_type_id: int = 2,
        device_variant_id: int = 3,
        ignore_target_app_ids: bool = False,
    ) -> FuotaPlan:
        """Create a FUOTA plan.

        ``POST /singleton/firmwareupdates/plans``

        Args:
            stages: List of FuotaStage objects defining the plan.
            description: Human-readable plan description.
            device_type_id: CoreCloud device type (2 = Alpha).
            device_variant_id: CoreCloud device variant (3 = Alpha B0).
            ignore_target_app_ids: If True, skip app ID validation.

        Returns:
            Created FuotaPlan including the assigned planId.

        Raises:
            RuntimeError: If plan creation fails.
        """
        payload = {
            "stages": [s.to_api() for s in stages],
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
        plan = FuotaPlan.from_api(resp.json())
        self.log.info("Plan created: id=%d", plan.plan_id)
        return plan

    def create_fuota_plan_from_dicts(
        self,
        stages: List[dict],
        description: str = "",
        device_type_id: int = 2,
        device_variant_id: int = 3,
        ignore_target_app_ids: bool = False,
    ) -> FuotaPlan:
        """Create a FUOTA plan from raw stage dicts (backward compatible).

        Each stage dict should have:
        - ``targets``: list of CFW version strings (e.g. ``["108.0.8.2-BMD"]``)
        - ``description``: human-readable label
        - ``isSkippable``: bool

        Returns:
            Created FuotaPlan including the assigned planId.
        """
        typed_stages = [FuotaStage.from_api(s) for s in stages]
        return self.create_fuota_plan(
            typed_stages, description, device_type_id,
            device_variant_id, ignore_target_app_ids,
        )

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

    def get_fuota_progress(self, device_id: str) -> Optional[FuotaProgress]:
        """Get FUOTA progress for a device.

        ``GET /singleton/firmwareupdates/progress?deviceId=<id>``

        Returns:
            FuotaProgress if transfer is active, None if no active
            transfer (404).
        """
        resp = self._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={device_id}",
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return FuotaProgress.from_api(resp.json())

    def assign_device_to_plan(
        self,
        device_id: str,
        plan_id: int,
        max_stage: int = 1000,
        enable: bool = True,
    ) -> FuotaAssignResult:
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
            FuotaAssignResult with count of updated devices.
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
        result = FuotaAssignResult.from_api(resp.json())
        self.log.info("Assignment result: %d devices updated", result.num_devices_updated)
        return result

    def get_device_fuota_settings(
        self,
        device_ids: Optional[List[str]] = None,
    ) -> List[FuotaDeviceSettings]:
        """Get FUOTA settings for devices.

        ``GET /singleton/firmwareupdates/settings/devices``

        CRITICAL: uses ``/settings/devices`` NOT ``/settings`` -- the latter
        returns empty results (known CoreCloud bug).

        Args:
            device_ids: Optional list of device IDs to filter. If None,
                returns all enrolled devices.

        Returns:
            List of FuotaDeviceSettings objects.
        """
        kwargs: Dict[str, Any] = {}
        if device_ids:
            kwargs["json"] = {"deviceIds": device_ids}
        resp = self._singleton_request(
            "GET", "firmwareupdates/settings/devices", **kwargs,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_devices = data.get("devicesFound", data if isinstance(data, list) else [])
        return [FuotaDeviceSettings.from_api(d) for d in raw_devices]

    def wait_for_fuota_complete(
        self,
        device_id: str,
        timeout_s: float = 7200,
        poll_interval_s: float = _FUOTA_POLL_INTERVAL_S,
    ) -> FuotaProgress:
        """Poll FUOTA progress until 100% or timeout.

        Args:
            device_id: DevEUI hex string.
            timeout_s: Maximum wait time (default 2h for LTE-M PSM wake).
            poll_interval_s: Polling interval.

        Returns:
            Final FuotaProgress at 100%.

        Raises:
            TimeoutError: If progress does not reach 100% within *timeout_s*.
        """
        deadline = time.monotonic() + timeout_s
        t0 = time.monotonic()
        last_pages = 0

        while time.monotonic() < deadline:
            progress = self.get_fuota_progress(device_id)

            if progress:
                if progress.pages_applied != last_pages:
                    elapsed = time.monotonic() - t0
                    self.log.info(
                        "FUOTA %s: %d/%d pages (%d%%) [%.0fs]",
                        progress.version, progress.pages_applied,
                        progress.total_pages, progress.percent_complete, elapsed,
                    )
                    last_pages = progress.pages_applied

                if progress.is_complete:
                    elapsed = time.monotonic() - t0
                    self.log.info(
                        "FUOTA complete: %s in %.0fs", progress.version, elapsed,
                    )
                    return progress
            else:
                self.log.debug("No FUOTA progress (404) -- transfer may not have started")

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
            FuotaStage(
                targets=from_targets,
                description=f"From: {', '.join(from_targets)}",
                is_skippable=False,
            ),
            FuotaStage(
                targets=to_targets,
                description=f"To: {', '.join(to_targets)}",
                is_skippable=False,
            ),
        ]

        plan = self.create_fuota_plan(
            stages, description, device_type_id, device_variant_id,
        )

        self.assign_device_to_plan(device_id, plan.plan_id, max_stage=1, enable=True)

        self.log.info("Waiting for FUOTA page delivery...")
        self.wait_for_fuota_complete(device_id, timeout_s=timeout_s)

        return plan.plan_id
