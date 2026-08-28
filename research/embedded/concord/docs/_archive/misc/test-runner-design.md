# Validation Test Runner Architecture

## The Problem

All validation tests live in the same container (`apps/validation/alpha/`) but:
- Run at different stages (gate, regression, integration)
- Have different triggers (PR, cron, manual)
- Need different timeouts and retry logic
- Produce different outputs and visualizations
- Share common infrastructure needs (MTIB, CoreCloud, storage)

We need a unified wrapper that:
1. Handles preflight checks consistently
2. Manages stage-specific configuration
3. Provides robust failure handling
4. Standardizes result collection and reporting
5. Supports restart/resume capabilities

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRIGGER LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  PR Merge ──► CI Webhook ──► API ──► K8s Job (gate)                     │
│  Cron ──────► CronJob ──────► API ──► K8s Job (regression)                 │
│  Manual ────► API Call ─────► API ──► K8s Job (integration)             │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      K8s JOB (validation container)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ValidationRunner                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │  Preflight  │─▶│   pytest    │─▶│  Reporter   │               │   │
│  │  │   Checks    │  │  execution  │  │  + Cleanup  │               │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Environment:                                                            │
│    STAGE=gate|regression|integration                                        │
│    RUN_ID=clxyz...                                                       │
│    MTIB_ADDRESS=10.4.45.33:50053                                         │
│    DEVICE_SNR=0964                                                       │
│    PIPELINE_ID=clxyz... (for gate)                                       │
│    VAL_1_0_API_* (for FUOTA)                                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         RESULT LAYER                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Real-time:  WebSocket ──► Frontend (live test progress)                │
│  Persistent: PostgreSQL ──► ValidationRun, ValidationStep               │
│  Artifacts:  MinIO ──► UART logs, power traces, firmware                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Stage Configuration

| Stage | Trigger | Timeout | Retry | Hardware | External Services |
|-------|---------|---------|-------|----------|-------------------|
| gate | PR merge | 15 min | 0 | MTIB, J-Link | CoreCloud FUOTA, MinIO |
| regression | Cron 2AM | 60 min | 1 | MTIB, sensors | CoreCloud, InfluxDB |
| integration | Manual | 30 min | 0 | MTIB, harness FW | None |

## Component Design

### 1. ValidationRunner (Entry Point)

The single entry point for all test execution:

```python
# libs/python/corekinect/test/validation/runner.py

class ValidationRunner:
    """Unified test runner with preflight, execution, and reporting."""

    def __init__(self, stage: str, run_id: str):
        self.stage = stage
        self.run_id = run_id
        self.config = StageConfig.load(stage)
        self.preflight = PreflightChecker(self.config)
        self.reporter = RunReporter(run_id)

    def run(self) -> int:
        """Execute the full test run. Returns exit code."""
        try:
            # 1. Report start
            self.reporter.start()

            # 2. Preflight checks
            preflight = self.preflight.check_all()
            if not preflight.passed:
                self.reporter.fail_preflight(preflight)
                return 1

            # 3. Execute pytest
            exit_code = self._run_pytest()

            # 4. Collect artifacts
            self._collect_artifacts()

            # 5. Report finish
            self.reporter.finish(exit_code)

            return exit_code

        except Exception as e:
            self.reporter.fail_exception(e)
            return 1

        finally:
            self._cleanup()
```

### 2. Preflight Checker

Validates all dependencies before wasting time on doomed runs:

```python
class PreflightChecker:
    """Validates dependencies before test execution."""

    CHECKS = [
        ("mtib", "MTIB connectivity"),
        ("storage", "Disk space > 1GB"),
        ("corecloud", "CoreCloud API auth"),
        ("firmware", "Firmware artifacts available"),
        ("fixture", "Fixture profile valid"),
        ("device", "Device SNR configured"),
    ]

    def check_all(self) -> PreflightResult:
        results = []
        for check_id, description in self.CHECKS:
            method = getattr(self, f"_check_{check_id}")
            try:
                passed, message = method()
                results.append(CheckResult(check_id, description, passed, message))
            except Exception as e:
                results.append(CheckResult(check_id, description, False, str(e)))

        return PreflightResult(results)

    def _check_mtib(self) -> tuple[bool, str]:
        """Verify MTIB gRPC connection."""
        try:
            client = MtibV1Client(self.config.mtib_config)
            err = client.connect()
            if err:
                return False, f"Connection failed: {err}"

            health = client.HealthCheck()
            client.disconnect()

            if health.status != "SERVING":
                return False, f"Unhealthy: {health.status}"

            return True, f"Connected to {self.config.mtib_address}"
        except Exception as e:
            return False, str(e)

    def _check_storage(self) -> tuple[bool, str]:
        """Verify sufficient disk space for artifacts."""
        import shutil
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        if free_gb < 1.0:
            return False, f"Only {free_gb:.1f}GB free"
        return True, f"{free_gb:.1f}GB available"

    def _check_corecloud(self) -> tuple[bool, str]:
        """Verify CoreCloud API authentication."""
        if self.config.stage == "integration":
            return True, "Not required for integration tests"

        try:
            from corekinect.test.fuota_client import FuotaClient
            client = FuotaClient(api_env="VAL_1_0")
            # Simple API call to verify auth
            client._ensure_token()
            return True, "Authenticated"
        except Exception as e:
            return False, str(e)

    def _check_firmware(self) -> tuple[bool, str]:
        """Verify firmware artifacts are available."""
        if self.config.stage != "gate":
            return True, "Not required for this stage"

        pipeline_id = os.environ.get("PIPELINE_ID")
        if not pipeline_id:
            return False, "PIPELINE_ID not set"

        # TODO: Verify pipeline has successful builds
        return True, f"Pipeline {pipeline_id[:8]}..."

    def _check_fixture(self) -> tuple[bool, str]:
        """Verify fixture profile exists and is valid."""
        path = os.environ.get("FIXTURE_PROFILE_PATH")
        if not path:
            return False, "FIXTURE_PROFILE_PATH not set"

        if not os.path.exists(path):
            return False, f"File not found: {path}"

        try:
            with open(path) as f:
                profile = json.load(f)

            required = ["product", "board", "dut"]
            missing = [k for k in required if k not in profile]
            if missing:
                return False, f"Missing fields: {missing}"

            return True, f"{profile['product']}/{profile['board']}"
        except Exception as e:
            return False, str(e)

    def _check_device(self) -> tuple[bool, str]:
        """Verify device SNR is configured."""
        snr = os.environ.get("DEVICE_SNR")
        if not snr:
            return False, "DEVICE_SNR not set"
        return True, f"SNR: {snr}"
```

### 3. Stage Configuration

```python
@dataclass
class StageConfig:
    """Stage-specific configuration."""

    stage: str
    timeout_s: int
    retry_count: int
    test_path: str
    pytest_args: list[str]
    required_services: list[str]
    artifact_patterns: list[str]

    @classmethod
    def load(cls, stage: str) -> "StageConfig":
        configs = {
            "gate": cls(
                stage="gate",
                timeout_s=900,
                retry_count=0,
                test_path="tests/gate/",
                pytest_args=["-v", "--tb=short"],
                required_services=["mtib", "corecloud", "minio"],
                artifact_patterns=["*.log", "*.uart", "*.csv"],
            ),
            "regression": cls(
                stage="regression",
                timeout_s=3600,
                retry_count=1,
                test_path="tests/regression/",
                pytest_args=["-v", "--tb=long"],
                required_services=["mtib", "corecloud"],
                artifact_patterns=["*.log", "*.uart", "*.csv", "*.png"],
            ),
            "integration": cls(
                stage="integration",
                timeout_s=1800,
                retry_count=0,
                test_path="tests/integration/",
                pytest_args=["-v", "--tb=short"],
                required_services=["mtib"],
                artifact_patterns=["*.log", "*.uart"],
            ),
        }
        return configs[stage]
```

### 4. Result Reporter

Handles all result submission:

```python
class RunReporter:
    """Reports run progress and results to Concord API."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.api_url = os.environ.get("CONCORD_API_URL")
        self.api_key = os.environ.get("CONCORD_API_KEY")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"ApiKey {self.api_key}"

    def start(self):
        """Report run started."""
        self._post("/report/start", {"timestamp": datetime.utcnow().isoformat()})

    def fail_preflight(self, result: PreflightResult):
        """Report preflight failure."""
        self._post("/report/preflight-failed", {
            "checks": [
                {"id": c.id, "passed": c.passed, "message": c.message}
                for c in result.checks
            ]
        })

    def finish(self, exit_code: int):
        """Report run finished."""
        self._post("/report/finish", {
            "exitCode": exit_code,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def upload_artifact(self, path: str, name: str):
        """Upload artifact to MinIO via API."""
        with open(path, "rb") as f:
            self._post(f"/artifacts/{name}", files={"file": f})
```

### 5. Artifact Collection

```python
class ArtifactCollector:
    """Collects and uploads test artifacts."""

    def __init__(self, config: StageConfig, reporter: RunReporter):
        self.config = config
        self.reporter = reporter
        self.artifacts_dir = Path(os.environ.get("ARTIFACTS_DIR", "/tmp/artifacts"))

    def collect_all(self):
        """Collect all artifacts matching stage patterns."""
        for pattern in self.config.artifact_patterns:
            for path in self.artifacts_dir.glob(pattern):
                self.reporter.upload_artifact(str(path), path.name)
```

## Restart/Resume Handling

### Run States

```
PENDING → PREFLIGHT → RUNNING → COMPLETED
                  ↓         ↓
              PREFLIGHT_FAILED  FAILED
                              ↓
                          CANCELLED
```

### Resume Logic

```python
def can_resume(run: ValidationRun) -> bool:
    """Check if a failed run can be resumed."""
    # Only allow resume for certain failure modes
    if run.status == "PREFLIGHT_FAILED":
        return True  # Retry after fixing dependency

    if run.status == "FAILED":
        # Check if failure was transient (network, timeout)
        if run.error_message and "timeout" in run.error_message.lower():
            return True
        if run.error_message and "connection" in run.error_message.lower():
            return True

    return False

def resume_run(run_id: str) -> ValidationRun:
    """Resume a failed run from the last successful test."""
    run = db.validation_run.find_unique(where={"id": run_id})

    if not can_resume(run):
        raise ValueError(f"Run {run_id} cannot be resumed")

    # Find last successful test
    last_passed = db.validation_step.find_first(
        where={"runId": run_id, "status": "PASSED"},
        order_by={"createdAt": "desc"},
    )

    # Create new run with skip marker
    new_run = create_run(
        design_id=run.design_id,
        resume_from=last_passed.node_id if last_passed else None,
    )

    return new_run
```

## CLI Entry Point

```python
# apps/validation/alpha/run.py

#!/usr/bin/env python3
"""Validation test runner entry point."""

import sys
import os

from corekinect.test.runner import ValidationRunner

def main():
    stage = os.environ.get("STAGE", "gate")
    run_id = os.environ.get("CONCORD_RUN_ID")

    if not run_id:
        print("ERROR: CONCORD_RUN_ID not set")
        sys.exit(1)

    runner = ValidationRunner(stage=stage, run_id=run_id)
    exit_code = runner.run()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

## K8s Job Template

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: validation-{{ .runId }}
spec:
  backoffLimit: {{ .retryCount }}
  activeDeadlineSeconds: {{ .timeoutS }}
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: validation
          image: {{ .image }}
          command: ["python", "run.py"]
          env:
            - name: STAGE
              value: "{{ .stage }}"
            - name: CONCORD_RUN_ID
              value: "{{ .runId }}"
            - name: CONCORD_API_URL
              value: "{{ .apiUrl }}"
            - name: CONCORD_API_KEY
              valueFrom:
                secretKeyRef:
                  name: validation-secrets
                  key: api-key
            - name: MTIB_ADDRESS
              value: "{{ .mtibAddress }}"
            - name: DEVICE_SNR
              value: "{{ .deviceSnr }}"
            - name: FIXTURE_PROFILE_PATH
              value: "/config/fixture.json"
            - name: PIPELINE_ID
              value: "{{ .pipelineId }}"
          volumeMounts:
            - name: fixture-config
              mountPath: /config
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2"
      volumes:
        - name: fixture-config
          configMap:
            name: fixture-{{ .benchId }}
```

## Result Flow

```
1. Test executes
   └─► pytest captures result
       └─► ConcordReporter plugin
           └─► POST /v2/validation/runs/{id}/report/test-result
               └─► API stores in PostgreSQL (ValidationStep)
               └─► API emits WebSocket event
                   └─► Frontend updates live

2. Test finishes
   └─► ArtifactCollector scans for files
       └─► POST /v2/validation/runs/{id}/artifacts/{name}
           └─► API stores in MinIO
           └─► API updates ValidationStep.artifacts

3. Run completes
   └─► ValidationRunner.finish()
       └─► POST /v2/validation/runs/{id}/report/finish
           └─► API updates ValidationRun.status
           └─► API emits WebSocket event
           └─► (optional) Webhook to CI system
```

## Visualization by Stage

### Gate (PR blocking)
- GitHub-style: linear timeline, pass/fail per test
- Focus: speed, binary outcome
- Key metric: total time, FUOTA success

### Regression (comprehensive)
- Dashboard-style: grouped by category (power, sensors, GPS)
- Focus: trends over time, regression detection
- Key metrics: power budgets, sensor ranges, timing

### Integration (debugging)
- Log-heavy: full UART output, state traces
- Focus: internal state visibility
- Key metrics: state transitions, IPC timing

## Common Bug Handlers

```python
class BugHandler:
    """Handles known issues gracefully."""

    HANDLERS = {
        "uart_latency": UartLatencyHandler(),
        "shell_timeout": ShellTimeoutHandler(),
        "fuota_stuck": FuotaStuckHandler(),
        "power_spike": PowerSpikeHandler(),
    }

    @classmethod
    def handle(cls, error: Exception, context: dict) -> HandlerResult:
        """Try to handle a known error pattern."""
        error_str = str(error).lower()

        for name, handler in cls.HANDLERS.items():
            if handler.matches(error_str, context):
                return handler.handle(error, context)

        return HandlerResult(handled=False)

class UartLatencyHandler:
    """Handles MTIB UART byte-by-byte latency issue."""

    def matches(self, error: str, ctx: dict) -> bool:
        return "timeout" in error and "uart" in error

    def handle(self, error: Exception, ctx: dict) -> HandlerResult:
        # Extend timeout and retry
        return HandlerResult(
            handled=True,
            action="retry",
            message="UART latency detected, extending timeout",
            new_timeout=ctx.get("timeout", 30) * 3,
        )
```

## Next Steps

1. Implement `ValidationRunner` in `libs/python/corekinect/test/validation/runner.py`
2. Implement `PreflightChecker`
3. Update K8s Job template to use `run.py` entry point
4. Add preflight endpoint to API for UI display
5. Add resume capability to API and frontend
