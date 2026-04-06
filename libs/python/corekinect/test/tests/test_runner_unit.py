"""Unit tests for corekinect.test.runner.

Tests the logic paths of ProductContext, StageConfig, CheckResult,
and PreflightResult without network calls or subprocess execution.
"""

from datetime import datetime, timezone

import pytest

from corekinect.test.runner import (
    CheckResult,
    PreflightResult,
    ProductContext,
    StageConfig,
)


# =============================================================================
# ProductContext.from_dict
# =============================================================================


def _product_api_response():
    """Return a realistic product API response dict."""
    return {
        "id": "clxyz123",
        "name": "Alpha B0",
        "slug": "alpha_b0",
        "buildBoard": "alpha_b0_nrf52840",
        "metadata": {
            "deviceTypeId": 2,
            "deviceVariantId": 3,
            "appIds": {"nrf9151": 108, "nrf52840": 109},
            "coreCloudEnv": "VAL_1_0",
        },
        "buildConfig": {
            "targets": {
                "comms": {"soc": "nrf9151", "appId": 108},
                "app": {"soc": "nrf52840", "appId": 109},
            }
        },
    }


class TestProductContextFromDict:
    def test_parses_all_fields(self):
        data = _product_api_response()
        ctx = ProductContext.from_dict(data)

        assert ctx.product_id == "clxyz123"
        assert ctx.name == "Alpha B0"
        assert ctx.slug == "alpha_b0"
        assert ctx.device_type_id == 2
        assert ctx.device_variant_id == 3
        assert ctx.core_cloud_env == "VAL_1_0"
        assert ctx.build_board == "alpha_b0_nrf52840"

    def test_parses_app_ids_from_metadata(self):
        data = _product_api_response()
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids == {"nrf9151": 108, "nrf52840": 109}

    def test_derives_app_ids_from_build_config_when_metadata_empty(self):
        data = {
            "id": "abc",
            "metadata": {},
            "buildConfig": {
                "targets": {
                    "comms": {"soc": "nrf9151", "appId": 108},
                    "app": {"soc": "nrf52840", "appId": 109},
                }
            },
        }
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids["nrf9151"] == 108
        assert ctx.app_ids["nrf52840"] == 109

    def test_handles_missing_metadata(self):
        data = {"id": "abc", "name": "Test"}
        ctx = ProductContext.from_dict(data)
        assert ctx.device_type_id == 0
        assert ctx.device_variant_id == 0
        assert ctx.app_ids == {}

    def test_handles_empty_dict(self):
        ctx = ProductContext.from_dict({})
        assert ctx.product_id == ""
        assert ctx.name == ""
        assert ctx.slug == ""

    def test_handles_targets_as_list(self):
        data = {
            "metadata": {},
            "buildConfig": {
                "targets": [
                    {"soc": "nrf9151", "appId": 108},
                    {"soc": "nrf52840", "appId": 109},
                ]
            },
        }
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids["nrf9151"] == 108
        assert ctx.app_ids["nrf52840"] == 109

    def test_skips_non_dict_target_items(self):
        data = {
            "metadata": {},
            "buildConfig": {
                "targets": ["not-a-dict", {"soc": "nrf52840", "appId": 109}]
            },
        }
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids == {"nrf52840": 109}


# =============================================================================
# ProductContext.default
# =============================================================================


class TestProductContextDefault:
    def test_returns_empty_context(self):
        ctx = ProductContext.default()
        assert ctx.product_id == ""
        assert ctx.name == ""
        assert ctx.slug == ""
        assert ctx.device_type_id == 0
        assert ctx.app_ids == {}

    def test_slug_from_product_and_board(self):
        ctx = ProductContext.default(product="alpha", board="b0")
        assert ctx.slug == "alpha_b0"

    def test_slug_from_product_only(self):
        ctx = ProductContext.default(product="alpha")
        assert ctx.slug == "alpha"

    def test_slug_empty_when_nothing_provided(self):
        ctx = ProductContext.default()
        assert ctx.slug == ""

    def test_slug_empty_when_board_only(self):
        ctx = ProductContext.default(board="b0")
        assert ctx.slug == ""


# =============================================================================
# StageConfig.load
# =============================================================================


class TestStageConfigLoad:
    def test_smoke_stage(self):
        cfg = StageConfig.load("smoke")
        assert cfg.stage == "smoke"
        assert cfg.timeout_s == 300
        assert cfg.test_path == "tests/smoke/"
        assert "-v" in cfg.pytest_args
        assert cfg.required_checks == []

    def test_driver_stage(self):
        cfg = StageConfig.load("driver")
        assert cfg.stage == "driver"
        assert cfg.timeout_s == 600
        assert cfg.test_path == "tests/driver/"
        assert "mtib" in cfg.required_checks
        assert "device" in cfg.required_checks

    def test_integration_stage(self):
        cfg = StageConfig.load("integration")
        assert cfg.stage == "integration"
        assert cfg.timeout_s == 1800
        assert cfg.test_path == "tests/integration/"
        assert "fixture" in cfg.required_checks

    def test_regression_stage(self):
        cfg = StageConfig.load("regression")
        assert cfg.stage == "regression"
        assert cfg.timeout_s == 3600
        assert cfg.retry_count == 1
        assert "*.csv" in cfg.artifact_patterns
        assert "*.png" in cfg.artifact_patterns

    def test_fuota_stage(self):
        cfg = StageConfig.load("fuota")
        assert cfg.stage == "fuota"
        assert cfg.timeout_s == 7200
        assert cfg.test_path == "tests/fuota/"
        assert "-s" in cfg.pytest_args

    def test_unknown_stage_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown stage"):
            StageConfig.load("nonexistent")

    def test_unknown_stage_lists_valid_stages(self):
        with pytest.raises(ValueError) as exc_info:
            StageConfig.load("bad")
        msg = str(exc_info.value)
        for valid in ("smoke", "driver", "integration", "regression", "fuota"):
            assert valid in msg

    def test_all_stages_have_test_path(self):
        for stage in ("smoke", "driver", "integration", "regression", "fuota"):
            cfg = StageConfig.load(stage)
            assert cfg.test_path.startswith("tests/")
            assert cfg.test_path.endswith("/")

    def test_all_stages_have_positive_timeout(self):
        for stage in ("smoke", "driver", "integration", "regression", "fuota"):
            cfg = StageConfig.load(stage)
            assert cfg.timeout_s > 0


# =============================================================================
# CheckResult
# =============================================================================


class TestCheckResult:
    def test_construction_passed(self):
        cr = CheckResult(
            check_id="mtib",
            description="MTIB connectivity",
            passed=True,
            message="Connected to 10.4.45.33",
            duration_ms=42,
        )
        assert cr.check_id == "mtib"
        assert cr.passed is True
        assert cr.duration_ms == 42

    def test_construction_failed(self):
        cr = CheckResult(
            check_id="device",
            description="Device SNR configured",
            passed=False,
            message="DEVICE_SNR not set",
        )
        assert cr.passed is False
        assert cr.message == "DEVICE_SNR not set"

    def test_default_duration(self):
        cr = CheckResult(check_id="x", description="x", passed=True, message="ok")
        assert cr.duration_ms == 0


# =============================================================================
# PreflightResult
# =============================================================================


class TestPreflightResult:
    def test_passed_all_pass(self):
        checks = [
            CheckResult("a", "A", True, "ok"),
            CheckResult("b", "B", True, "ok"),
            CheckResult("c", "C", True, "ok"),
        ]
        result = PreflightResult(checks=checks)
        assert result.passed is True

    def test_passed_one_fail(self):
        checks = [
            CheckResult("a", "A", True, "ok"),
            CheckResult("b", "B", False, "nope"),
            CheckResult("c", "C", True, "ok"),
        ]
        result = PreflightResult(checks=checks)
        assert result.passed is False

    def test_passed_empty_checks(self):
        result = PreflightResult(checks=[])
        assert result.passed is True

    def test_failed_checks_returns_only_failures(self):
        checks = [
            CheckResult("a", "A", True, "ok"),
            CheckResult("b", "B", False, "fail-b"),
            CheckResult("c", "C", False, "fail-c"),
        ]
        result = PreflightResult(checks=checks)
        failed = result.failed_checks
        assert len(failed) == 2
        assert all(not c.passed for c in failed)
        ids = {c.check_id for c in failed}
        assert ids == {"b", "c"}

    def test_failed_checks_empty_when_all_pass(self):
        checks = [CheckResult("a", "A", True, "ok")]
        result = PreflightResult(checks=checks)
        assert result.failed_checks == []

    def test_to_dict_structure(self):
        checks = [
            CheckResult("mtib", "MTIB", True, "connected", duration_ms=10),
        ]
        result = PreflightResult(checks=checks)
        result.finished_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        d = result.to_dict()

        assert d["passed"] is True
        assert d["finishedAt"] is not None
        assert len(d["checks"]) == 1
        assert d["checks"][0]["id"] == "mtib"
        assert d["checks"][0]["passed"] is True
        assert d["checks"][0]["durationMs"] == 10

    def test_to_dict_no_finished_at(self):
        result = PreflightResult(checks=[])
        d = result.to_dict()
        assert d["finishedAt"] is None

    def test_started_at_is_auto_set(self):
        result = PreflightResult(checks=[])
        assert result.started_at is not None
        assert isinstance(result.started_at, datetime)
