"""CoreOps REST client for device personalization.

Provides authenticated access to CoreOps server for:
- Device ID assignment (SNR → Device ID)
- Public key upload
- ICCID/SIM registration

Uses the same auth server as CoreCloud (auth.office.corekinect.cloud:2013)
with server-to-server credentials.

Environment variables (COREOPS_ prefix):
    COREOPS_SERVER_URL: CoreOps server URL (default: https://coreops.office.corekinect.cloud:2013)
    COREOPS_AUTH_SERVER_URL: Auth server URL (default: https://auth.office.corekinect.cloud:2013)
    COREOPS_API_KEY: API key for X-API-KEY header
    COREOPS_AUTH_USER: Auth username for Basic auth
    COREOPS_AUTH_PASS: Auth password for Basic auth
    COREOPS_VERIFY_SSL: Verify SSL certs (default: false for internal network)
    COREOPS_TIMEOUT: Request timeout in seconds (default: 10)

Example:
    with CoreOpsClient() as client:
        device_id = client.assign_device_id("0964")
        client.upload_public_key(device_id, "BF2g...")
        client.save_iccid("89148000...", "Verizon", "0964", "355025...")
"""

import atexit
import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
from dotenv import load_dotenv
from requests import Session

from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="core_ops")


class CoreOpsConfig(EnvConfig):
    """CoreOps client configuration from environment variables."""

    ENV_PREFIX = "COREOPS_"

    # Server URLs
    server_url: str = "https://coreops.office.corekinect.cloud:2013"
    auth_server_url: str = "https://auth.office.corekinect.cloud:2013"

    # Auth credentials (server-to-server)
    api_key: Optional[str] = None
    auth_user: Optional[str] = None
    auth_pass: Optional[str] = None

    # Request settings — TLS verification enabled by default for security
    verify_ssl: bool = True
    timeout: float = 10.0


@dataclass
class DeviceAssignment:
    """Result of device ID assignment."""
    device_id: str
    snr: str


class CoreOpsClient:
    """REST client for CoreOps device personalization endpoints.

    Handles authentication via the shared Corekinect auth server and
    provides methods for the 3 main personalization operations.

    Thread-safe via session management. Can be used as context manager.

    Args:
        config: Optional CoreOpsConfig. If not provided, loads from env vars.
        logger: Optional logger instance.
    """

    def __init__(
        self,
        config: Optional[CoreOpsConfig] = None,
        logger: Optional[Logger] = None,
    ):
        """  init  ."""
        load_dotenv(override=False)

        self._config = config or CoreOpsConfig()
        self._log = logger.from_parent("coreops") if logger else log
        self._session: Optional[Session] = None
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._depth = 0

        # Validate required config
        if not self._config.api_key:
            raise ValueError("COREOPS_API_KEY is required")
        if not self._config.auth_user or not self._config.auth_pass:
            raise ValueError("COREOPS_AUTH_USER and COREOPS_AUTH_PASS are required")

        # Register cleanup
        if not hasattr(self, "_atexit_reg"):
            atexit.register(self._teardown)
            self._atexit_reg = True

    @classmethod
    def from_env(cls, logger: Optional[Logger] = None) -> "CoreOpsClient":
        """Build a :class:`CoreOpsClient` from ``COREOPS_*`` env vars.

        Convenience factory for parity with the other corekinect
        service clients (:class:`ConcordReporter.from_env`,
        :class:`MtibV1Client` config). Identical to ``CoreOpsClient()``
        — :class:`CoreOpsConfig` already auto-reads the env on
        construction — but the explicit ``from_env`` name makes the
        intent obvious at call sites and matches the convention.
        """
        return cls(config=CoreOpsConfig(), logger=logger)

    def __enter__(self) -> "CoreOpsClient":
        """  enter  ."""
        if self._depth > 0:
            self._depth += 1
            return self
        self._depth = 1
        self._session = requests.Session()
        # Fetch token immediately to fail fast on bad creds
        self._ensure_token()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """  exit  ."""
        if self._depth <= 1:
            self._teardown()
            self._depth = 0
        else:
            self._depth -= 1
        return False

    def _teardown(self) -> None:
        """ teardown."""
        if self._session:
            try:
                self._session.close()
            finally:
                self._session = None
        self._token = None
        self._token_expiry = 0.0

    def _get_session(self) -> Session:
        """ get session."""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _basic_auth_header(self) -> str:
        """Build Basic auth header from credentials."""
        raw = f"{self._config.auth_user}:{self._config.auth_pass}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _ensure_token(self) -> str:
        """Fetch or return cached auth token."""
        now = time.time()
        if self._token and now < self._token_expiry - 30:
            return self._token

        # Fetch new token — uses client_credentials grant + X-API-KEY header
        url = f"{self._config.auth_server_url.rstrip('/')}/Authentication/Tokens/Request"
        headers = {
            "Authorization": self._basic_auth_header(),
            "X-API-KEY": self._config.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        sess = self._get_session()
        resp = sess.post(
            url,
            data={"grant_type": "client_credentials"},
            headers=headers,
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()

        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("accessToken")
        )
        if not token:
            raise RuntimeError(f"No token in auth response: {list(data.keys())}")

        expires_in = data.get("expires_in") or data.get("expiresIn") or 600
        self._token_expiry = now + float(expires_in)
        self._token = token
        self._log.debug("Auth token acquired, expires in %ds", expires_in)
        return token

    def _auth_headers(self) -> dict:
        """Build authenticated request headers."""
        token = self._ensure_token()
        return {
            "Authorization": f"Bearer {token}",
            "X-API-KEY": self._config.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> requests.Response:
        """Make authenticated request with auto-retry on 401."""
        url = f"{self._config.server_url.rstrip('/')}{path}"
        sess = self._get_session()
        headers = self._auth_headers()

        resp = sess.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
        )

        # Retry once on 401 (token expired)
        if resp.status_code == 401:
            self._token = None
            headers = self._auth_headers()
            resp = sess.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
            )

        return resp

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def search_board_assembly(self, snr: str) -> dict:
        """Search for a board assembly by serial number.

        Returns panel information including all boards and their positions.
        Used for panel manufacturing to resolve per-slot SNRs from a
        single scanned barcode.

        Args:
            snr: Board serial number (scanned from panel or individual DUT)

        Returns:
            Dict with keys:
                panelSerialNumber: Panel barcode (None for singletons)
                boards: List of {panelPosition, boardSerialNumber}

        Raises:
            requests.HTTPError: On API error
        """
        resp = self._request(
            "GET",
            "/boards/assemblies/search",
            params={"boardSerialNumber": snr},
        )
        resp.raise_for_status()
        return resp.json()

    def assign_device_id(self, snr: str) -> str:
        """Assign a device ID for a board serial number.

        CoreOps maintains a deterministic mapping from SNR to device ID.
        Calling this multiple times with the same SNR returns the same ID.

        Args:
            snr: Board serial number (e.g., "0964")

        Returns:
            Device ID as hex string (e.g., "70B3D584C01E1FCC")

        Raises:
            requests.HTTPError: On API error
            ValueError: If response doesn't contain deviceId
        """
        resp = self._request(
            "POST",
            "/devices/ids/assign",
            params={"boardSerialNumber": snr},
        )
        resp.raise_for_status()

        data = resp.json()
        device_id = data.get("deviceId")
        if not device_id:
            raise ValueError(f"No deviceId in response: {data}")

        self._log.info("Assigned device ID %s to SNR %s", device_id, snr)
        return device_id

    def upload_public_key(self, device_id: str, public_key: str) -> None:
        """Upload device public key to CoreOps.

        The public key must be the raw EC P-256 point in base64 format
        (65 bytes starting with 0x04, NOT DER/SubjectPublicKeyInfo).

        Args:
            device_id: Device ID hex string
            public_key: Raw EC public key in base64 (starts with "B" when base64-encoded)

        Raises:
            requests.HTTPError: On API error
        """
        resp = self._request(
            "POST",
            "/devices/publickeys/save",
            json={"DeviceId": device_id, "PublicKey": public_key},
        )
        resp.raise_for_status()
        self._log.info("Uploaded public key for device %s", device_id)

    def save_iccid(
        self,
        iccid: str,
        carrier: str,
        snr: str,
        imei: str,
    ) -> None:
        """Register an ICCID (SIM card) with the device.

        Args:
            iccid: SIM card ICCID (e.g., "89148000009808567681")
            carrier: Carrier name (e.g., "Verizon", "Onomondo", "Soracom")
            snr: Board serial number
            imei: Device IMEI

        Raises:
            requests.HTTPError: On API error (except 400 "already exists")
        """
        resp = self._request(
            "POST",
            "/iccids/register",
            json={
                "Iccid": iccid,
                "Carrier": carrier,
                "boardSerialNumber": snr,
                "Imei": imei,
            },
        )

        # 400 with "AlreadyExists" is OK (idempotent)
        if resp.status_code == 400:
            try:
                data = resp.json()
                if data.get("code") == "Iccids.AlreadyExists":
                    self._log.debug("ICCID %s already registered", iccid)
                    return
            except Exception:
                pass

        resp.raise_for_status()
        self._log.info("Registered ICCID %s (%s) for SNR %s", iccid, carrier, snr)

    def save_iccids(
        self,
        iccids: List[str],
        carriers: List[str],
        snr: str,
        imei: str,
    ) -> None:
        """Register multiple ICCIDs for a device.

        Args:
            iccids: List of SIM card ICCIDs
            carriers: List of carrier names (same length as iccids)
            snr: Board serial number
            imei: Device IMEI
        """
        if len(iccids) != len(carriers):
            raise ValueError("iccids and carriers must have same length")

        for iccid, carrier in zip(iccids, carriers):
            self.save_iccid(iccid, carrier, snr, imei)
