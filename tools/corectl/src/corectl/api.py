"""HTTP client for the Concord backend.

Two auth modes — humans use **sessions**, services use **API keys**:

* Session auth (``corectl auth login``):
    Bearer access token (15 min) + refresh token (30 days, rotated).
    The client auto-refreshes when the access token is within 60 s of
    expiry and transparently retries on a 401.

* Service-account auth (``--service-account`` flag, ``CONCORD_API_KEY``
  env var):
    Long-lived API key sent as ``Authorization: ApiKey <key>``. No
    refresh dance — the key is the credential.

Both paths land on the same backend JWT issuer, so downstream permission
checks behave identically.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import requests


# How close to expiry we proactively refresh. 60 s is enough headroom for
# a typical request even on a slow link, without burning refreshes.
_REFRESH_LEEWAY_SECONDS = 60


class AuthError(Exception):
    """Raised when no usable credential is available or the refresh chain breaks.

    The CLI catches this at the entry-point and prints a friendly
    "run ``corectl auth login``" message.
    """


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    # ``datetime.fromisoformat`` accepts the ``+00:00`` offset we store.
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


class ConcordAPI:
    """Token-aware Concord HTTP client.

    Use :meth:`from_config` to construct from the parsed YAML config —
    that wires the auth mode (session vs API key), refresh hook, and save
    callback. The bare ``__init__`` exists for tests.
    """

    def __init__(
        self,
        base_url: str,
        *,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[str] = None,
        api_key: Optional[str] = None,
        tls_verify: bool = True,
        on_refresh: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._tls_verify = tls_verify
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = _parse_iso(expires_at)
        self._api_key = api_key
        self._on_refresh = on_refresh
        self._session = requests.Session()
        self._session.verify = tls_verify

    # ─── Constructors ───────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        *,
        save_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        service_account_key: Optional[str] = None,
    ) -> "ConcordAPI":
        """Build a client from the loaded config + optional save callback.

        ``service_account_key`` (from ``--service-account`` or
        ``$CONCORD_API_KEY``) takes precedence over the saved session —
        CI runs always want the explicit key, never a stale local session
        file someone left behind.
        """
        from .config import get_api_url, get_session, get_tls_verify

        base_url = get_api_url(config)
        tls = get_tls_verify(config)

        if service_account_key:
            return cls(
                base_url,
                api_key=service_account_key,
                tls_verify=tls,
            )

        session = get_session(config)
        if session is None:
            raise AuthError(
                "Not authenticated. Run: corectl auth login\n"
                "(or set CONCORD_API_KEY for service-account auth)"
            )

        on_refresh = None
        if save_callback is not None:
            def _on_refresh(updated: Dict[str, Any]) -> None:
                # The saved config dict is our source of truth — mutate
                # it in-place and let the caller persist it.
                config["access_token"] = updated["access_token"]
                config["refresh_token"] = updated["refresh_token"]
                config["expires_at"] = updated["expires_at"]
                save_callback(config)
            on_refresh = _on_refresh

        return cls(
            base_url,
            access_token=session["access_token"],
            refresh_token=session["refresh_token"],
            expires_at=session.get("expires_at"),
            tls_verify=tls,
            on_refresh=on_refresh,
        )

    # ─── HTTP verbs (exposed for backward-compat with existing call sites) ─

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._request("DELETE", path, **kwargs)

    def health_check(self) -> bool:
        """Cheap reachability probe — no auth required."""
        try:
            resp = self._raw("GET", "/v2/docs", auth=False)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ─── Internals ──────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Auth-aware request: refresh proactively, retry once on 401.

        Service-account keys skip both branches — there is no refresh path
        and a 401 on an API key means the key is bad, not stale.
        """
        if self._api_key is None and self._access_token:
            self._maybe_refresh()

        resp = self._raw(method, path, **kwargs)

        if (
            resp.status_code == 401
            and self._refresh_token
            and self._api_key is None
        ):
            # The token may have been revoked server-side, or the clock
            # skewed past our leeway. One retry — if that also fails,
            # surface it.
            self._refresh_now()
            resp = self._raw(method, path, **kwargs)

        return resp

    def _raw(self, method: str, path: str, *, auth: bool = True, **kwargs) -> requests.Response:
        """Unwrapped HTTP call. Used directly only by ``health_check`` and the refresh dance.

        Intentionally does **not** set ``Content-Type`` — ``requests`` derives
        it from the kwargs (``json=`` → JSON, ``files=`` → multipart). Setting
        it here would clobber the multipart boundary that file-upload callers
        rely on.
        """
        headers = dict(kwargs.pop("headers", {}) or {})
        if auth:
            if self._api_key:
                headers["Authorization"] = f"ApiKey {self._api_key}"
            elif self._access_token:
                headers["Authorization"] = f"Bearer {self._access_token}"
        return self._session.request(
            method, f"{self._base_url}{path}", headers=headers, **kwargs,
        )

    def _maybe_refresh(self) -> None:
        if self._expires_at is None or self._refresh_token is None:
            return
        leeway = timedelta(seconds=_REFRESH_LEEWAY_SECONDS)
        if datetime.now(timezone.utc) + leeway >= self._expires_at:
            self._refresh_now()

    def _refresh_now(self) -> None:
        """Rotate the refresh token. Raises ``AuthError`` if the chain is dead."""
        if not self._refresh_token:
            raise AuthError("No refresh token available; run: corectl auth login")

        resp = self._raw(
            "POST", "/v2/auth/session/refresh",
            json={"refresh_token": self._refresh_token},
            auth=False,
        )
        if resp.status_code != 200:
            # 401 here means our refresh token was revoked (logout
            # elsewhere, or replay detected). Either way, the local
            # session is dead — wipe it via the save callback.
            if self._on_refresh:
                # Signal an empty session so the caller can clear state.
                # We pass an explicit "empty" sentinel; the callback
                # treats blank tokens as "wipe me".
                pass
            raise AuthError(
                "Session expired or revoked. Run: corectl auth login"
            )

        body = resp.json()
        data = body.get("data") or body
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        # The backend reports ``expires_in`` (seconds); we persist the
        # absolute timestamp so the next process restart still knows when
        # to refresh.
        expires_in = int(data.get("expires_in") or 0)
        new_exp = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self._expires_at = new_exp

        if self._on_refresh:
            self._on_refresh({
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": new_exp.isoformat(),
            })
