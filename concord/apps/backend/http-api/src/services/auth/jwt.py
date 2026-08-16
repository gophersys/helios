import hashlib
import secrets

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from config.env import env_config

ALGORITHM = "HS256"

# Web cookie JWT — long-lived because the cookie itself is the only
# session credential the browser ever sees. The frontend re-prompts at
# /login when this expires.
TOKEN_EXPIRE_HOURS = 24

# CLI session access token — short-lived because the CLI holds a
# refresh token and rotates against it. Mirrors the Claude Code /
# RFC 8628 device-code-flow pattern.
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# CLI session refresh token — long-lived but rotated on every use.
# When a refresh succeeds the presented token is revoked and a new
# one is issued; replaying a revoked token signals credential theft.
REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_token(
    user_id: str,
    email: str,
    name: str,
    permission_set_id: str | None,
    role: str = "DEVELOPER",
) -> str:
    """Create a long-lived JWT for the web cookie session.

    Used by the browser login flow (``/v2/auth/login`` and
    ``/v2/auth/dev-login``). The 24-hour expiry matches the cookie
    lifetime — no refresh-token mechanism applies here.
    """
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "permissionSetId": permission_set_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, env_config.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(
    user_id: str,
    email: str,
    name: str,
    permission_set_id: str | None,
    role: str = "DEVELOPER",
) -> str:
    """Create a short-lived JWT for a CLI session.

    Same payload shape as :func:`create_token` so the existing
    ``verify_token`` path validates both. The shorter expiry is
    safe because the CLI rotates against a refresh token (see
    :func:`make_refresh_token`) and re-fetches transparently when
    the access token nears expiry.
    """
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "permissionSetId": permission_set_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, env_config.JWT_SECRET_KEY, algorithm=ALGORITHM)


def make_refresh_token() -> Tuple[str, str]:
    """Generate a fresh refresh token and its SHA-256 hash.

    Returns ``(raw_token, hash)``. Persist the hash; hand the raw to
    the CLI exactly once. The raw token is a 256-bit URL-safe random
    string — the same shape ``secrets.token_urlsafe(32)`` produces
    elsewhere in the codebase for one-shot keys.
    """
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


def hash_refresh_token(raw: str) -> str:
    """Return the SHA-256 hex digest the DB stores for ``raw``.

    Pulled out as a helper so callers (the /refresh handler) can
    look up a presented token without reimplementing the hash.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
    """Verify and decode a JWT token, returning (payload, error)."""
    try:
        payload = jwt.decode(token, env_config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token expired"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {e}"
