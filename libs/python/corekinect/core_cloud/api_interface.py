import atexit
import base64
import logging
import os
import time
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Sequence, Union

import requests
from dotenv import load_dotenv
from requests import Response, Session

from corekinect.utils import EnvConfig
from corekinect.utils import SingletonThreadSafeMeta


def _ensure_scheme(host_or_url: str, default_scheme: str = "https") -> str:
    """ ensure scheme."""
    if "://" not in host_or_url:
        return f"{default_scheme}://{host_or_url}"
    return host_or_url


def _ensure_url(host_or_url: str, path: str, *, default_scheme: str = "https") -> str:
    """ ensure url."""
    if not host_or_url:
        raise ValueError("Missing host for URL construction.")
    base = _ensure_scheme(host_or_url, default_scheme=default_scheme).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _apply_namespace_env(ns: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]]) -> None:
    """
    Copies namespaced variables like DEV_1_0_API_AUTH_USERNAME -> API_AUTH_USERNAME
    so EnvConfig classes can read them via fixed ENV_PREFIX keys.
    """
    if not ns:
        return
    ns = ns.rstrip("_") + "_"

    def copy_first_present(target_key: str, candidates: Sequence[str]) -> None:
        """Copy first present."""
        for c in candidates:
            v = os.getenv(c)
            if v is not None and v != "":
                os.environ[target_key] = v
                return

    # Primary map (aliases in priority order where useful)
    alias_map: Mapping[str, Sequence[str]] = {
        # Auth side
        "AUTH_SERVER_HOST_NAME": [f"{ns}API_AUTH_SERVER_HOST_NAME", f"{ns}AUTH_SERVER_HOST_NAME"],
        "AUTH_USERNAME": [f"{ns}API_AUTH_USERNAME", f"{ns}AUTH_USERNAME"],
        "AUTH_PASSWORD": [f"{ns}API_AUTH_PASSWORD", f"{ns}AUTH_PASSWORD"],
        "AUTH_PATH": [f"{ns}API_AUTH_PATH", f"{ns}AUTH_PATH"],  # default provided below
        # API side
        "API_REST_SERVER_HOST_NAME": [f"{ns}API_REST_SERVER_HOST_NAME", f"{ns}API_SERVER_HOST_NAME", f"{ns}API_HOST"],
        "API_KEY": [f"{ns}API_KEY"],
        "API_TIMEOUT": [f"{ns}API_TIMEOUT"],
        "API_VERIFY_SSL": [f"{ns}API_VERIFY_SSL", f"{ns}VERIFY_SSL"],
        "API_RATE_LIMIT_QPS": [f"{ns}API_RATE_LIMIT_QPS"],
        "API_DEFAULT_SCHEME": [f"{ns}API_DEFAULT_SCHEME"],
    }

    for target, sources in alias_map.items():
        copy_first_present(target, sources)


class AuthConfig(EnvConfig):
    """
    ENV_PREFIX: AUTH_
      - AUTH_SERVER_HOST_NAME
      - AUTH_USERNAME
      - AUTH_PASSWORD
      - AUTH_PATH (optional; default '/authentication/tokens/request')
    """

    ENV_PREFIX = "AUTH_"

    server_host_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    path: str = "/authentication/tokens/request"  # token endpoint path


class ApiConfig(EnvConfig):
    """
    ENV_PREFIX: API_
      - API_REST_SERVER_HOST_NAME
      - API_KEY
      - API_TIMEOUT (seconds; default 30)
      - API_VERIFY_SSL (bool or path to CA bundle; default True)
      - API_RATE_LIMIT_QPS (float; default 0 → no throttling)
      - API_DEFAULT_SCHEME ('https' or 'http'; default 'https')
      - API_GPS_CONFIG_PATH (optional; default '/System/Devices/Configurations/Gps')
    """

    ENV_PREFIX = "API_"

    rest_server_host_name: Optional[str] = None
    key: Optional[str] = None
    timeout: float = 30.0
    verify_ssl: Union[bool, str, Path] = True
    rate_limit_qps: float = 0.0
    default_scheme: str = "https"
    gps_config_path: str = "/System/Devices/Configurations/Gps"


class CoreCloudRestInterface(metaclass=SingletonThreadSafeMeta):
    """
    Context-managed REST interface with namespaced ENV settings, token fetch, and
    automatic refresh on 401. Mirrors the style of CoreCloudDBInterface.

    Attributes:
        auth (AuthConfig): Auth configuration with server, username, password.
        api (ApiConfig): API configuration with REST server, key, timeout, etc.
        env_namespace (Optional[str]): Namespace for environment variables, e.g. "DEV_1_0".
        test_auth_on_enter (bool): If True, fetches token on __enter__ to fail early if creds are wrong.

    Example:
        with CoreCloudRestInterface(env_namespace="DEV_1_0") as api:
            r = api.put_gps_config("70B3D584C01E1492", template_payload)
            r.raise_for_status()
    """

    def __init__(
        self,
        *,
        env_namespace: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]] = "DEV_1_0",
        auth: Optional[AuthConfig] = None,
        api: Optional[ApiConfig] = None,
        test_auth_on_enter: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """  init  ."""
        self._depth = 0
        self.log = logger or logging.getLogger(self.__class__.__name__)

        load_dotenv(override=False)
        _apply_namespace_env(env_namespace)

        self.auth = auth or AuthConfig(namespace=env_namespace)
        self.api = api or ApiConfig(namespace=env_namespace)

        self._session: Optional[Session] = None
        self._token: Optional[str] = None
        self._token_expiry_ts: Optional[float] = None  # epoch seconds
        self._last_request_ts: float = 0.0

        # Clean up on exit
        if not hasattr(self, "_atexit_reg"):
            atexit.register(self._teardown)
            self._atexit_reg = True

        # Pre-flight sanity
        if not self.auth.server_host_name:
            raise ValueError("AUTH_SERVER_HOST_NAME is required (via env).")
        if not self.api.rest_server_host_name:
            raise ValueError("API_REST_SERVER_HOST_NAME is required (via env).")
        if not self.auth.username or not self.auth.password:
            raise ValueError("AUTH_USERNAME and AUTH_PASSWORD are required (via env).")
        if not self.api.key:
            raise ValueError("API_KEY is required (via env).")

        # Prepare session now (token fetched on-demand or on enter)
        self._session = requests.Session()

        # Normalize verify path if provided
        if isinstance(self.api.verify_ssl, Path):
            self.api.verify_ssl = str(self.api.verify_ssl)

        self._test_auth_on_enter = test_auth_on_enter

    def __enter__(self) -> "CoreCloudRestInterface":
        """  enter  ."""
        if self._depth > 0:
            self._depth += 1
            return self
        self._depth = 1
        try:
            if self._test_auth_on_enter:
                # fetch token immediately so we fail early if creds are wrong
                self._ensure_token()
                # Also verify REST API access - wrong API key causes 401 even with valid token
                self._verify_api_access()
            return self
        except Exception:
            self._depth = 0
            self._teardown()
            raise

    def _verify_api_access(self) -> None:
        """Verify REST API is accessible with current credentials.

        Auth token acquisition can succeed but REST API calls fail with 401
        if the API key is wrong. This catches that early with a clear error.
        """
        try:
            # Make a minimal API call to verify access
            resp = self.request("GET", "/System/Devices/Search", json={"deviceIds": []})
            if resp.status_code == 401:
                raise RuntimeError(
                    "CoreCloud REST API returned 401 Unauthorized. "
                    "Token was acquired successfully but API rejects requests. "
                    "CHECK VAL_1_0_API_KEY - the key in K8s secrets may be wrong. "
                    f"Expected key starts with 'KWh0dHBz' (for VAL environment). "
                    f"Current key starts with '{str(self.api.key)[:10]}...'"
                )
        except requests.RequestException as e:
            raise RuntimeError(f"CoreCloud REST API connectivity check failed: {e}")

    def __exit__(self, exc_type, exc, tb) -> bool:
        """  exit  ."""
        if self._depth <= 1:
            self._teardown()
            self._depth = 0
        else:
            self._depth -= 1
        return False  # do not suppress exceptions

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Response:
        """
        Perform an authenticated request. Auto-refreshes token on 401 once.
        """
        self._maybe_throttle()

        token = self._ensure_token()
        url = _ensure_url(self.api.rest_server_host_name, path, default_scheme=self.api.default_scheme)

        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-API-KEY": str(self.api.key),
        }
        if headers:
            h.update(headers)

        sess = self._require_session()
        to = float(self.api.timeout if timeout is None else timeout)
        verify = self.api.verify_ssl

        # First attempt
        resp = sess.request(method.upper(), url, params=params, json=json, timeout=to, verify=verify, headers=h)
        if resp.status_code != 401:
            self._last_request_ts = time.time()
            return resp

        # If unauthorized, try a single token refresh
        self._invalidate_token()
        token = self._ensure_token()
        h["Authorization"] = f"Bearer {token}"
        resp2 = sess.request(method.upper(), url, params=params, json=json, timeout=to, verify=verify, headers=h)
        self._last_request_ts = time.time()
        return resp2

    def _require_session(self) -> Session:
        """ require session."""
        if not self._session:
            self._session = requests.Session()
        return self._session

    def _basic_auth_header(self) -> str:
        """ basic auth header."""
        raw = f"{self.auth.username}:{self.auth.password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _auth_url(self) -> str:
        """ auth url."""
        return _ensure_url(self.auth.server_host_name, self.auth.path, default_scheme=self.api.default_scheme)

    def _ensure_token(self) -> str:
        """ ensure token."""
        now = time.time()
        if self._token and self._token_expiry_ts and now < self._token_expiry_ts - 15:
            return self._token

        # fetch
        sess = self._require_session()
        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "X-API-KEY": str(self.api.key),  # Required by CoreCloud auth
        }
        url = self._auth_url()
        resp = sess.post(
            url,
            data={"grant_type": "password"},
            headers=headers,
            timeout=float(self.api.timeout),
            verify=self.api.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()

        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("id_token")
            or data.get("jwt")
            or data.get("accessToken")
        )
        if not token:
            raise RuntimeError(f"No token in auth response. Keys: {list(data.keys())}")

        # expiry handling
        expires_in = data.get("expires_in") or data.get("expiresIn") or 600  # seconds, default 10min
        try:
            self._token_expiry_ts = now + float(expires_in)
        except Exception:
            self._token_expiry_ts = now + 600.0
        self._token = token
        return token

    def _invalidate_token(self) -> None:
        """ invalidate token."""
        self._token = None
        self._token_expiry_ts = None

    def _throttle_delay(self) -> float:
        """
        Compute delay based on API_RATE_LIMIT_QPS; returns additional seconds to sleep
        *beyond* whatever the caller requests.
        """
        qps = float(self.api.rate_limit_qps or 0.0)
        if qps <= 0:
            return 0.0
        min_interval = 1.0 / qps
        now = time.time()
        elapsed = now - self._last_request_ts
        return max(0.0, min_interval - elapsed)

    def _maybe_throttle(self) -> None:
        """ maybe throttle."""
        delay = self._throttle_delay()
        if delay > 0:
            time.sleep(delay)

    def _teardown(self) -> None:
        """ teardown."""
        if self._session:
            try:
                self._session.close()
            finally:
                self._session = None
        self._invalidate_token()
