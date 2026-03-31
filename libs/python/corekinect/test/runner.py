"""Unified validation test runner.

This is the single entry point for all validation test execution.
It handles preflight checks, pytest execution, result reporting, and cleanup.

Usage:
    runner = ValidationRunner(stage="fuota", run_id="clxyz...")
    exit_code = runner.run()

Environment variables:
    CONCORD_RUN_ID: Validation run ID (required)
    CONCORD_API_URL: API base URL for reporting
    CONCORD_API_KEY: API key for auth
    STAGE: Test stage (smoke, silicon, integration, nightly, fuota)
    MTIB_ADDRESS: MTIB server address (host:port)
    DEVICE_SNR: J-Link probe serial number
    FIXTURE_PROFILE_PATH: Path to fixture profile JSON
    PIPELINE_ID: CI pipeline ID (for fuota stage)
    ARTIFACTS_DIR: Directory for test artifacts
    PRODUCT_SLUG: Product slug for catalog API lookup (e.g., "alpha_b0")
"""

import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from corekinect.utils import Logger

log = Logger(log_name="validation.runner")


# =============================================================================
# PRODUCT CONTEXT
# =============================================================================


@dataclass
class ProductContext:
    """Product metadata from the Concord catalog API.

    Carries CoreCloud identifiers, firmware app IDs, and other product-specific
    config that validation tests need (e.g., FUOTA targets, device registration).

    Loaded from /v2/products/by-slug/<slug> at session start.
    Falls back to hardcoded defaults if API is unavailable.
    """

    product_id: str = ""
    name: str = ""
    slug: str = ""
    device_type_id: int = 0
    device_variant_id: int = 0
    app_ids: Dict[str, int] = field(default_factory=dict)
    core_cloud_env: str = ""
    build_board: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, slug: str, api_url: str, api_key: str) -> "ProductContext":
        """Load product context from Concord catalog API.

        Args:
            slug: Product slug (e.g., "alpha_b0")
            api_url: Concord API base URL
            api_key: API key for authentication

        Returns:
            ProductContext populated from API response

        Raises:
            ValueError: If product not found or API request fails
        """
        api_url = api_url.rstrip("/")
        auth_prefix = "ApiKey" if api_key.startswith("ck_") else "Bearer"
        headers = {"Authorization": f"{auth_prefix} {api_key}"}

        resp = requests.get(
            f"{api_url}/v2/products/by-slug/{slug}",
            headers=headers,
            timeout=30,
        )

        if not resp.ok:
            raise ValueError(
                f"Failed to load product '{slug}' from API: {resp.status_code} {resp.text}"
            )

        response_data = resp.json()
        product_data = response_data.get("data", response_data)
        return cls.from_dict(product_data)

    @classmethod
    def from_dict(cls, data: dict) -> "ProductContext":
        """Create ProductContext from API response dict."""
        metadata = data.get("metadata") or {}
        build_config = data.get("buildConfig") or {}
        # Derive app_ids from buildConfig.targets if available
        app_ids = metadata.get("appIds", {})
        if not app_ids and build_config.get("targets"):
            targets = build_config["targets"]
            items = targets.values() if isinstance(targets, dict) else targets
            for t in items:
                if not isinstance(t, dict):
                    continue
                soc = t.get("soc", "")
                aid = t.get("appId")
                if soc and aid is not None:
                    app_ids[soc] = aid
        return cls(
            product_id=data.get("id", ""),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            device_type_id=metadata.get("deviceTypeId", 0),
            device_variant_id=metadata.get("deviceVariantId", 0),
            app_ids=app_ids,
            core_cloud_env=metadata.get("coreCloudEnv", ""),
            build_board=data.get("buildBoard", ""),
            metadata=metadata,
        )

    @classmethod
    def default(cls, product: str = "", board: str = "") -> "ProductContext":
        """Return an empty ProductContext that must be populated from the Product API.

        All fields default to empty/None. The caller is expected to load product
        configuration from /v2/products/by-slug/<slug> via from_api().
        """
        slug = f"{product}_{board}" if product and board else product or ""
        return cls(slug=slug)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class StageConfig:
    """Stage-specific configuration."""

    stage: str
    timeout_s: int
    retry_count: int
    test_path: str
    pytest_args: List[str]
    required_checks: List[str]
    artifact_patterns: List[str]

    @classmethod
    def load(cls, stage: str) -> "StageConfig":
        """Load configuration for a stage."""
        configs = {
            "nightly": cls(
                stage="nightly",
                timeout_s=3600,
                retry_count=1,
                test_path="tests/nightly/",
                pytest_args=["-v", "--tb=long"],
                required_checks=["mtib", "storage", "device", "fixture"],
                artifact_patterns=["*.log", "*.uart", "*.csv", "*.png"],
            ),
            "integration": cls(
                stage="integration",
                timeout_s=1800,
                retry_count=0,
                test_path="tests/integration/",
                pytest_args=["-v", "--tb=short"],
                required_checks=["mtib", "storage", "device", "fixture"],
                artifact_patterns=["*.log", "*.uart"],
            ),
            "smoke": cls(
                stage="smoke",
                timeout_s=300,
                retry_count=0,
                test_path="tests/smoke/",
                pytest_args=["-v", "--tb=short"],
                required_checks=[],
                artifact_patterns=[],
            ),
            "silicon": cls(
                stage="silicon",
                timeout_s=600,
                retry_count=0,
                test_path="tests/silicon/",
                pytest_args=["-v", "--tb=short"],
                required_checks=["mtib", "device"],
                artifact_patterns=["*.log", "*.uart"],
            ),
            "fuota": cls(
                stage="fuota",
                timeout_s=7200,  # 2h — FUOTA polling takes up to 90 min
                retry_count=0,
                test_path="tests/fuota/",
                pytest_args=["-v", "-s", "--tb=long"],  # No -x: tests within a class are sequential, but different test files continue independently
                required_checks=["mtib", "device"],
                artifact_patterns=["*.log", "*.uart"],
            ),
        }

        if stage not in configs:
            raise ValueError(f"Unknown stage: {stage}. Valid: {list(configs.keys())}")

        return configs[stage]


# =============================================================================
# PREFLIGHT CHECKS
# =============================================================================


@dataclass
class CheckResult:
    """Result of a single preflight check."""

    check_id: str
    description: str
    passed: bool
    message: str
    duration_ms: int = 0


@dataclass
class PreflightResult:
    """Result of all preflight checks."""

    checks: List[CheckResult]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "startedAt": self.started_at.isoformat(),
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "checks": [
                {
                    "id": c.check_id,
                    "description": c.description,
                    "passed": c.passed,
                    "message": c.message,
                    "durationMs": c.duration_ms,
                }
                for c in self.checks
            ],
        }


class PreflightChecker:
    """Validates all dependencies before test execution."""

    # Check definitions: (id, description, method_name)
    ALL_CHECKS = [
        ("mtib", "MTIB connectivity", "_check_mtib"),
        ("storage", "Disk space > 500MB", "_check_storage"),
        ("device", "Device SNR configured", "_check_device"),
        ("fixture", "Fixture profile valid", "_check_fixture"),
        ("firmware", "Firmware artifacts available", "_check_firmware"),
        ("corecloud", "CoreCloud API auth", "_check_corecloud"),
    ]

    def __init__(self, config: StageConfig):
        self.config = config

    def check_all(self) -> PreflightResult:
        """Run all required preflight checks."""
        results = []

        for check_id, description, method_name in self.ALL_CHECKS:
            # Skip checks not required for this stage
            if check_id not in self.config.required_checks:
                continue

            start = datetime.now(timezone.utc)
            try:
                method = getattr(self, method_name)
                passed, message = method()
            except Exception as e:
                passed = False
                message = f"Exception: {e}"

            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            results.append(CheckResult(check_id, description, passed, message, duration_ms))

            log.info(
                "Preflight %s: %s - %s",
                "PASS" if passed else "FAIL",
                check_id,
                message,
            )

        result = PreflightResult(checks=results)
        result.finished_at = datetime.now(timezone.utc)
        return result

    def _check_mtib(self) -> Tuple[bool, str]:
        """Verify MTIB gRPC connection."""
        address = os.environ.get("MTIB_ADDRESS")
        if not address:
            host = os.environ.get("MTIB_HOST")
            port_str = os.environ.get("MTIB_PORT", "50053")
            if not host:
                return False, "MTIB_ADDRESS or MTIB_HOST not set"
            try:
                port_num = int(port_str)
            except ValueError:
                return False, f"MTIB_PORT is not a valid integer: {port_str}"
            address = f"{host}:{port_num}"

        try:
            from corekinect.mtib_client.v1.client.config import NetConfig
            from corekinect.mtib_client.v1.client.core import MtibV1Client

            # Parse address - handle host:port format, default port 50053
            parts = address.rsplit(":", 1)
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 50053
            cfg = MtibV1Client.Config(net=NetConfig(addr=host, port=port))
            client = MtibV1Client(cfg)

            err = client.connect()
            if err:
                return False, f"Connection failed: {err}"

            # HealthCheck returns (ok, details, err)
            result = client.HealthCheck()
            client.disconnect()

            if isinstance(result, tuple) and len(result) >= 3:
                ok, details, err = result[0], result[1], result[2]
            else:
                ok, err = result if isinstance(result, tuple) else (result, None)

            if err:
                return False, f"Health check failed: {err}"

            return True, f"Connected to {address}"

        except Exception as e:
            return False, str(e)

    def _check_storage(self) -> Tuple[bool, str]:
        """Verify sufficient disk space."""
        try:
            usage = shutil.disk_usage("/")
            free_mb = usage.free / (1024 * 1024)
            if free_mb < 500:
                return False, f"Only {free_mb:.0f}MB free (need 500MB)"
            return True, f"{free_mb:.0f}MB available"
        except Exception as e:
            return False, str(e)

    def _check_device(self) -> Tuple[bool, str]:
        """Verify device SNR is configured."""
        snr = os.environ.get("DEVICE_SNR")
        if not snr:
            return False, "DEVICE_SNR not set"
        return True, f"SNR: {snr}"

    def _check_fixture(self) -> Tuple[bool, str]:
        """Verify fixture profile exists and is valid."""
        path = os.environ.get("FIXTURE_PROFILE_PATH")
        if not path:
            return False, "FIXTURE_PROFILE_PATH not set"

        if not os.path.exists(path):
            return False, f"File not found: {path}"

        try:
            with open(path) as f:
                profile = json.load(f)

            required = ["product", "board"]
            missing = [k for k in required if k not in profile]
            if missing:
                return False, f"Missing fields: {missing}"

            product = profile.get("product", "?")
            board = profile.get("board", "?")
            return True, f"{product}/{board}"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            return False, str(e)

    def _check_firmware(self) -> Tuple[bool, str]:
        """Verify firmware artifacts are available."""
        pipeline_id = os.environ.get("PIPELINE_ID")
        if not pipeline_id:
            # For fuota, PIPELINE_ID is required
            if self.config.stage == "fuota":
                return False, "PIPELINE_ID required for fuota tests"
            return True, "Not required for this stage"

        # TODO: Actually verify the pipeline has artifacts
        return True, f"Pipeline: {pipeline_id[:12]}..."

    def _check_corecloud(self) -> Tuple[bool, str]:
        """Verify CoreCloud API authentication."""
        # Only required for fuota stage
        if self.config.stage not in ("fuota",):
            return True, "Not required for this stage"

        api_key = os.environ.get("VAL_1_0_API_KEY")
        if not api_key:
            return False, "VAL_1_0_API_KEY not set"

        try:
            from corekinect.test.fuota_client import FuotaClient

            client = FuotaClient(api_env="VAL_1_0")
            client._ensure_token()
            return True, "Authenticated"
        except Exception as e:
            return False, str(e)


# =============================================================================
# RESULT REPORTER
# =============================================================================


class RunReporter:
    """Reports run progress to Concord API."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.api_url = os.environ.get("CONCORD_API_URL", "").rstrip("/")
        self.api_key = os.environ.get("CONCORD_API_KEY", "")
        self.enabled = bool(self.api_url and self.api_key and run_id)

        if self.enabled:
            self.session = requests.Session()
            self.session.headers["Authorization"] = f"ApiKey {self.api_key}"
            self.session.headers["Content-Type"] = "application/json"
        else:
            self.session = None
            log.warning("Reporter disabled: missing CONCORD_API_URL, CONCORD_API_KEY, or run_id")

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict]:
        """POST to the API."""
        if not self.enabled:
            return None

        url = f"{self.api_url}/v2/sessions/{self.run_id}{endpoint}"
        try:
            resp = self.session.post(url, json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("Reporter POST failed: %s - %s", endpoint, e)
            return None

    def report_preflight_start(self):
        """Report preflight checks starting."""
        self._post("/report/preflight", {"status": "RUNNING"})

    def report_preflight_result(self, result: PreflightResult):
        """Report preflight check results."""
        self._post("/report/preflight", {
            "status": "PASSED" if result.passed else "FAILED",
            "checks": result.to_dict()["checks"],
        })

    def report_run_failed(self, error: str, stage: str = "unknown"):
        """Report run failed before tests started."""
        self._post("/report/finish", {
            "status": "FAILED",
            "errorMessage": error,
            "stage": stage,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
        })


# =============================================================================
# ARTIFACT COLLECTOR
# =============================================================================


class ArtifactCollector:
    """Collects and uploads test artifacts."""

    def __init__(self, config: StageConfig, reporter: RunReporter):
        self.config = config
        self.reporter = reporter
        self.artifacts_dir = Path(os.environ.get("ARTIFACTS_DIR", "/tmp/artifacts"))

    def collect_all(self) -> int:
        """Collect and upload all artifacts. Returns count."""
        if not self.artifacts_dir.exists():
            log.info("No artifacts directory: %s", self.artifacts_dir)
            return 0

        count = 0
        for pattern in self.config.artifact_patterns:
            try:
                for path in self.artifacts_dir.glob(pattern):
                    if path.is_file():
                        log.info("Artifact: %s (%d bytes)", path.name, path.stat().st_size)
                        # TODO: Upload to API/MinIO
                        count += 1
            except Exception as exc:
                log.warning("Failed to collect artifacts for pattern %s: %s", pattern, exc)

        return count


# =============================================================================
# VALIDATION RUNNER
# =============================================================================


class ValidationRunner:
    """Unified validation test runner."""

    def __init__(self, stage: str, run_id: str):
        self.stage = stage
        self.run_id = run_id
        self.config = StageConfig.load(stage)
        self.preflight = PreflightChecker(self.config)
        self.reporter = RunReporter(run_id)
        self.collector = ArtifactCollector(self.config, self.reporter)

    def run(self) -> int:
        """Execute the full test run. Returns exit code."""
        log.info("=" * 60)
        log.info("ValidationRunner: stage=%s run_id=%s", self.stage, self.run_id)
        log.info("=" * 60)

        try:
            # 1. Preflight checks
            log.info("Running preflight checks...")
            self.reporter.report_preflight_start()

            preflight_result = self.preflight.check_all()
            self.reporter.report_preflight_result(preflight_result)

            if not preflight_result.passed:
                failed = ", ".join(c.check_id for c in preflight_result.failed_checks)
                error_msg = f"Preflight failed: {failed}"
                log.error(error_msg)
                self.reporter.report_run_failed(error_msg, "preflight")
                return 1

            log.info("Preflight passed (%d checks)", len(preflight_result.checks))

            # 2. Execute pytest
            log.info("Running tests: %s", self.config.test_path)
            exit_code = self._run_pytest()
            log.info("pytest exit code: %d", exit_code)

            # 3. Collect artifacts
            artifact_count = self.collector.collect_all()
            log.info("Collected %d artifacts", artifact_count)

            # 4. Final cleanup
            self._cleanup()

            return exit_code

        except KeyboardInterrupt:
            log.warning("Interrupted by user")
            self.reporter.report_run_failed("Interrupted by user", "interrupt")
            return 130

        except Exception as e:
            error_msg = f"Runner exception: {e}\n{traceback.format_exc()}"
            log.error(error_msg)
            self.reporter.report_run_failed(str(e), "exception")
            return 1

    def _run_pytest(self) -> int:
        """Run pytest and return exit code."""
        args = [
            sys.executable,
            "-m",
            "pytest",
            self.config.test_path,
            f"--timeout={self.config.timeout_s}",
            *self.config.pytest_args,
        ]

        # Optional test filter from env (e.g. "test_02" to skip test_01)
        pytest_filter = os.environ.get("PYTEST_FILTER", "").strip()
        if pytest_filter:
            args.extend(["-k", pytest_filter])
            log.info("pytest filter: -k %s", pytest_filter)

        log.info("pytest command: %s", " ".join(args))

        env = os.environ.copy()
        # Ensure PYTHONPATH includes our libs
        pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pythonpath

        result = subprocess.run(
            args,
            env=env,
            cwd=os.getcwd(),
        )

        return result.returncode

    def _cleanup(self):
        """Final cleanup tasks."""
        log.info("Cleanup complete")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run validation tests")
    parser.add_argument(
        "--stage",
        default=os.environ.get("STAGE", "fuota"),
        choices=["smoke", "silicon", "integration", "nightly", "fuota"],
        help="Test stage to run",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CONCORD_RUN_ID"),
        help="Validation run ID for reporting",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks, don't run tests",
    )

    args = parser.parse_args()

    if not args.run_id:
        log.warning("No run_id provided - reporting disabled")
        args.run_id = f"local-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    runner = ValidationRunner(stage=args.stage, run_id=args.run_id)

    if args.preflight_only:
        result = runner.preflight.check_all()
        for check in result.checks:
            status = "PASS" if check.passed else "FAIL"
            log.info("[%s] %s: %s", status, check.check_id, check.message)
        sys.exit(0 if result.passed else 1)

    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
