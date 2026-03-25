"""CoreOps Proxy client for device ID assignment.

Calls the CoreOps proxy service (in-cluster) to get device IDs from SNRs.
The proxy handles all CoreOps authentication internally.

Usage:
    from corekinect.core_ops.proxy_client import CoreOpsProxyClient

    client = CoreOpsProxyClient()  # Uses default in-cluster URL
    device_id = client.assign_device_id("09J5")
    # Returns: "70B3D584C01E1DDD"

Environment:
    COREOPS_PROXY_URL: Override proxy URL (default: http://coreops-proxy)
"""

import os
from typing import Optional

import requests

from corekinect.utils import Logger

log = Logger(log_name="coreops_proxy")

# Default in-cluster service URL
DEFAULT_PROXY_URL = "http://coreops-proxy"


class CoreOpsProxyClient:
    """Client for CoreOps proxy service.

    The proxy runs in the K8s cluster and handles CoreOps authentication.
    This client just makes simple HTTP calls to the proxy.
    """

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
        logger: Optional[Logger] = None,
    ):
        """Initialize CoreOps proxy client.

        Args:
            proxy_url: Proxy service URL. Defaults to COREOPS_PROXY_URL env var
                       or http://coreops-proxy (in-cluster).
            timeout: Request timeout in seconds.
            logger: Optional logger instance.
        """
        self._url = proxy_url or os.environ.get("COREOPS_PROXY_URL", DEFAULT_PROXY_URL)
        self._timeout = timeout
        self._log = logger.from_parent("coreops") if logger else log
        self._session = requests.Session()

    def assign_device_id(self, snr: str) -> str:
        """Get device ID for a board serial number.

        CoreOps maintains a deterministic SNR → Device ID mapping.
        Calling multiple times with the same SNR returns the same ID.

        Args:
            snr: Board serial number (e.g., "09J5", "0964")

        Returns:
            Device ID as hex string (e.g., "70B3D584C01E1DDD")

        Raises:
            ValueError: If SNR is empty or response invalid
            requests.HTTPError: On proxy/CoreOps error
        """
        if not snr:
            raise ValueError("SNR is required")

        url = f"{self._url.rstrip('/')}/v1/devices/ids/assign"
        self._log.debug("Requesting device ID for SNR %s from %s", snr, url)

        resp = self._session.post(
            url,
            json={"snr": snr},
            timeout=self._timeout,
        )
        resp.raise_for_status()

        data = resp.json()
        device_id = data.get("deviceId")

        if not device_id:
            raise ValueError(f"No deviceId in response: {data}")

        self._log.info("SNR %s → Device ID %s", snr, device_id)
        return device_id

    def health_check(self) -> bool:
        """Check if the proxy is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            url = f"{self._url.rstrip('/')}/health"
            resp = self._session.get(url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
