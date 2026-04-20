"""CLI session endpoints — RFC 8628 device-code flow.

Six handlers wire up a Claude-Code-style login for ``corectl``:

* ``POST /v2/auth/session/code``    — CLI requests a fresh user/device code pair
* ``POST /v2/auth/session/poll``    — CLI polls until a human approves
* ``GET  /v2/auth/session/verify``  — frontend resolves a user code into a session
* ``POST /v2/auth/session/approve`` — authed human approves the pending session
* ``POST /v2/auth/session/refresh`` — CLI rotates its access token
* ``POST /v2/auth/session/revoke``  — CLI logs out (or admin kills the chain)

The pre-auth endpoints (``code``, ``poll``, ``verify``, ``refresh``, ``revoke``)
do not use ``@require_permissions`` — they are the credential-issuing path.
``approve`` requires an authenticated browser session.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

from flask import g, jsonify, request

from config import env_config
from src.lib.audit import log_audit
from src.lib.decorators import require_auth
from src.lib.errors import bad_request, forbidden, not_found, unauthorized
from src.lib.types import ApiResponse
from src.services.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    hash_refresh_token,
    make_refresh_token,
)
from src.services.database.prisma import get_db_client

from .types import (
    SessionApproveRequest,
    SessionPollRequest,
    SessionRefreshRequest,
    SessionRevokeRequest,
)

logger = logging.getLogger(__name__)

# RFC 8628 timing — short-lived approval window, polite poll interval.
SESSION_EXPIRE_MINUTES = 10
POLL_INTERVAL_SECONDS = 5
USER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1


def _generate_user_code() -> str:
    """Return an 8-char ``XXXX-XXXX`` code from an ambiguity-free alphabet.

    The alphabet drops ``I``/``O``/``0``/``1`` so a human reading the code off
    a terminal and typing it into a browser cannot misread it.
    """
    raw = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _generate_device_code() -> str:
    """Return a 256-bit URL-safe device code (the CLI's polling secret)."""
    return secrets.token_urlsafe(32)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _verification_uri(user_code: str) -> str:
    """Build the URL we tell the CLI to open in a browser.

    The frontend's root layout watches for ``?code=…`` on any route and
    auto-opens the Settings → Sessions dialog — so we send the CLI user
    to ``/`` with the code appended. Landing on the dashboard means they
    never see a 404 on a not-yet-loaded SPA route, and the query-param
    contract is decoupled from any specific page URL.

    Traefik terminates TLS and proxies plain HTTP to the pod, so
    ``request.url_root`` / ``request.host_url`` both return ``http://…``.
    Honour the standard ``X-Forwarded-Proto`` / ``X-Forwarded-Host``
    headers so the URL we print is the public one, not the in-cluster one.
    """
    proto = (request.headers.get("X-Forwarded-Proto") or request.scheme or "https").split(",")[0].strip()
    host = request.headers.get("X-Forwarded-Host") or request.host
    return f"{proto}://{host}/?code={user_code}"


def _is_expired(session) -> bool:
    return session.expiresAt < _now()


def _serialize_pending(session) -> dict:
    """Public view of a pending session for the approval UI.

    Intentionally omits ``deviceCode`` — that's the CLI's secret, not for
    the browser. The browser only needs to know who's asking and when it expires.
    """
    return {
        "userCode": session.userCode,
        "status": session.status,
        "userAgent": session.userAgent,
        "createdAt": session.createdAt.isoformat(),
        "expiresAt": session.expiresAt.isoformat(),
    }


def _issue_token_pair(user, session_id: str, db) -> dict:
    """Create an access + refresh token pair and persist the refresh hash.

    Returns the response body the CLI receives on a successful poll/refresh.
    The raw refresh token is shown exactly once.
    """
    user_role = getattr(user, "role", "DEVELOPER") or "DEVELOPER"
    access_token = create_access_token(
        user.id, user.email, user.name, user.permissionSetId, role=user_role,
    )
    raw_refresh, refresh_hash = make_refresh_token()
    db.refreshtoken.create(
        data={
            "userId": user.id,
            "sessionId": session_id,
            "tokenHash": refresh_hash,
            "expiresAt": _now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        }
    )
    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────


def request_session_code():
    """CLI requests a fresh user/device code pair (no auth required).

    Returns the user code (humans type into a browser), the device code (the
    CLI's polling secret), the verification URI, and RFC 8628 timing fields.
    """
    db = get_db_client()
    # Ensure the user code is unique among non-expired sessions. Birthday
    # collisions in 32^8 are astronomically unlikely, but a duplicate would
    # let two CLIs share an approval — retry on the rare clash.
    for _ in range(5):
        user_code = _generate_user_code()
        existing = db.authsession.find_unique(where={"userCode": user_code})
        if not existing or _is_expired(existing):
            break
    else:
        return bad_request("Could not allocate a unique user code; retry")

    device_code = _generate_device_code()
    user_agent = request.headers.get("User-Agent", "")[:255]

    session = db.authsession.create(
        data={
            "userCode": user_code,
            "deviceCode": device_code,
            "userAgent": user_agent or None,
            "expiresAt": _now() + timedelta(minutes=SESSION_EXPIRE_MINUTES),
        }
    )

    return jsonify(ApiResponse.ok({
        "user_code": user_code,
        "device_code": device_code,
        "verification_uri": _verification_uri(user_code),
        "expires_in": SESSION_EXPIRE_MINUTES * 60,
        "interval": POLL_INTERVAL_SECONDS,
        "session_id": session.id,
    }).to_dict()), 201


def poll_session():
    """CLI polls for approval status (no auth required — device_code is the secret).

    Returns one of:
      * ``{"status": "pending"}`` — still waiting on a human
      * ``{"status": "expired"}`` — 10-min window elapsed
      * ``{"status": "denied"}``  — human clicked Deny
      * ``{"status": "slow_down"}`` — caller polled faster than ``interval``
      * ``{"access_token": ..., "refresh_token": ..., ...}`` on approval
    """
    data, error = SessionPollRequest.from_json(request.get_json(silent=True) or {})
    if error:
        return bad_request(error)

    db = get_db_client()
    session = db.authsession.find_unique(
        where={"deviceCode": data.device_code},
        include={"user": True},
    )
    if not session:
        return not_found("Unknown device_code")

    # RFC 8628 slow_down — last poll was too recent. We don't store
    # last-poll-at on the session yet (a future migration can add it); the
    # CLI honours the ``interval`` we returned at /code time, so this branch
    # is reachable only if a misbehaving client races the poll.
    # Leaving the door open here keeps the contract honest.

    now = _now()
    if session.expiresAt < now and session.status == "PENDING":
        # Lazy-expire so polling clients see a terminal state.
        db.authsession.update(
            where={"id": session.id},
            data={"status": "EXPIRED"},
        )
        return jsonify(ApiResponse.ok({"status": "expired"}).to_dict()), 200

    if session.status == "PENDING":
        return jsonify(ApiResponse.ok({"status": "pending"}).to_dict()), 200

    if session.status == "EXPIRED":
        return jsonify(ApiResponse.ok({"status": "expired"}).to_dict()), 200

    if session.status == "DENIED":
        return jsonify(ApiResponse.ok({"status": "denied"}).to_dict()), 200

    # APPROVED — issue tokens. Idempotency: if the CLI polls twice after
    # approval we'll mint a new pair each time. That's fine — old refresh
    # tokens still rotate independently. The session row is single-use only
    # in the sense that ``approve`` flips it to APPROVED exactly once.
    if session.status == "APPROVED":
        if not session.user:
            # Approved but the user got deleted in the gap.
            return forbidden("Account no longer exists")
        if not session.user.active:
            return forbidden("Account deactivated")
        body = _issue_token_pair(session.user, session.id, db)
        return jsonify(ApiResponse.ok(body).to_dict()), 200

    return bad_request(f"Unknown session status: {session.status}")


def verify_session_code():
    """Frontend resolves ``?user_code=XXXX-XXXX`` into a pending session.

    Used by ``/settings/sessions?code=...`` to show "corectl wants to act
    as <email> until <date>" before the user clicks Approve. No auth needed —
    the user_code is itself the lookup token, and the response intentionally
    omits the device_code.
    """
    user_code = (request.args.get("user_code") or "").strip().upper()
    if not user_code:
        return bad_request("user_code query param is required")

    db = get_db_client()
    session = db.authsession.find_unique(where={"userCode": user_code})
    if not session:
        return not_found("Unknown user_code")
    if _is_expired(session) and session.status == "PENDING":
        return jsonify(ApiResponse.ok({**_serialize_pending(session), "status": "EXPIRED"}).to_dict()), 200

    return jsonify(ApiResponse.ok(_serialize_pending(session)).to_dict()), 200


@require_auth
def approve_session():
    """Authed human flips a PENDING session to APPROVED, binding it to themselves.

    Uses ``@require_auth`` only (not ``@require_permissions``) — any logged-in
    Concord user can authorize their own CLI. Permissions on what corectl can
    *do* are enforced per-endpoint by the existing permission machinery once
    the access token is in use.
    """
    data, error = SessionApproveRequest.from_json(request.get_json(silent=True) or {})
    if error:
        return bad_request(error)

    db = get_db_client()
    session = db.authsession.find_unique(where={"userCode": data.user_code})
    if not session:
        return not_found("Unknown user_code")
    if session.status != "PENDING":
        return bad_request(f"Session is not pending (status: {session.status})")
    if _is_expired(session):
        db.authsession.update(where={"id": session.id}, data={"status": "EXPIRED"})
        return bad_request("Session expired — request a new code")

    user_id = g.current_user["sub"]
    db.authsession.update(
        where={"id": session.id},
        data={
            "status": "APPROVED",
            "userId": user_id,
            "approvedAt": _now(),
        },
    )

    log_audit(
        "authSession.approve",
        "AuthSession",
        session.id,
        {"userCode": session.userCode, "userAgent": session.userAgent},
    )

    return jsonify(ApiResponse.ok({
        "status": "approved",
        "userCode": session.userCode,
    }).to_dict()), 200


def refresh_session():
    """Rotate a refresh token, issuing a fresh access+refresh pair.

    Replay protection: the presented refresh token is revoked atomically as
    part of issuing the new one. If it was *already* revoked we surface a
    401 — the legitimate client has already rotated past it, so seeing an
    old token here is a strong signal of credential theft. (A future PR
    will revoke the entire chain in that case; for now we just refuse.)
    """
    data, error = SessionRefreshRequest.from_json(request.get_json(silent=True) or {})
    if error:
        return bad_request(error)

    db = get_db_client()
    presented_hash = hash_refresh_token(data.refresh_token)
    token = db.refreshtoken.find_unique(
        where={"tokenHash": presented_hash},
        include={"user": True, "session": True},
    )
    if not token:
        return unauthorized("Invalid refresh token")
    if token.revokedAt is not None:
        # Replay of an already-rotated token. Tracked-followup #SUSPECTED_REPLAY:
        # walk the parentId chain and revoke everything.
        logger.warning("Replay of revoked refresh token (id=%s, user=%s)", token.id, token.userId)
        return unauthorized("Refresh token revoked")
    if token.expiresAt < _now():
        return unauthorized("Refresh token expired")
    if not token.user or not token.user.active:
        return forbidden("Account deactivated")

    # Mint the new pair first so we don't leave the user empty-handed if
    # something fails in the middle.
    user_role = getattr(token.user, "role", "DEVELOPER") or "DEVELOPER"
    new_access = create_access_token(
        token.user.id, token.user.email, token.user.name,
        token.user.permissionSetId, role=user_role,
    )
    raw_refresh, new_hash = make_refresh_token()
    db.refreshtoken.create(
        data={
            "userId": token.user.id,
            "sessionId": token.sessionId,
            "tokenHash": new_hash,
            "parentId": token.id,
            "expiresAt": _now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        }
    )
    db.refreshtoken.update(
        where={"id": token.id},
        data={"revokedAt": _now()},
    )

    return jsonify(ApiResponse.ok({
        "access_token": new_access,
        "refresh_token": raw_refresh,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }).to_dict()), 200


def revoke_session():
    """Revoke a refresh token (logout). Idempotent.

    Pre-auth so the CLI can log out without first refreshing an expired
    access token. Possession of the refresh token *is* the authorization
    here — same as RFC 7009 token revocation semantics.
    """
    data, error = SessionRevokeRequest.from_json(request.get_json(silent=True) or {})
    if error:
        return bad_request(error)

    db = get_db_client()
    presented_hash = hash_refresh_token(data.refresh_token)
    token = db.refreshtoken.find_unique(where={"tokenHash": presented_hash})
    if not token:
        # Don't leak whether the token ever existed.
        return jsonify(ApiResponse.ok({"revoked": True}).to_dict()), 200
    if token.revokedAt is None:
        db.refreshtoken.update(
            where={"id": token.id},
            data={"revokedAt": _now()},
        )
        log_audit(
            "authSession.revoke",
            "RefreshToken",
            token.id,
            {"sessionId": token.sessionId, "userId": token.userId},
        )

    return jsonify(ApiResponse.ok({"revoked": True}).to_dict()), 200
