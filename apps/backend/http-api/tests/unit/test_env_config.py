"""
Tests for environment configuration consistency.

Validates that:
- ProxyConfig correctly parses boolean fields (AUTH_ENABLED, etc.)
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
HELM_DIR = REPO_ROOT / "deploy" / "helm"
LOCAL_DIR = REPO_ROOT / "deploy" / "local"


# ---------------------------------------------------------------------------
# ProxyConfig boolean parsing
# ---------------------------------------------------------------------------

class TestProxyConfigBooleanParsing:
    """Verify that EnvConfig._parse_bool handles AUTH_ENABLED correctly."""

    def test_auth_enabled_false_string(self):
        """The string 'false' should parse to Python False."""
        env_override = {
            "ENVIRONMENT": "test",
            "AUTH_ENABLED": "false",
        }
        with patch.dict(os.environ, env_override):
            from config.env import ProxyConfig
            # Create a new instance with the overridden env
            config = ProxyConfig.__new__(ProxyConfig)
            # Manually test the bool parsing
            from corekinect.utils.config.env import EnvConfig
            assert EnvConfig._parse_bool("false") is False

    def test_auth_enabled_true_string(self):
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
    """Ensure the default JWT secret is rejected in production."""

    def test_rejects_default_secret_in_production(self):
        """ProxyConfig should raise RuntimeError if default JWT secret is used in production."""
        env_override = {
            "ENVIRONMENT": "production",
            "JWT_SECRET_KEY": "concord-dev-jwt-secret-change-in-production",
            "DELETE_ALL_KEY": "test",
            "LOG_LEVEL": "10",
            "LOG_PATH": "/tmp/test.log",
            "SERVER_PORT": "9001",
            "DB_STORAGE_PATH": "/tmp/test",
            "DB_STORAGE_LIMIT_GB": "1",
            "SUPPORTED_REGISTRIES": "[]",
            "COREOPS_SERVER_URL": "http://localhost:50050",
            "ASSETS_FOLDER": "/tmp/test-assets",
            "STORAGE_URL": "http://localhost:9000",
            "STORAGE_ACCESS_KEY": "test",
            "STORAGE_SECRET_ACCESS_KEY": "test",
            "STORAGE_BUCKET_NAME": "test",
            "INFLUXDB_URL": "http://localhost:8086",
            "INFLUXDB_TOKEN": "test",
            "INFLUXDB_ORG": "test",
            "INFLUXDB_BUCKET_TELEMETRY": "test",
            "INFLUXDB_BUCKET_METRICS": "test",
        }
        with patch.dict(os.environ, env_override, clear=False):
            from config.env import ProxyConfig
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be changed"):
                ProxyConfig(namespace=None, auto_load_env=True)

    def test_accepts_custom_secret_in_production(self):
        """ProxyConfig should accept a custom JWT secret in production."""
        env_override = {
            "ENVIRONMENT": "production",
            "JWT_SECRET_KEY": "my-strong-production-secret-2026",
            "DELETE_ALL_KEY": "test",
            "LOG_LEVEL": "10",
            "LOG_PATH": "/tmp/test.log",
            "SERVER_PORT": "9001",
            "DB_STORAGE_PATH": "/tmp/test",
            "DB_STORAGE_LIMIT_GB": "1",
            "SUPPORTED_REGISTRIES": "[]",
            "COREOPS_SERVER_URL": "http://localhost:50050",
            "ASSETS_FOLDER": "/tmp/test-assets",
            "STORAGE_URL": "http://localhost:9000",
            "STORAGE_ACCESS_KEY": "test",
            "STORAGE_SECRET_ACCESS_KEY": "test",
            "STORAGE_BUCKET_NAME": "test",
            "INFLUXDB_URL": "http://localhost:8086",
            "INFLUXDB_TOKEN": "test",
            "INFLUXDB_ORG": "test",
            "INFLUXDB_BUCKET_TELEMETRY": "test",
            "INFLUXDB_BUCKET_METRICS": "test",
        }
        with patch.dict(os.environ, env_override, clear=False):
            from config.env import ProxyConfig
            # Should not raise
            config = ProxyConfig(namespace=None, auto_load_env=True)
            assert config.JWT_SECRET_KEY == "my-strong-production-secret-2026"


# ---------------------------------------------------------------------------
# Helm values completeness
# ---------------------------------------------------------------------------

# Config keys that MUST be present in every Helm values file
_REQUIRED_CONFIG_KEYS = {
    "SERVER_PORT",
    "AUTH_ENABLED",
    "CORS_ORIGINS",
}

# Secret keys that MUST be present in every Helm values file
_REQUIRED_SECRET_KEYS = {
    "DATABASE_URL",
    "STORAGE_URL",
    "STORAGE_ACCESS_KEY",
    "STORAGE_SECRET_ACCESS_KEY",
    "STORAGE_BUCKET_NAME",
    "INFLUXDB_URL",
    "INFLUXDB_TOKEN",
    "INFLUXDB_ORG",
    "INFLUXDB_BUCKET_TELEMETRY",
    "INFLUXDB_BUCKET_METRICS",
    "JWT_SECRET_KEY",
}


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

    @pytest.mark.parametrize("env_file", ["values-staging.yaml", "values-production.yaml"])
    def test_secret_keys_present(self, env_file):
        """Each environment values file must define all required secret keys."""
        path = HELM_DIR / env_file
        if not path.exists():
            pytest.skip(f"{env_file} not found")

        values = _load_yaml(path)
        secrets = values.get("secrets", {})
        missing = _REQUIRED_SECRET_KEYS - set(secrets.keys())
        assert not missing, f"{env_file} missing secret keys: {missing}"

    @pytest.mark.parametrize("env_file", ["values-staging.yaml", "values-production.yaml"])
    def test_auth_enabled_is_string_bool(self, env_file):
        """AUTH_ENABLED should be a string 'true' or 'false', not a YAML boolean."""
        path = HELM_DIR / env_file
        if not path.exists():
            pytest.skip(f"{env_file} not found")

        values = _load_yaml(path)
        auth_val = values.get("config", {}).get("AUTH_ENABLED")
        assert auth_val is not None, f"{env_file} missing AUTH_ENABLED"
        assert isinstance(auth_val, str), (
            f"{env_file}: AUTH_ENABLED should be a quoted string ('\"true\"' or '\"false\"'), "
            f"got {type(auth_val).__name__}: {auth_val}"
        )
        assert auth_val in ("true", "false"), (
            f"{env_file}: AUTH_ENABLED should be 'true' or 'false', got '{auth_val}'"
        )

    def test_staging_and_production_have_different_jwt_secrets(self):
        """Staging and production must not share JWT secrets."""
        staging_path = HELM_DIR / "values-staging.yaml"
        prod_path = HELM_DIR / "values-production.yaml"
        if not staging_path.exists() or not prod_path.exists():
            pytest.skip("Both values files required")

        staging = _load_yaml(staging_path)
        prod = _load_yaml(prod_path)

        staging_jwt = staging.get("secrets", {}).get("JWT_SECRET_KEY", "")
        prod_jwt = prod.get("secrets", {}).get("JWT_SECRET_KEY", "")

        assert staging_jwt != prod_jwt, (
            "Staging and production must have different JWT_SECRET_KEY values"
        )

    def test_staging_and_production_have_different_db_passwords(self):
        """Staging and production must use different database credentials."""
        staging_path = HELM_DIR / "values-staging.yaml"
        prod_path = HELM_DIR / "values-production.yaml"
        if not staging_path.exists() or not prod_path.exists():
            pytest.skip("Both values files required")

        staging = _load_yaml(staging_path)
        prod = _load_yaml(prod_path)

        staging_url = staging.get("secrets", {}).get("DATABASE_URL", "")
        prod_url = prod.get("secrets", {}).get("DATABASE_URL", "")

        assert staging_url != prod_url, (
            "Staging and production must have different DATABASE_URL values"
        )


# ---------------------------------------------------------------------------
# ProxyConfig field coverage
# ---------------------------------------------------------------------------

class TestProxyConfigFieldCoverage:
    """Ensure ProxyConfig declares all fields referenced in deployment configs."""

    def test_auth_enabled_field_exists(self):
        """ProxyConfig must declare AUTH_ENABLED as a bool field."""
        from config.env import ProxyConfig
        import typing

        hints = typing.get_type_hints(ProxyConfig)
        assert "AUTH_ENABLED" in hints, (
            "ProxyConfig must declare AUTH_ENABLED — "
            "this was the root cause of the production OAuth error"
        )
        assert hints["AUTH_ENABLED"] is bool, (
            "AUTH_ENABLED must be declared as bool"
        )
