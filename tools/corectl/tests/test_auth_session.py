"""End-to-end tests for the device-code login + auto-refresh path.

We exercise three things that would otherwise only be caught in
production:

1. ``corectl auth login`` walks the RFC 8628 flow correctly and
   honours server-supplied ``slow_down`` / ``pending`` responses.
2. ``ConcordAPI`` proactively refreshes a near-expiry token before the
   real request goes out.
3. On a 401, ``ConcordAPI`` performs exactly one transparent refresh +
   retry; a second 401 is surfaced (not infinite-looped).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from corectl.api import AuthError, ConcordAPI
from corectl.commands import auth as auth_mod


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _resp(status: int, body: dict) -> MagicMock:
    """Mimic the subset of ``requests.Response`` our code touches."""
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.json.return_value = body
    r.text = str(body)
    return r


def _envelope(payload: dict) -> dict:
    """Wrap ``payload`` in the backend's standard ``{data, errors}`` shape."""
    return {"data": payload, "errors": []}


# ────────────────────────────────────────────────────────────────────────
# corectl auth login — the device-code dance
# ────────────────────────────────────────────────────────────────────────


def test_login_happy_path_walks_full_flow(tmp_path, monkeypatch):
    """code → pending → approved → tokens persisted to disk."""
    monkeypatch.setattr("corectl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("corectl.config.CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr("corectl.commands.auth.time.sleep", lambda *_a, **_kw: None)

    code_resp = _resp(201, _envelope({
        "user_code": "ABCD-EFGH",
        "device_code": "dev-xyz",
        "verification_uri": "https://x/settings/sessions?code=ABCD-EFGH",
        "expires_in": 600,
        "interval": 1,
    }))
    pending_resp = _resp(200, _envelope({"status": "pending"}))
    approved_resp = _resp(200, _envelope({
        "access_token": _fake_jwt(email="alice@example.com"),
        "refresh_token": "rt-xxx",
        "token_type": "Bearer",
        "expires_in": 900,
    }))

    posts = [code_resp, pending_resp, pending_resp, approved_resp]
    with patch("corectl.commands.auth.requests.post", side_effect=posts):
        runner = CliRunner()
        result = runner.invoke(
            auth_mod.auth,
            ["login", "--url", "https://x", "--no-browser"],
            obj={"config": {}},
        )

    assert result.exit_code == 0, result.output
    assert "ABCD-EFGH" in result.output
    assert "alice@example.com" in result.output

    # And the session is now on disk.
    from corectl.config import load_config, get_session
    saved = load_config()
    sess = get_session(saved)
    assert sess is not None
    assert sess["refresh_token"] == "rt-xxx"
    assert sess["user_email"] == "alice@example.com"


def test_login_aborts_on_denied(tmp_path, monkeypatch):
    """A ``denied`` poll response exits non-zero and does not save tokens."""
    monkeypatch.setattr("corectl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("corectl.config.CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr("corectl.commands.auth.time.sleep", lambda *_a, **_kw: None)

    code = _resp(201, _envelope({
        "user_code": "ABCD-EFGH", "device_code": "d", "verification_uri": "u",
        "expires_in": 600, "interval": 1,
    }))
    denied = _resp(200, _envelope({"status": "denied"}))

    with patch("corectl.commands.auth.requests.post", side_effect=[code, denied]):
        runner = CliRunner()
        result = runner.invoke(
            auth_mod.auth, ["login", "--url", "https://x", "--no-browser"], obj={"config": {}},
        )

    assert result.exit_code != 0
    assert "denied" in result.output.lower()
    # No session got written.
    assert not (tmp_path / "config.yaml").exists() or "refresh_token" not in (tmp_path / "config.yaml").read_text()


def test_login_honours_slow_down(tmp_path, monkeypatch):
    """``slow_down`` must increase the polling interval."""
    monkeypatch.setattr("corectl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("corectl.config.CONFIG_FILE", tmp_path / "config.yaml")

    sleeps: list[float] = []
    monkeypatch.setattr("corectl.commands.auth.time.sleep", lambda s: sleeps.append(s))

    code = _resp(201, _envelope({
        "user_code": "AAAA-BBBB", "device_code": "d", "verification_uri": "u",
        "expires_in": 600, "interval": 2,
    }))
    slow = _resp(200, _envelope({"status": "slow_down"}))
    approved = _resp(200, _envelope({
        "access_token": _fake_jwt(), "refresh_token": "rt",
        "token_type": "Bearer", "expires_in": 900,
    }))

    with patch("corectl.commands.auth.requests.post", side_effect=[code, slow, approved]):
        runner = CliRunner()
        result = runner.invoke(
            auth_mod.auth, ["login", "--url", "https://x", "--no-browser"], obj={"config": {}},
        )

    assert result.exit_code == 0, result.output
    # First sleep at the server's interval (2s); after slow_down we should
    # have backed off — the second poll's wait is at least 2 + 5 = 7s.
    assert sleeps[0] == 2
    assert sleeps[1] >= 7


# ────────────────────────────────────────────────────────────────────────
# ConcordAPI auto-refresh
# ────────────────────────────────────────────────────────────────────────


def test_request_proactively_refreshes_when_near_expiry():
    """A token expiring in <60s triggers a refresh before the real call."""
    # Build a client whose token is "5 seconds from expiring" — the
    # 60-second leeway in the client must trip the refresh.
    near_expiry = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()

    save_args: list[dict] = []
    api = ConcordAPI(
        "https://x",
        access_token="old-access",
        refresh_token="old-refresh",
        expires_at=near_expiry,
        on_refresh=save_args.append,
    )

    # The session.request call needs to satisfy two requests: the refresh
    # POST, then the real GET. Track call order to verify the refresh
    # really did go first.
    calls: list[tuple] = []

    def _fake_request(method, url, **kw):
        calls.append((method, url, kw.get("headers", {}).get("Authorization")))
        if url.endswith("/v2/auth/session/refresh"):
            return _resp(200, _envelope({
                "access_token": "fresh-access",
                "refresh_token": "fresh-refresh",
                "expires_in": 900,
            }))
        return _resp(200, _envelope({"ok": True}))

    api._session.request = _fake_request  # noqa: SLF001

    api.get("/v2/things")

    # First call was the refresh (no Auth header — it's pre-auth).
    assert calls[0][1].endswith("/v2/auth/session/refresh")
    # Second call was the real GET, using the FRESH access token.
    assert calls[1][1].endswith("/v2/things")
    assert calls[1][2] == "Bearer fresh-access"

    # The on_refresh hook was called with the rotated pair.
    assert save_args
    assert save_args[0]["access_token"] == "fresh-access"
    assert save_args[0]["refresh_token"] == "fresh-refresh"


def test_401_triggers_one_refresh_and_one_retry():
    """The first 401 is recoverable; the second is fatal."""
    # Token comfortably in the future so we don't proactively refresh —
    # this isolates the 401-recovery path from the proactive path.
    far_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    api = ConcordAPI(
        "https://x",
        access_token="old", refresh_token="rt", expires_at=far_future,
        on_refresh=lambda _kw: None,
    )

    # Real GET 401, refresh OK, retry GET 200.
    responses = iter([
        _resp(401, _envelope({})),
        _resp(200, _envelope({"access_token": "new", "refresh_token": "new-rt", "expires_in": 900})),
        _resp(200, _envelope({"ok": True})),
    ])

    def _fake_request(method, url, **kw):
        return next(responses)

    api._session.request = _fake_request  # noqa: SLF001

    resp = api.get("/v2/things")
    assert resp.status_code == 200
    # And the chain is exhausted — no extra calls were made.
    with pytest.raises(StopIteration):
        next(responses)


def test_persistent_401_is_surfaced_not_looped():
    """Two consecutive 401s mean the refresh didn't fix it — propagate."""
    far_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    api = ConcordAPI(
        "https://x",
        access_token="old", refresh_token="rt", expires_at=far_future,
    )

    responses = iter([
        _resp(401, _envelope({})),
        _resp(200, _envelope({"access_token": "new", "refresh_token": "new-rt", "expires_in": 900})),
        _resp(401, _envelope({})),  # still unauthorized after refresh
    ])

    def _fake_request(method, url, **kw):
        return next(responses)

    api._session.request = _fake_request  # noqa: SLF001

    resp = api.get("/v2/things")
    assert resp.status_code == 401
    # Three calls and three only — we did NOT loop forever.
    with pytest.raises(StopIteration):
        next(responses)


def test_revoked_refresh_raises_auth_error():
    """If the backend rejects the refresh token, the error must propagate."""
    near_expiry = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    api = ConcordAPI(
        "https://x",
        access_token="old", refresh_token="rt", expires_at=near_expiry,
    )
    api._session.request = lambda *a, **kw: _resp(401, _envelope({}))  # noqa: SLF001

    with pytest.raises(AuthError):
        api.get("/v2/things")


def test_service_account_key_skips_refresh_logic():
    """Service-account auth uses ApiKey header and doesn't try to refresh on 401."""
    api = ConcordAPI("https://x", api_key="ck_live_xxx")
    captured = {}

    def _fake_request(method, url, **kw):
        captured["headers"] = kw.get("headers", {})
        return _resp(401, _envelope({}))

    api._session.request = _fake_request  # noqa: SLF001

    resp = api.get("/v2/things")
    assert resp.status_code == 401
    assert captured["headers"]["Authorization"] == "ApiKey ck_live_xxx"


def test_from_config_without_session_raises():
    """No tokens, no service-account key → AuthError, not a silent fallback."""
    with pytest.raises(AuthError):
        ConcordAPI.from_config({}, save_callback=lambda _: None)


def test_from_config_prefers_service_account_over_session():
    """A service-account key wins over a saved session — CI hygiene."""
    config = {
        "access_token": "user-jwt", "refresh_token": "user-rt",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    api = ConcordAPI.from_config(
        config, save_callback=lambda _: None, service_account_key="ck_ci",
    )
    captured = {}

    def _fake(method, url, **kw):
        captured["h"] = kw.get("headers", {})
        return _resp(200, _envelope({}))

    api._session.request = _fake  # noqa: SLF001

    api.get("/v2/x")
    assert captured["h"]["Authorization"] == "ApiKey ck_ci"


# ────────────────────────────────────────────────────────────────────────
# Helpers used by the login tests
# ────────────────────────────────────────────────────────────────────────


def _fake_jwt(email: str = "alice@example.com") -> str:
    """Forge an unsigned JWT with the given ``email`` claim.

    Good enough for the email-extraction code in ``auth.login`` — it
    never validates the signature.
    """
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload_bytes = json.dumps({"sub": "u1", "email": email}).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"
