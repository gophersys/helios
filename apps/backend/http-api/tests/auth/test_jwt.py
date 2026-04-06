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
