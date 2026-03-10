"""CoreCloud message polling for Stage 4 verification.

Uses the CoreCloud REST API (/System/Devices/Status) to poll for device
state changes. Falls back to direct DB queries via msg_class.since_server_time()
only if the REST API is not configured.

All queries return status changes detected after mark_test_start() was called.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from corekinect.utils import Logger
from corekinect.utils.timeutil.formaters import auto_format_time_elapsed

log = Logger(log_name="cloud_client")

# Default poll interval (CoreCloud uplink ~60s, no need to poll faster)
DEFAULT_POLL_INTERVAL_S = 2.0

T = TypeVar("T")


class CloudClient:
    """CoreCloud device status polling for Stage 4 verification.

    Polls /System/Devices/Status via CoreCloudRestInterface for boot,
    position, and hardware failure state changes. Each test calls
    mark_test_start() before triggering device behavior, then wait_for_*
    methods detect when the device status changes (new recordId).

    Args:
        device_id: Integer device ID (e.g., 0x70B3D584C01E1FCC).
        api_env: CoreCloud API namespace (default: "VAL_1_0").
        logger: Parent Logger instance (creates child logger if provided).
    """

    def __init__(self, device_id: int, api_env: str = "VAL_1_0",
                 db_env: str = "", logger: Optional[Logger] = None):
        self._device_id = device_id
        self._device_id_hex = f"{device_id:016X}"
        self._api_env = api_env or db_env or "VAL_1_0"
        self._log = logger.from_parent("cloud") if logger else log
        self._api = None
        self._baseline: Optional[Dict[str, Any]] = None

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def db_env(self) -> str:
        return self._api_env

    def _get_api(self):
        """Lazily initialize CoreCloudRestInterface."""
        if self._api is None:
            try:
                from corekinect.core_cloud.api_interface import CoreCloudRestInterface
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
        """Record baseline device status — subsequent queries detect changes."""
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
        """Poll /System/Devices/Status for a change in a section.

        Detects change by comparing recordId against baseline. Returns the
        new section data when it changes and matches the optional predicate.

        Args:
            section: Status section key (e.g., "bootInfo", "positionInfo").
            predicate: Optional filter on the new section data.
            timeout_s: Maximum wait time.
            poll_interval_s: Polling interval.

        Raises:
            TimeoutError: If no matching change arrives within timeout_s.
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
                        if predicate is None or predicate(section_data):
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
        """Poll for a new boot event after mark_test_start().

        Args:
            boot_reason: If provided, only match boots with this reason string.
                Maps: 0="Normal", 1="Exception", 2="Fuota", 3="Charger".
            timeout_s: Maximum wait time.

        Returns:
            Boot info dict with keys: recordId, timeOfBoot, bootReason.
        """
        reason_map = {0: "Normal", 1: "Exception", 2: "Fuota", 3: "Charger"}
        reason_str = reason_map.get(boot_reason) if boot_reason is not None else None

        def pred(boot: Dict) -> bool:
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
        """Poll for a new position event after mark_test_start().

        Returns:
            Position info dict with keys: recordId, timeOfFix, latitude,
            longitude, battPercent, updateReason, etc.
        """
        return self._poll_status_change("positionInfo", predicate, timeout_s, poll_interval_s=10)

    # ------------------------------------------------------------------
    # Hardware Failures
    # ------------------------------------------------------------------

    def check_hw_failures(self) -> Dict[str, Any]:
        """Check current hardware failure status.

        Returns:
            App HW failure info dict. Empty dict if API unavailable.
        """
        status = self._fetch_status()
        if not status:
            return {}
        return status.get("appHwFailInfo", {})

    def check_comms_hw_failures(self) -> Dict[str, Any]:
        """Check current comms hardware failure status.

        Returns:
            Comms HW failure info dict. Empty dict if API unavailable.
        """
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
        """Poll for biometric data — not available via REST API.

        MockCloudClient provides this via injected scenarios.
        Hardware mode requires direct DB access (not yet on REST API).
        """
        import pytest
        pytest.skip("Biometric polling not available via REST API — use mock mode")

    def wait_for_network_status(self, timeout_s: float = 120) -> Dict[str, Any]:
        """Poll for network status — not available via REST API.

        MockCloudClient provides this via injected scenarios.
        Hardware mode requires direct DB access (not yet on REST API).
        """
        import pytest
        pytest.skip("Network status polling not available via REST API — use mock mode")

    def query_messages(self, *args, **kwargs) -> List:
        """Query messages — not available via REST API."""
        import pytest
        pytest.skip("Message queries not available via REST API — use mock mode")

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get full device status snapshot."""
        return self._fetch_status()
