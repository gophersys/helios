"""CoreCloud device status polling for test verification.

Polls /System/Devices/Status for state changes (boot, position, HW
failures) that occur after mark_test_start(). Used by tests to verify
that the device reacted to a stimulus.

    client = CloudClient(device_id=0x70B3D584C01E1FCC)
    client.mark_test_start()
    # ... trigger device behavior ...
    boot = client.wait_for_boot(timeout_s=120)
"""

import re
import time
from typing import Any, Callable, Dict, List, Optional

from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.errors import CloudError
from corekinect.utils import Logger
from corekinect.utils.timeutil.formaters import auto_format_time_elapsed

log = Logger(log_name="cloud_client")

# Device ID validation pattern: 16 hex characters
_DEVICE_ID_PATTERN = re.compile(r'^[0-9A-Fa-f]{16}$')


def validate_device_id(device_id: str) -> bool:
    """Return True if device_id is a valid 16-character hex string."""
    return bool(_DEVICE_ID_PATTERN.match(device_id))

# Default poll interval (CoreCloud uplink ~60s, no need to poll faster)
DEFAULT_POLL_INTERVAL_S = 2.0

class CloudClient:
    """Poll CoreCloud /System/Devices/Status for state changes.

    Call mark_test_start() before triggering device behavior, then use
    wait_for_boot() / wait_for_position() to detect when the device
    status changes (new recordId).

    Args:
        device_id: Integer device ID (e.g., 0x70B3D584C01E1FCC).
        api_env: CoreCloud namespace (default: "VAL_1_0").
    """

    def __init__(self, device_id: int, api_env: str = "VAL_1_0",
                 db_env: str = "", logger: Optional[Logger] = None):
        """  init  ."""
        self._device_id = device_id
        self._device_id_hex = f"{device_id:016X}"

        # Validate the computed hex string
        if not validate_device_id(self._device_id_hex):
            raise ValueError(f"Invalid device ID: {device_id} (hex: {self._device_id_hex})")

        self._api_env = api_env or db_env or "VAL_1_0"
        self._log = logger.from_parent("cloud") if logger else log
        self._api = None
        self._baseline: Optional[Dict[str, Any]] = None

    @property
    def device_id(self) -> int:
        """Device id."""
        return self._device_id

    @property
    def db_env(self) -> str:
        """Db env."""
        return self._api_env

    def _get_api(self):
        """Lazily initialize CoreCloudRestInterface."""
        if self._api is None:
            try:
                self._api = CoreCloudRestInterface(env_namespace=self._api_env)
                self._api.__enter__()
                self._log.info("REST API connected (env=%s)", self._api_env)
            except (ValueError, RuntimeError, ImportError) as e:
                self._log.warning("REST API unavailable: %s", e)
                self._api = False  # sentinel: tried and failed
        return self._api if self._api else None

    def _fetch_status(self) -> Optional[Dict[str, Any]]:
        """Fetch current device status from REST API."""
        api = self._get_api()
        if not api:
            return None
        try:
            resp = api.request(
                "GET", "/System/Devices/Status",
                json={"deviceIds": [self._device_id_hex]},
            )
            if resp.status_code == 200:
                devices = resp.json().get("devices", [])
                if devices:
                    return devices[0]
        except Exception as e:
            self._log.warning("Status fetch failed: %s", e)
        return None

    def mark_test_start(self) -> None:
        """Snapshot current device status as baseline for change detection."""
        self._baseline = self._fetch_status()
        if self._baseline:
            self._log.debug(
                "Baseline: boot=%s, pos=%s",
                self._baseline.get("bootInfo", {}).get("recordId", 0),
                self._baseline.get("positionInfo", {}).get("recordId", 0),
            )
        else:
            self._log.debug("No baseline available (API not configured)")

    def _poll_status_change(
        self,
        section: str,
        predicate: Optional[Callable[[Dict[str, Any]], bool]],
        timeout_s: float,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> Dict[str, Any]:
        """Poll for a recordId change in a status section.

        Returns the new section data when it changes and matches the
        optional predicate.

        Raises:
            TimeoutError: If no matching change within timeout_s.
        """
        baseline_record_id = 0
        if self._baseline:
            baseline_record_id = self._baseline.get(section, {}).get("recordId", 0)

        deadline = time.monotonic() + timeout_s
        t0 = time.monotonic()
        last_err = None

        while time.monotonic() < deadline:
            try:
                status = self._fetch_status()
                if status:
                    section_data = status.get(section, {})
                    current_record_id = section_data.get("recordId", 0)
                    if current_record_id > baseline_record_id:
                        if predicate is not None:
                            try:
                                pred_ok = predicate(section_data)
                            except Exception as exc:
                                self._log.warning("Predicate raised: %s", exc)
                                continue
                        else:
                            pred_ok = True
                        if pred_ok:
                            elapsed = auto_format_time_elapsed(time.monotonic() - t0)
                            self._log.info(
                                "%s changed after %s (recordId %d -> %d)",
                                section, elapsed, baseline_record_id, current_record_id,
                            )
                            return section_data
            except Exception as e:
                last_err = e
                self._log.warning("Poll error for %s: %s", section, e)

            time.sleep(poll_interval_s)

        err_detail = f" (last error: {last_err})" if last_err else ""
        raise TimeoutError(
            f"No {section} change for device {self._device_id_hex} "
            f"within {timeout_s}s{err_detail}"
        )

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    def wait_for_boot(
        self,
        boot_reason: Optional[int] = None,
        timeout_s: float = 120,
    ) -> Dict[str, Any]:
        """Wait for a new boot event after mark_test_start().

        Args:
            boot_reason: Filter by reason: 0=Normal, 1=Exception, 2=Fuota, 3=Charger.
        """
        reason_map = {0: "Normal", 1: "Exception", 2: "Fuota", 3: "Charger"}
        reason_str = reason_map.get(boot_reason) if boot_reason is not None else None

        def pred(boot: Dict) -> bool:
            """Pred."""
            if reason_str is not None and boot.get("bootReason") != reason_str:
                return False
            return True

        return self._poll_status_change("bootInfo", pred, timeout_s)

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def wait_for_position(
        self,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        timeout_s: float = 300,
    ) -> Dict[str, Any]:
        """Wait for a new position event after mark_test_start()."""
        return self._poll_status_change("positionInfo", predicate, timeout_s, poll_interval_s=10)

    # ------------------------------------------------------------------
    # Hardware Failures
    # ------------------------------------------------------------------

    def check_hw_failures(self) -> Dict[str, Any]:
        """Return app HW failure info, or empty dict if API unavailable."""
        status = self._fetch_status()
        if not status:
            return {}
        return status.get("appHwFailInfo", {})

    def check_comms_hw_failures(self) -> Dict[str, Any]:
        """Return comms HW failure info, or empty dict if API unavailable."""
        status = self._fetch_status()
        if not status:
            return {}
        return status.get("commsHwFailInfo", {})

    # ------------------------------------------------------------------
    # Generic
    # ------------------------------------------------------------------

    def wait_for_biometric(
        self,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        timeout_s: float = 120,
    ) -> Dict[str, Any]:
        """Not available via REST API. Use mock mode for testing."""
        raise NotImplementedError("Biometric polling not available via REST API — use mock mode")

    def wait_for_network_status(self, timeout_s: float = 120) -> Dict[str, Any]:
        """Not available via REST API. Use mock mode for testing."""
        raise NotImplementedError("Network status polling not available via REST API — use mock mode")

    def query_messages(self, *args, **kwargs) -> List:
        """Not available via REST API. Use mock mode for testing."""
        raise NotImplementedError("Message queries not available via REST API — use mock mode")

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Return full device status snapshot, or None if API unavailable."""
        return self._fetch_status()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_ground_mode_config(self) -> Optional[Dict[str, Any]]:
        """Read current GroundModeConfigV2 from CoreCloud.

        Returns None if API unavailable.

        Raises:
            CloudError: If API returns non-200 status.
        """
        api = self._get_api()
        if not api:
            return None

        resp = api.request(
            "POST",
            "/System/Devices/Configurations/GroundModeV2/Search",
            json={"deviceIds": [self._device_id_hex]},
        )
        if resp.status_code != 200:
            raise CloudError(
                f"GroundModeConfigV2 query failed: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )

        data = resp.json()
        configs = data.get("groundModeConfigurations", [])
        if not configs:
            self._log.warning("No GroundModeConfigV2 found for device %s", self._device_id_hex)
            return None

        # Find our device's config (there should be exactly one)
        for cfg in configs:
            if cfg.get("deviceId") == self._device_id_hex:
                return cfg

        self._log.warning(
            "Device %s not in config response (got %d devices)",
            self._device_id_hex, len(configs),
        )
        return None

    def set_ground_mode_config(
        self,
        config_values: Dict[str, Any],
    ) -> None:
        """Write GroundModeConfigV2 to CoreCloud.

        Reads current config, merges changes, then PUTs the full object
        (CoreCloud requires all fields in the PUT payload).

        Args:
            config_values: Fields to update in camelCase.
                Example: {"gpsHeartbeatPeriod": 120}

        Raises:
            CloudError: If API fails or current config can't be read.
        """
        api = self._get_api()
        if not api:
            raise CloudError("CoreCloud REST API not available")

        # Read current config — PUT requires ALL fields
        current = self.get_ground_mode_config()
        if current is None:
            raise CloudError(
                f"Cannot read current config for {self._device_id_hex} — "
                f"cannot merge changes"
            )

        # Merge changes into full config
        payload = {**current, **config_values}

        resp = api.request(
            "PUT",
            "/System/Devices/Configurations/GroundModeV2",
            json=payload,
        )
        if resp.status_code not in (200, 204):
            raise CloudError(
                f"GroundModeConfigV2 write failed: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )
        self._log.info(
            "Config updated for %s: %s",
            self._device_id_hex, config_values,
        )

    def wait_for_config_change(
        self,
        field: str,
        expected_value: Any,
        timeout_s: float = 180,
        poll_interval_s: float = 10,
    ) -> Dict[str, Any]:
        """Poll until a config field matches the expected value.

        Use after set_ground_mode_config() to verify the device applied
        the new config.

        Raises:
            TimeoutError: If field doesn't match within timeout_s.
            CloudError: If API query fails.
        """
        deadline = time.monotonic() + timeout_s
        t0 = time.monotonic()

        while time.monotonic() < deadline:
            config = self.get_ground_mode_config()
            if config and config.get(field) == expected_value:
                elapsed = auto_format_time_elapsed(time.monotonic() - t0)
                self._log.info(
                    "Config %s reached %s after %s",
                    field, expected_value, elapsed,
                )
                return config

            if config:
                self._log.debug(
                    "Config %s = %s (waiting for %s)",
                    field, config.get(field), expected_value,
                )

            time.sleep(poll_interval_s)

        current = self.get_ground_mode_config()
        current_val = current.get(field) if current else "N/A"
        raise TimeoutError(
            f"Config field '{field}' did not reach {expected_value} "
            f"within {timeout_s}s (current: {current_val})"
        )
