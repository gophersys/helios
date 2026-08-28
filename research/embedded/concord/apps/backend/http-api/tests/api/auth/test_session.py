"""Tests for the CLI session (RFC 8628 device-code flow) endpoints."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.services.auth.jwt import hash_refresh_token
from tests.conftest import make_obj


def _future(minutes: int = 10) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _past(minutes: int = 1) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


# ─────────────────────────────────────────────────────────────────────────────
# POST /v2/auth/session/code — pre-auth, CLI requests user+device codes
# ─────────────────────────────────────────────────────────────────────────────


def test_request_session_code_returns_pair(client, mock_db):
    """The /code endpoint must return a user_code, device_code, and timing."""
    captured = {}

    def _capture(data):
        captured.update(data)
        return make_obj(id="sess-1", **data)

    mock_db.authsession.find_unique.return_value = None
    mock_db.authsession.create.side_effect = _capture

    response = client.post(
        "/v2/auth/session/code",
        json={},
    )
    assert response.status_code == 201
    body = json.loads(response.data)["data"]

    # User code is the human-typed one — 8 letters split by a hyphen.
    assert "-" in body["user_code"]
    assert len(body["user_code"]) == 9
    # Device code is the CLI's polling secret — long random.
    assert len(body["device_code"]) >= 32
    # RFC 8628 contract.
    assert body["expires_in"] == 600
    assert body["interval"] == 5
    # corectl's device-code URL points at ``/`` — the frontend's root
    # layout watches for ``?code=…`` on any route and auto-opens the
    # settings → sessions modal. Old tests asserted a dedicated
    # ``/settings/sessions`` path; that route was removed when the
    # approval UX moved into the shared settings modal.
    assert body["verification_uri"].endswith(f"/?code={body['user_code']}")

    # The persisted record must mirror what we returned.
    assert captured["userCode"] == body["user_code"]
    assert captured["deviceCode"] == body["device_code"]


def test_request_session_code_records_user_agent(client, mock_db):
    """The User-Agent header is stored so the approval UI can display it."""
    seen = {}
    mock_db.authsession.find_unique.return_value = None
    mock_db.authsession.create.side_effect = lambda data: (seen.update(data), make_obj(id="s1"))[1]

    client.post(
        "/v2/auth/session/code",
        json={},
        headers={"User-Agent": "corectl/1.0.0 (linux)"},
    )

    assert seen["userAgent"] == "corectl/1.0.0 (linux)"


# ─────────────────────────────────────────────────────────────────────────────
# POST /v2/auth/session/poll — pre-auth, CLI polls for approval
# ─────────────────────────────────────────────────────────────────────────────


def test_poll_session_pending(client, mock_db):
    """A PENDING session that hasn't expired returns ``pending``."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", status="PENDING", expiresAt=_future(), user=None,
    )

    response = client.post(
        "/v2/auth/session/poll",
        json={"device_code": "dev-xyz"},
    )
    assert response.status_code == 200
    assert json.loads(response.data)["data"] == {"status": "pending"}


def test_poll_session_lazy_expires_pending(client, mock_db):
    """A PENDING session past its expiry is flipped to EXPIRED on poll."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", status="PENDING", expiresAt=_past(), user=None,
    )

    response = client.post(
        "/v2/auth/session/poll",
        json={"device_code": "dev-xyz"},
    )
    assert response.status_code == 200
    assert json.loads(response.data)["data"] == {"status": "expired"}
    # We must have persisted the expiry — otherwise the next poll would
    # silently flip back to "pending".
    mock_db.authsession.update.assert_called_once()
    assert mock_db.authsession.update.call_args.kwargs["data"]["status"] == "EXPIRED"


def test_poll_session_returns_tokens_when_approved(client, mock_db):
    """Approved sessions yield an access+refresh pair and persist the refresh hash."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1",
        status="APPROVED",
        expiresAt=_future(),
        user=make_obj(
            id="u1", email="alice@example.com", name="Alice",
            permissionSetId="ps1", role="DEVELOPER", active=True,
        ),
    )
    mock_db.refreshtoken.create.return_value = make_obj(id="rt1")

    response = client.post(
        "/v2/auth/session/poll",
        json={"device_code": "dev-xyz"},
    )
    assert response.status_code == 200
    body = json.loads(response.data)["data"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 15 * 60
    assert len(body["access_token"]) > 20
    assert len(body["refresh_token"]) >= 32

    # The refresh hash actually persisted — not the raw token.
    persisted = mock_db.refreshtoken.create.call_args.kwargs["data"]
    assert persisted["tokenHash"] == hash_refresh_token(body["refresh_token"])
    assert persisted["userId"] == "u1"
    assert persisted["sessionId"] == "s1"


def test_poll_session_rejects_deactivated_user(client, mock_db):
    """An approved session for a deactivated user must not mint tokens."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1",
        status="APPROVED",
        expiresAt=_future(),
        user=make_obj(
            id="u1", email="x@y.com", name="X",
            permissionSetId=None, role="DEVELOPER", active=False,
        ),
    )

    response = client.post(
        "/v2/auth/session/poll",
        json={"device_code": "dev-xyz"},
    )
    assert response.status_code == 403


def test_poll_session_unknown_device_code(client, mock_db):
    mock_db.authsession.find_unique.return_value = None
    response = client.post(
        "/v2/auth/session/poll",
        json={"device_code": "nope"},
    )
    assert response.status_code == 404


def test_poll_session_missing_device_code(client, mock_db):
    response = client.post("/v2/auth/session/poll", json={})
    assert response.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# GET /v2/auth/session/verify — frontend resolves a user_code
# ─────────────────────────────────────────────────────────────────────────────


def test_verify_session_code_omits_device_code(client, mock_db):
    """The frontend payload must never contain the device_code secret."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1",
        userCode="ABCD-EFGH",
        deviceCode="MUST-NOT-LEAK",
        status="PENDING",
        userAgent="corectl/1.0.0",
        createdAt=datetime.now(timezone.utc),
        expiresAt=_future(),
    )

    response = client.get("/v2/auth/session/verify?user_code=ABCD-EFGH")
    assert response.status_code == 200
    body = json.loads(response.data)["data"]
    assert body["userCode"] == "ABCD-EFGH"
    assert "deviceCode" not in body
    assert "MUST-NOT-LEAK" not in response.data.decode()


def test_verify_session_code_unknown(client, mock_db):
    mock_db.authsession.find_unique.return_value = None
    response = client.get("/v2/auth/session/verify?user_code=ZZZZ-ZZZZ")
    assert response.status_code == 404


def test_verify_session_code_normalises_to_uppercase(client, mock_db):
    """Lowercase input must hit the same record as uppercase — humans type both."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", userCode="ABCD-EFGH", deviceCode="d", status="PENDING",
        userAgent=None, createdAt=datetime.now(timezone.utc), expiresAt=_future(),
    )
    client.get("/v2/auth/session/verify?user_code=abcd-efgh")
    where = mock_db.authsession.find_unique.call_args.kwargs["where"]
    assert where == {"userCode": "ABCD-EFGH"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /v2/auth/session/approve — authed, human approves
# ─────────────────────────────────────────────────────────────────────────────


def test_approve_session_flips_to_approved(authed_client, mock_db):
    """Approve binds the session to the caller and stamps approvedAt."""
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", userCode="ABCD-EFGH", status="PENDING", expiresAt=_future(),
        userAgent="corectl/1.0.0",
    )

    with patch("api.v2.auth.session.log_audit"):
        response = authed_client.post(
            "/v2/auth/session/approve",
            json={"user_code": "ABCD-EFGH"},
        )
    assert response.status_code == 200

    update_data = mock_db.authsession.update.call_args.kwargs["data"]
    assert update_data["status"] == "APPROVED"
    assert update_data["userId"] == "test-user-id"  # from authed_client fixture
    assert update_data["approvedAt"] is not None


def test_approve_session_rejects_already_approved(authed_client, mock_db):
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", userCode="ABCD-EFGH", status="APPROVED", expiresAt=_future(),
    )

    response = authed_client.post(
        "/v2/auth/session/approve",
        json={"user_code": "ABCD-EFGH"},
    )
    assert response.status_code == 400
    mock_db.authsession.update.assert_not_called()


def test_approve_session_rejects_expired(authed_client, mock_db):
    mock_db.authsession.find_unique.return_value = make_obj(
        id="s1", userCode="ABCD-EFGH", status="PENDING", expiresAt=_past(),
    )

    response = authed_client.post(
        "/v2/auth/session/approve",
        json={"user_code": "ABCD-EFGH"},
    )
    assert response.status_code == 400
    # Lazy-expire side effect: the session was bumped to EXPIRED.
    update_data = mock_db.authsession.update.call_args.kwargs["data"]
    assert update_data["status"] == "EXPIRED"


def test_approve_session_requires_auth(client, mock_db):
    """Without an Authorization header the approve endpoint must 401."""
    response = client.post(
        "/v2/auth/session/approve",
        json={"user_code": "ABCD-EFGH"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# POST /v2/auth/session/refresh — rotation chain
# ─────────────────────────────────────────────────────────────────────────────


def test_refresh_session_rotates_and_revokes_old(client, mock_db):
    """A valid refresh issues a new pair AND revokes the presented token."""
    raw = "raw-refresh-aaa"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-old",
        userId="u1",
        sessionId="s1",
        tokenHash=hash_refresh_token(raw),
        revokedAt=None,
        expiresAt=_future(60 * 24 * 30),
        user=make_obj(
            id="u1", email="a@b.com", name="Alice",
            permissionSetId="ps1", role="DEVELOPER", active=True,
        ),
        session=make_obj(id="s1"),
    )
    mock_db.refreshtoken.create.return_value = make_obj(id="rt-new")

    response = client.post(
        "/v2/auth/session/refresh",
        json={"refresh_token": raw},
    )
    assert response.status_code == 200
    body = json.loads(response.data)["data"]
    assert body["access_token"]
    assert body["refresh_token"] != raw  # rotated

    # The new token records its parent.
    new_data = mock_db.refreshtoken.create.call_args.kwargs["data"]
    assert new_data["parentId"] == "rt-old"
    # The old token is revoked atomically.
    revoke_call = mock_db.refreshtoken.update.call_args
    assert revoke_call.kwargs["where"] == {"id": "rt-old"}
    assert revoke_call.kwargs["data"]["revokedAt"] is not None


def test_refresh_session_replay_of_revoked_token_rejected(client, mock_db):
    """Presenting an already-revoked token must 401 — replay signal."""
    raw = "raw-revoked"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-revoked",
        userId="u1",
        sessionId="s1",
        tokenHash=hash_refresh_token(raw),
        revokedAt=_past(),
        expiresAt=_future(60 * 24 * 30),
        user=make_obj(id="u1", email="a@b.com", name="A", permissionSetId=None, role="DEVELOPER", active=True),
        session=make_obj(id="s1"),
    )

    response = client.post(
        "/v2/auth/session/refresh",
        json={"refresh_token": raw},
    )
    assert response.status_code == 401
    # Critically: no new token issued.
    mock_db.refreshtoken.create.assert_not_called()


def test_refresh_session_unknown_token(client, mock_db):
    mock_db.refreshtoken.find_unique.return_value = None
    response = client.post(
        "/v2/auth/session/refresh",
        json={"refresh_token": "nope"},
    )
    assert response.status_code == 401


def test_refresh_session_expired(client, mock_db):
    raw = "raw-expired"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-exp", userId="u1", sessionId="s1",
        tokenHash=hash_refresh_token(raw), revokedAt=None, expiresAt=_past(),
        user=make_obj(id="u1", email="a@b.com", name="A", permissionSetId=None, role="DEVELOPER", active=True),
        session=make_obj(id="s1"),
    )
    response = client.post(
        "/v2/auth/session/refresh",
        json={"refresh_token": raw},
    )
    assert response.status_code == 401


def test_refresh_session_deactivated_user(client, mock_db):
    raw = "raw-deact"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-d", userId="u1", sessionId="s1",
        tokenHash=hash_refresh_token(raw), revokedAt=None,
        expiresAt=_future(60 * 24 * 30),
        user=make_obj(id="u1", email="a@b.com", name="A", permissionSetId=None, role="DEVELOPER", active=False),
        session=make_obj(id="s1"),
    )
    response = client.post(
        "/v2/auth/session/refresh",
        json={"refresh_token": raw},
    )
    assert response.status_code == 403
    mock_db.refreshtoken.create.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# POST /v2/auth/session/revoke
# ─────────────────────────────────────────────────────────────────────────────


def test_revoke_session_marks_revoked(client, mock_db):
    raw = "raw-to-revoke"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-1", userId="u1", sessionId="s1",
        tokenHash=hash_refresh_token(raw), revokedAt=None,
        expiresAt=_future(60 * 24 * 30),
    )

    with patch("api.v2.auth.session.log_audit"):
        response = client.post(
            "/v2/auth/session/revoke",
            json={"refresh_token": raw},
        )
    assert response.status_code == 200
    update_call = mock_db.refreshtoken.update.call_args
    assert update_call.kwargs["where"] == {"id": "rt-1"}
    assert update_call.kwargs["data"]["revokedAt"] is not None


def test_revoke_session_idempotent_for_unknown_token(client, mock_db):
    """Unknown tokens still 200 — never leak whether the token existed."""
    mock_db.refreshtoken.find_unique.return_value = None
    response = client.post(
        "/v2/auth/session/revoke",
        json={"refresh_token": "anything"},
    )
    assert response.status_code == 200
    mock_db.refreshtoken.update.assert_not_called()


def test_revoke_session_idempotent_for_already_revoked(client, mock_db):
    """Already-revoked tokens return 200 without re-updating."""
    raw = "raw-already-revoked"
    mock_db.refreshtoken.find_unique.return_value = make_obj(
        id="rt-old", userId="u1", sessionId="s1",
        tokenHash=hash_refresh_token(raw), revokedAt=_past(),
        expiresAt=_future(60 * 24 * 30),
    )
    response = client.post(
        "/v2/auth/session/revoke",
        json={"refresh_token": raw},
    )
    assert response.status_code == 200
    mock_db.refreshtoken.update.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# AUTH_ENABLED matrix — pre-auth endpoints must work in both modes
# ─────────────────────────────────────────────────────────────────────────────


def test_request_code_works_when_auth_disabled(client, mock_db):
    """Pre-auth endpoints have no decorator — disabling auth must not change them."""
    mock_db.authsession.find_unique.return_value = None
    mock_db.authsession.create.return_value = make_obj(id="s1")

    with patch("config.env.env_config.AUTH_ENABLED", False):
        response = client.post("/v2/auth/session/code", json={})
    assert response.status_code == 201
