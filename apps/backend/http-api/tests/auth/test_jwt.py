"""
Unit tests for JWT functions in src/services/auth/jwt.py.

Tests token creation, verification, and expiration handling.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest


def test_create_token_returns_string():
    from src.services.auth.jwt import create_token

    token = create_token(
        user_id="user-123",
        email="test@example.com",
        name="Test User",
        permission_set_id="perm-set-123",
    )

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_token_can_be_decoded():
    from src.services.auth.jwt import create_token
    from config import env_config

    token = create_token(
        user_id="user-456",
        email="alice@example.com",
        name="Alice",
        permission_set_id="perm-789",
    )

    # Decode without verification to check structure
    decoded = jwt.decode(token, options={"verify_signature": False})

    assert decoded["sub"] == "user-456"
    assert decoded["email"] == "alice@example.com"
    assert decoded["name"] == "Alice"
    assert decoded["permissionSetId"] == "perm-789"
    assert "iat" in decoded
    assert "exp" in decoded


def test_verify_token_valid():
    from src.services.auth.jwt import create_token, verify_token

    token = create_token(
        user_id="user-123",
        email="test@example.com",
        name="Test User",
        permission_set_id="perm-set-123",
    )

    payload, error = verify_token(token)

    assert error is None
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"
    assert payload["name"] == "Test User"
    assert payload["permissionSetId"] == "perm-set-123"


def test_verify_token_expired():
    from src.services.auth.jwt import verify_token, ALGORITHM
    from config import env_config

    # Create an expired token (expired 1 hour ago)
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User",
        "permissionSetId": "perm-set-123",
        "iat": datetime.now(timezone.utc) - timedelta(hours=25),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, env_config.JWT_SECRET_KEY, algorithm=ALGORITHM)

    result_payload, error = verify_token(expired_token)

    assert result_payload is None
    assert error == "Token expired"


def test_verify_token_invalid_signature():
    from src.services.auth.jwt import verify_token, ALGORITHM

    # Create a token with a different secret
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User",
        "permissionSetId": "perm-set-123",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    invalid_token = jwt.encode(payload, "wrong-secret-key-padded-to-32chars", algorithm=ALGORITHM)

    result_payload, error = verify_token(invalid_token)

    assert result_payload is None
    assert error is not None
    assert error.startswith("Invalid token:")


def test_verify_token_malformed():
    from src.services.auth.jwt import verify_token

    malformed_token = "not.a.valid.jwt.token"

    result_payload, error = verify_token(malformed_token)

    assert result_payload is None
    assert error is not None
    assert error.startswith("Invalid token:")


def test_round_trip_create_and_verify():
    from src.services.auth.jwt import create_token, verify_token

    user_id = "round-trip-user"
    email = "roundtrip@example.com"
    name = "Round Trip User"
    permission_set_id = "round-trip-perm"

    token = create_token(
        user_id=user_id,
        email=email,
        name=name,
        permission_set_id=permission_set_id,
    )

    payload, error = verify_token(token)

    assert error is None
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["name"] == name
    assert payload["permissionSetId"] == permission_set_id


def test_create_token_with_null_permission_set():
    from src.services.auth.jwt import create_token, verify_token

    token = create_token(
        user_id="user-no-perms",
        email="noperms@example.com",
        name="No Perms User",
        permission_set_id=None,
    )

    payload, error = verify_token(token)

    assert error is None
    assert payload is not None
    assert payload["permissionSetId"] is None


def test_token_expiration_time():
    from src.services.auth.jwt import create_token, TOKEN_EXPIRE_HOURS

    before = datetime.now(timezone.utc).replace(microsecond=0)
    token = create_token(
        user_id="user-123",
        email="test@example.com",
        name="Test User",
        permission_set_id="perm-set-123",
    )
    after = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=1)

    decoded = jwt.decode(token, options={"verify_signature": False})
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    iat_time = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc)

    # Check that expiration is roughly TOKEN_EXPIRE_HOURS from now
    expected_exp = before + timedelta(hours=TOKEN_EXPIRE_HOURS)
    time_diff = abs((exp_time - expected_exp).total_seconds())

    assert time_diff < 5  # Within 5 seconds tolerance
    assert iat_time >= before
    assert iat_time <= after


# ════════════════════════════════════════════════════════════════════════
# CLI session helpers — short-lived access token + rotated refresh token
# ════════════════════════════════════════════════════════════════════════


def test_create_access_token_uses_15_minute_expiry():
    """The CLI access token must expire in 15 min (vs 24h for the cookie)."""
    from src.services.auth.jwt import (
        ACCESS_TOKEN_EXPIRE_MINUTES,
        create_access_token,
    )

    before = datetime.now(timezone.utc).replace(microsecond=0)
    token = create_access_token(
        user_id="user-123",
        email="cli@example.com",
        name="CLI User",
        permission_set_id=None,
    )

    decoded = jwt.decode(token, options={"verify_signature": False})
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    expected_exp = before + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    time_diff = abs((exp_time - expected_exp).total_seconds())

    assert time_diff < 5, f"expected ~15 min expiry, got {(exp_time - before).total_seconds()}s"
    # And it's verifiable by the same path the cookie tokens use.
    from src.services.auth.jwt import verify_token
    payload, err = verify_token(token)
    assert err is None
    assert payload["sub"] == "user-123"


def test_create_access_token_payload_matches_cookie_token_shape():
    """Same claims as ``create_token`` so ``verify_token`` and the
    permission decorators don't need a second code path."""
    from src.services.auth.jwt import create_access_token, create_token, verify_token

    cookie_jwt = create_token("u1", "x@y.com", "X", "ps1", role="ADMIN")
    cli_jwt = create_access_token("u1", "x@y.com", "X", "ps1", role="ADMIN")

    cookie_payload, _ = verify_token(cookie_jwt)
    cli_payload, _ = verify_token(cli_jwt)

    # Strip the time-based fields; the rest must be identical so
    # downstream auth gates can't tell the two apart.
    cookie_claims = {k: v for k, v in cookie_payload.items() if k not in ("iat", "exp")}
    cli_claims = {k: v for k, v in cli_payload.items() if k not in ("iat", "exp")}
    assert cookie_claims == cli_claims


def test_make_refresh_token_returns_raw_and_matching_hash():
    from src.services.auth.jwt import hash_refresh_token, make_refresh_token

    raw, digest = make_refresh_token()
    assert isinstance(raw, str) and len(raw) >= 32, f"raw too short: {len(raw)}"
    # Independently re-hash and compare — proves the helper isn't lying.
    assert hash_refresh_token(raw) == digest


def test_make_refresh_token_is_random_per_call():
    """Two calls must return different raw tokens AND different hashes."""
    from src.services.auth.jwt import make_refresh_token

    raws = {make_refresh_token()[0] for _ in range(50)}
    hashes = {make_refresh_token()[1] for _ in range(50)}
    # Birthday-paradox collision space is 256 bits; 50 calls colliding
    # would be a true RNG failure, not flake.
    assert len(raws) == 50
    assert len(hashes) == 50


def test_hash_refresh_token_is_deterministic():
    """Hashing the same raw twice must produce the same digest."""
    from src.services.auth.jwt import hash_refresh_token

    h1 = hash_refresh_token("constant-input-XYZ")
    h2 = hash_refresh_token("constant-input-XYZ")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_refresh_token_constants_match_documented_lifetimes():
    """Pin the constants so a future bump is a deliberate, reviewable change."""
    from src.services.auth.jwt import (
        ACCESS_TOKEN_EXPIRE_MINUTES,
        REFRESH_TOKEN_EXPIRE_DAYS,
        TOKEN_EXPIRE_HOURS,
    )

    assert ACCESS_TOKEN_EXPIRE_MINUTES == 15, (
        "CLI access tokens must be short — bumping this means callers "
        "can't transparently refresh on 401 anymore"
    )
    assert REFRESH_TOKEN_EXPIRE_DAYS == 30, (
        "Refresh tokens are the persistent session — bumping this needs "
        "a security review (longer = bigger replay window)"
    )
    # Web cookie unchanged at 24h.
    assert TOKEN_EXPIRE_HOURS == 24
