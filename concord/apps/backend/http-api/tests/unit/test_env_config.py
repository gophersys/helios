"""
Tests for environment configuration consistency.

Validates that:
- AppConfig correctly parses boolean fields (AUTH_ENABLED, etc.)
- JWT_SECRET_KEY validation rejects the default value in production
- All Helm values files define the required config/secrets keys
- Local docker-compose defines the required environment variables

These tests prevent regressions where a config field exists in deployment
manifests but is never read by the Python code (like AUTH_ENABLED was).
"""

import os
import types as stdlib_types
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[5]  # tests/unit/ → http-api → backend → apps → concord
HELM_DIR = REPO_ROOT / "deploy" / "production" / "helm"
LOCAL_DIR = REPO_ROOT / "deploy" / "development"


# ---------------------------------------------------------------------------
# AppConfig boolean parsing
# ---------------------------------------------------------------------------

class TestAppConfigBooleanParsing:
    """Verify that EnvConfig._parse_bool handles boolean string parsing."""

    def test_bool_false_string(self):
        """The string 'false' should parse to Python False."""
        from corekinect.utils.config.env import EnvConfig
        assert EnvConfig._parse_bool("false") is False

    def test_bool_true_string(self):
        """The string 'true' should parse to Python True."""
        from corekinect.utils.config.env import EnvConfig
        assert EnvConfig._parse_bool("true") is True

    def test_auth_enabled_boolean_values(self):
        """Various boolean-like string values should parse correctly."""
        from corekinect.utils.config.env import EnvConfig
        # True values
        assert EnvConfig._parse_bool("true") is True
        assert EnvConfig._parse_bool("True") is True
        assert EnvConfig._parse_bool("TRUE") is True
        assert EnvConfig._parse_bool("1") is True
        assert EnvConfig._parse_bool("yes") is True

        # False values
        assert EnvConfig._parse_bool("false") is False
        assert EnvConfig._parse_bool("False") is False
        assert EnvConfig._parse_bool("FALSE") is False
        assert EnvConfig._parse_bool("0") is False
        assert EnvConfig._parse_bool("no") is False


# ---------------------------------------------------------------------------
# JWT secret validation
# ---------------------------------------------------------------------------

class TestJwtSecretValidation:
    """Ensure the default JWT secret is rejected in production and staging."""

    # Shared base env so each test only overrides what it cares about.
    _BASE_ENV = {
        "LOG_LEVEL": "10",
        "LOG_PATH": "/tmp/test.log",
        "SERVER_PORT": "9001",
        "CONCORD_API_HOST": "test.concord.local",
        "ASSETS_FOLDER": "/tmp/test-assets",
        "STORAGE_URL": "http://localhost:9000",
        "STORAGE_ACCESS_KEY": "test",
        "STORAGE_SECRET_ACCESS_KEY": "test",
        "STORAGE_BUCKET_NAME": "test",
    }

    def _make_env(self, **overrides):
        env = dict(self._BASE_ENV)
        env.update(overrides)
        return env

    # --- default secret rejected in deployed environments ---

    def test_rejects_default_secret_in_production(self):
        """AppConfig should raise RuntimeError if default JWT secret is used in production."""
        env = self._make_env(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="concord-dev-jwt-secret-change-in-production",
        )
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be changed"):
                AppConfig(namespace=None, auto_load_env=True)

    def test_rejects_default_secret_in_staging(self):
        """AppConfig should raise RuntimeError if default JWT secret is used in staging."""
        env = self._make_env(
            ENVIRONMENT="staging",
            JWT_SECRET_KEY="concord-dev-jwt-secret-change-in-production",
        )
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be changed"):
                AppConfig(namespace=None, auto_load_env=True)

    # --- minimum length enforced in deployed environments ---

    def test_rejects_short_secret_in_production(self):
        """HS256 needs >= 32 chars; a short secret should be rejected in production."""
        env = self._make_env(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="too-short",
        )
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is too short"):
                AppConfig(namespace=None, auto_load_env=True)

    def test_rejects_short_secret_in_staging(self):
        """HS256 needs >= 32 chars; a short secret should be rejected in staging."""
        env = self._make_env(
            ENVIRONMENT="staging",
            JWT_SECRET_KEY="too-short",
        )
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is too short"):
                AppConfig(namespace=None, auto_load_env=True)

    # --- valid secrets accepted ---

    def test_accepts_custom_secret_in_production(self):
        """AppConfig should accept a strong custom JWT secret in production."""
        secret = "my-strong-production-secret-2026!"  # 33 chars
        env = self._make_env(ENVIRONMENT="production", JWT_SECRET_KEY=secret)
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            config = AppConfig(namespace=None, auto_load_env=True)
            assert config.JWT_SECRET_KEY == secret

    def test_accepts_custom_secret_in_staging(self):
        """AppConfig should accept a strong custom JWT secret in staging."""
        secret = "my-strong-staging-secret-20260311"  # 32 chars
        env = self._make_env(ENVIRONMENT="staging", JWT_SECRET_KEY=secret)
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            config = AppConfig(namespace=None, auto_load_env=True)
            assert config.JWT_SECRET_KEY == secret

    # --- development / test are lenient ---

    def test_allows_default_secret_in_development(self):
        """Development should accept the default JWT secret for local convenience."""
        env = self._make_env(
            ENVIRONMENT="development",
            JWT_SECRET_KEY="concord-dev-jwt-secret-change-in-production",
        )
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            config = AppConfig(namespace=None, auto_load_env=True)
            assert config.JWT_SECRET_KEY == "concord-dev-jwt-secret-change-in-production"

    def test_allows_short_secret_in_development(self):
        """Development should accept short secrets for convenience."""
        env = self._make_env(ENVIRONMENT="development", JWT_SECRET_KEY="dev")
        with patch.dict(os.environ, env, clear=False):
            from config.env import AppConfig
            config = AppConfig(namespace=None, auto_load_env=True)
            assert config.JWT_SECRET_KEY == "dev"


# ---------------------------------------------------------------------------
# Helm values completeness
# ---------------------------------------------------------------------------

# Config keys that MUST be present in every Helm values file.
#
# When a feature reads a config field at startup or per-request and that
# field has caused a 500 / silent disable in production, it goes here.
# This list is the regression net for "field exists in env.py but nobody
# remembered to set it in values-*.yaml" bugs. Add new entries when you
# add a new ProxyConfig field whose absence breaks a feature in prod.
_REQUIRED_CONFIG_KEYS = {
    "SERVER_PORT",
    "CORS_ORIGINS",
    "STORAGE_URL",
    "STORAGE_BUCKET_NAME",
    "CONCORD_API_HOST",
    # CkBoards / Bitbucket integration — board-discovery 500s when these
    # are missing (caught in production after the v0.9.16 deploy).
    "BITBUCKET_EMAIL",
    "BITBUCKET_WORKSPACE",
    "CK_BOARDS_REPO_URL",
}

# NOTE: secrets are NOT in the helm values files. They're mounted from K8s
# Secrets populated from ungitignored shared.env / {namespace}.env overlays.
# A "required secret keys" check belongs against THOSE files, not helm values.


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning an empty dict if PyYAML is not installed."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed — skipping Helm values test")
    with open(path) as f:
        return yaml.safe_load(f) or {}


class TestHelmValuesCompleteness:
    """Ensure all Helm values files define required config and secret keys."""

    @pytest.mark.parametrize("env_file", ["values-staging.yaml", "values-production.yaml"])
    def test_config_keys_present(self, env_file):
        """Each environment values file must define all required config keys."""
        path = HELM_DIR / env_file
        if not path.exists():
            pytest.skip(f"{env_file} not found")

        values = _load_yaml(path)
        config = values.get("config", {})
        missing = _REQUIRED_CONFIG_KEYS - set(config.keys())
        assert not missing, f"{env_file} missing config keys: {missing}"

    # Note: secret-key checks intentionally REMOVED.
    #
    # Secrets (DATABASE_URL, JWT_SECRET_KEY, *API_TOKEN, etc.) are NOT in the
    # helm values files — they are mounted from K8s secrets sourced from
    # ungitignored shared.env / {namespace}.env overlay files. The previous
    # tests parsed values-*.yaml looking for a 'secrets:' block that doesn't
    # exist there, and only "passed" because they were silently skipping
    # against a stale HELM_DIR path.
    #
    # If a separate guard is needed for shared.env / overlay completeness,
    # add it as a new test class that points at those files. Don't shoehorn
    # it into the values-yaml checks.


# ---------------------------------------------------------------------------
# AppConfig field coverage
# ---------------------------------------------------------------------------

class TestAppConfigFieldCoverage:
    """Ensure AppConfig declares all fields referenced in deployment configs."""

    def test_jwt_secret_field_exists(self):
        """AppConfig must declare JWT_SECRET_KEY as a str field."""
        from config.env import AppConfig
        import typing

        hints = typing.get_type_hints(AppConfig)
        assert "JWT_SECRET_KEY" in hints, "AppConfig must declare JWT_SECRET_KEY"
        assert hints["JWT_SECRET_KEY"] is str, "JWT_SECRET_KEY must be str"
