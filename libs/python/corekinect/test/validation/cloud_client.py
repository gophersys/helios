"""CoreCloud message polling for Stage 4 verification.

Wraps existing corekinect.core_cloud SDK with timeout-based polling
suitable for black-box test verification. All queries return messages
received after mark_test_start() was called.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Callable, List, Optional, Type, TypeVar

from corekinect.core_cloud.msg_def_v1_0 import (
    AlphaHwFailureMsg,
    BiometricDataMsg,
    BootMsgV2,
    CommsHwFailureMsg,
    GPSConfMsg,
    MsgBase,
    NetworkStatusMsgV4,
    PositionMsgV6,
)

T = TypeVar("T", bound=MsgBase)

log = logging.getLogger(__name__)

# Default poll interval (CoreCloud uplink ~60s, no need to poll faster)
DEFAULT_POLL_INTERVAL_S = 2.0


class CloudClient:
    """CoreCloud message polling for Stage 4 verification.

    Wraps existing corekinect.core_cloud SDK with timeout-based polling.
    Each test calls mark_test_start() before triggering device behavior,
    then wait_for_* methods only return messages received after that point.

    Args:
        device_id: Integer device ID (e.g., 0x70B3D584C01E1FCC).
        db_env: CoreCloud namespace (default: "DEV_1_0").
            Devices personalized against dev.office.corekinect.cloud use DEV_1_0.
            Devices personalized against val.office.corekinect.cloud use VAL_1_0.
    """

    def __init__(self, device_id: int, db_env: str = "DEV_1_0"):
        self._device_id = device_id
        self._db_env = db_env
        self._test_start: Optional[datetime] = None

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def db_env(self) -> str:
        return self._db_env

    def mark_test_start(self) -> None:
        """Record timestamp — subsequent queries only return messages after this point."""
        self._test_start = datetime.now(timezone.utc)
        log.debug("Test start marked at %s", self._test_start.isoformat())

    def _require_test_start(self) -> datetime:
        if self._test_start is None:
            raise RuntimeError("mark_test_start() must be called before querying messages")
        return self._test_start

    def _poll(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]],
        timeout_s: float,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> T:
        """Poll CoreCloud for a message matching a predicate after test_start.

        Uses msg_class.since_server_time() to get messages in the window
        [test_start, now]. Returns the first message matching the predicate.

        Raises:
            TimeoutError: If no matching message arrives within timeout_s.
        """
        since = self._require_test_start()
        deadline = time.monotonic() + timeout_s
        last_err = None

        while time.monotonic() < deadline:
            try:
                msgs = msg_class.since_server_time(
                    self._device_id, since, db_env=self._db_env
                )
                if msgs:
                    for msg in msgs:
                        if predicate is None or predicate(msg):
                            return msg
            except Exception as e:
                last_err = e
                log.warning("Poll error for %s: %s", msg_class.__name__, e)

            time.sleep(poll_interval_s)

        err_detail = f" (last error: {last_err})" if last_err else ""
        raise TimeoutError(
            f"No {msg_class.__name__} matching predicate for device "
            f"{self._device_id:#X} within {timeout_s}s{err_detail}"
        )

    def _query_all(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]] = None,
    ) -> List[T]:
        """Query all messages of a type since test_start, optionally filtered."""
        since = self._require_test_start()
        msgs = msg_class.since_server_time(
            self._device_id, since, db_env=self._db_env
        )
        if predicate:
            return [m for m in msgs if predicate(m)]
        return msgs

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    def wait_for_boot(
        self,
        boot_reason: Optional[int] = None,
        timeout_s: float = 120,
    ) -> BootMsgV2:
        """Poll for BootMsgV2 after test_start.

        Args:
            boot_reason: If provided, only match boots with this reason.
                0=normal, 1=exception, 2=FUOTA complete, 3=charger.
            timeout_s: Maximum wait time.
        """
        def pred(b: BootMsgV2) -> bool:
            if boot_reason is not None and b.boot_reason != boot_reason:
                return False
            return True

        return self._poll(BootMsgV2, pred, timeout_s)

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def wait_for_position(
        self,
        predicate: Optional[Callable[[PositionMsgV6], bool]] = None,
        timeout_s: float = 300,
    ) -> PositionMsgV6:
        """Poll for PositionMsgV6 matching predicate after test_start.

        GPS acquisition can take several minutes, default 300s timeout.
        """
        return self._poll(PositionMsgV6, predicate, timeout_s, poll_interval_s=10)

    # ------------------------------------------------------------------
    # Biometric
    # ------------------------------------------------------------------

    def wait_for_biometric(
        self,
        predicate: Optional[Callable[[BiometricDataMsg], bool]] = None,
        timeout_s: float = 120,
    ) -> BiometricDataMsg:
        """Poll for BiometricDataMsg matching predicate after test_start."""
        return self._poll(BiometricDataMsg, predicate, timeout_s)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def wait_for_network_status(
        self, timeout_s: float = 120
    ) -> NetworkStatusMsgV4:
        """Poll for NetworkStatusMsgV4 confirming successful uplink."""
        def pred(n: NetworkStatusMsgV4) -> bool:
            return bool(n.did_lte_conn and n.did_sock_conn and n.send_success)

        return self._poll(NetworkStatusMsgV4, pred, timeout_s)

    # ------------------------------------------------------------------
    # Hardware Failures
    # ------------------------------------------------------------------

    def check_hw_failures(self) -> List[AlphaHwFailureMsg]:
        """Return all AlphaHwFailureMsg since test_start (empty = no failures)."""
        return self._query_all(AlphaHwFailureMsg)

    def check_comms_hw_failures(self) -> List[CommsHwFailureMsg]:
        """Return all CommsHwFailureMsg since test_start (empty = no failures)."""
        return self._query_all(CommsHwFailureMsg)

    # ------------------------------------------------------------------
    # Generic
    # ------------------------------------------------------------------

    def wait_for_message(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]] = None,
        timeout_s: float = 120,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> T:
        """Generic polling for any message type."""
        return self._poll(msg_class, predicate, timeout_s, poll_interval_s)

    def query_messages(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]] = None,
    ) -> List[T]:
        """Query all messages of a type since test_start."""
        return self._query_all(msg_class, predicate)
