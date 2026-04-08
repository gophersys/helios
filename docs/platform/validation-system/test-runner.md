---
min_role: DEVELOPER
---
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
# libs/python/corekinect/test/runner.py

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

1. Implement `ValidationRunner` in `libs/python/corekinect/test/runner.py`
2. Implement `PreflightChecker`
3. Update K8s Job template to use `run.py` entry point
4. Add preflight endpoint to API for UI display
5. Add resume capability to API and frontend

---

# Part 2: Test Execution Stack


> How Stage 3 and Stage 4 test cases are built on top of the CoreCloud abstraction,
> the MTIB V2 server, and the Concord test runner system. Maps existing code to
> documented architecture, identifies gaps, and resolves open design questions.

---

## 1. Purpose

The validation architecture documents describe a test system with many moving parts: MTIB V2 gRPC servers, a CoreCloud Python SDK, Zephyr shell commands, fixture controllers, UART demuxers, harness transports, and K8s-orchestrated test pods. This document answers one question:

**How does a single PRD test case — like "PRDTST-324: Motion detection threshold" — flow from the test spec, through Python test code, down to physical hardware actions and backend verification?**

The answer reveals three clean layers, a composition pattern (TestContext), and a clear map of what exists today vs what needs to be built.

---

## 2. The Stack

Every Stage 3 and Stage 4 test case flows through the same layered architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│  PRD Test Cases (PRDTST-xxx)                                    │
│  "Motion threshold triggers position message within 30s"        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ defined in
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Test Spec (validation_spec/*.yaml)                             │
│  acceptance criteria, fixture requirements, tags, timeouts      │
└─────────────────────────────┬───────────────────────────────────┘
                              │ executed by
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Test Function (tests/test_motion.py::test_motion_threshold)    │
│  Python async function, receives TestContext                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TestContext (ctx)                                               │
│  Composes all three pillars into a unified API                  │
│                                                                 │
│  ctx.mtib     → MTIB V2 client (hardware control)               │
│  ctx.cloud    → CloudClient (backend verification)              │
│  ctx.fixture  → FixtureController (physical stimulus)           │
│  ctx.uart     → UartDemuxer (UART capture + routing)            │
│  ctx.harness  → HarnessTransport (Stage 3 only)                │
│  ctx.logs     → LogAccess (device log queries)                  │
│  ctx.power    → PowerProfiler (measurement + traces)            │
└────────┬───────────────┬──────────────────┬─────────────────────┘
         │               │                  │
         ▼               ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐
│  CloudClient │ │  MtibV2Client│ │  FixtureController  │
│              │ │              │ │                     │
│  CoreCloud   │ │  71 gRPC     │ │  Fixture Profile    │
│  DB + REST   │ │  RPCs        │ │  JSON → pin mapping │
└──────┬───────┘ └──────┬───────┘ └──────────┬──────────┘
       │                │                     │
       ▼                ▼                     ▼
┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐
│  PostgreSQL  │ │  MTIB V2     │ │  MTIB GPIO/Motor/   │
│  (CoreCloud) │ │  Server      │ │  ADC/Peltier        │
│  REST API    │ │  (Verdin)    │ │  (physical pins)    │
└──────────────┘ └──────────────┘ └─────────────────────┘
```

The critical insight: **the three pillars are independent**. A test that only checks power draw uses `ctx.mtib` and `ctx.power` — no CoreCloud needed. A test that checks backend message format uses `ctx.cloud` — no fixture actions needed. A FUOTA test uses all three. The TestContext doesn't force coupling between pillars; it makes them available.

---

## 3. Layer 1: MTIB V2 — The Hardware Interface

### What Exists Today (Code)

The MTIB V2 client is **fully implemented and production-tested** in manufacturing:

| Component | Location | Status |
|-----------|----------|--------|
| MTIB V2 Server | `apps/edge/mtib-server-v2/src/` | Production (71 RPCs, 17 handlers) |
| Python Client | `libs/python/corekinect/mtib_client/v2/` | Production (mixin architecture) |
| Shell Helper | `libs/python/corekinect/mtib_client/v2/client/shell.py` | Production (persistent UART, boot_and_lock_shells) |
| Command Wrappers | `libs/python/corekinect/mtib_client/v2/client/cmd_*.py` | Production (AlphaAppShellCommands, CommsShellCommands) |
| Mock Server | `libs/python/corekinect/mtib_client/v2/tests/mock_server.py` | Exists (for unit tests) |

### How Manufacturing Uses MTIB Today

Manufacturing tests use the MTIB V2 client directly via `MtibV2Client`:

```python
# From apps/manufacturing/alpha/src/tests/post/step_0.py (actual production code)

client = MtibV2Client(ClientConfig(net=NetConfig(addr=node, port=50052)))
error = client.connect()

# Power control
client.power_enable(channel=0, voltage_v=4.5)    # Battery sim at 4.5V (BQ25180 UVLO)
client.power_enable(channel=1)                     # Charger/USB at 5V

# GPIO for SWD level shifter
client.gpio_config(pin=0, direction=1)             # Output mode
client.gpio_write(pin=0, value=False)

# Flash firmware via J-Link
err, session = client.debug_connect(target_id="nrf52840", probe_id="")
err, result = client.flash_program(
    session_id=session.session_id,
    filename="alpha_app_prod_8.hex",
    erase_before=True, verify_after=True, reset_after=True
)

# Persistent UART shells
app_shell, comms_shell, err = boot_and_lock_shells(client, app_port="uart1", comms_port="uart0")
response, err = app_shell.send_command("post", timeout=30)
```

### What the Test Runner Needs From MTIB

The validation test runner needs the **exact same RPCs** that manufacturing uses, plus a few additions:

| RPC Category | Manufacturing Uses | Validation Also Needs | Status |
|-------------|-------------------|----------------------|--------|
| Power enable/disable | Yes (4.5V battery, 5V charger) | Same | Exists |
| Power measurement | Minimal (current check) | Continuous sampling (`PowerStream`, `PowerMeasure`) | Exists in MTIB, unused by mfg |
| Flash programming | Yes (J-Link SWD) | Same, plus `--recover` before flash | Exists |
| UART streaming | Yes (persistent shells) | Same, plus UartDemuxer prefix routing | UART exists; demuxer is new |
| GPIO control | Yes (SWD level shifter) | Same, plus button, on-skin, charger relay, peltier | Same RPCs, different pin assignments |
| Motor control | No | Yes (linear actuator for motion tests) | Exists in MTIB, unused by mfg |
| ADC reads | Yes (voltage test points) | Yes (photodiode LED reads, thermistor) | Exists |
| BLE | No | Possible future (BLE advertising tests) | Exists in MTIB |
| I2C | No | Yes (NFC reader via I2C) | Exists in MTIB |

**Key takeaway**: The MTIB V2 layer is complete. The validation test runner doesn't need new RPCs — it needs a **composition layer** (FixtureController) that maps abstract test actions to the right MTIB RPCs with the right pin numbers.

---

## 4. Layer 2: CoreCloud SDK — The Backend Interface

### What Exists Today (Code)

The CoreCloud SDK is **implemented and working** for DB reads and limited REST writes:

| Component | Location | Status |
|-----------|----------|--------|
| DB Interface | `libs/python/corekinect/core_cloud/db_interface.py` | Production (PostgreSQL + SSH tunnel) |
| REST Interface | `libs/python/corekinect/core_cloud/api_interface.py` | Production (token auth, rate limiting) |
| v1.0 Message Defs | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` | Production (10+ message classes) |
| v1.0 ORM | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` | Production (includes FUOTA tables) |

### Message Classes Available for Validation

| Message Class | UID | Base | DB Read | REST Send | Used By Stage 4 Tests |
|--------------|-----|------|---------|-----------|----------------------|
| `BootMsgV2` | 548 | `MsgBase` | `.last()`, `.since_*()` | No | FUOTA (boot reason, FW version) |
| `PositionMsgV6` | 556 | `MsgBase` | `.last()`, `.since_*()` | No | Motion, power, GNSS, config |
| `BiometricDataMsg` | 557 | `MsgBase` | `.last()`, `.since_*()` | No | On-skin, biometrics |
| `NetworkStatusMsgV4` | 512 | `MsgBase` | `.last()`, `.since_*()` | No | LTE diagnostics |
| `AlphaHwFailureMsg` | 559 | `MsgBase` | `.last()`, `.since_*()` | No | Hardware failure detection |
| `GPSConfMsg` | 524 | `ConfMsgBase` | `.last()`, `.since_*()` | `.send_via_rest()` | GNSS config delivery |
| `GroundModeConfigV2` | 538 | `MsgBase` | `.last()`, `.since_*()` | **No** (not ConfMsgBase) | Config value tests (18 deferred) |
| `DeviceMessageLog` | — | `MsgBase` | `.last()`, `.since_*()` | No | Generic message audit |

### The Query Pattern

All message reads follow the same pattern (from the SDK):

```python
from corekinect.core_cloud.msg_def_v1_0 import PositionMsgV6, BootMsgV2

# Get the most recent position message for a device
msg = PositionMsgV6.last(dut_id=12345, db_env="VAL_1_0")
# Returns: PositionMsgV6(device_id=12345, latitude=37.7749, longitude=-122.4194,
#          update_reason=3, is_in_motion=True, batt_percent=85, ...)

# Get all position messages since a timestamp
msgs = PositionMsgV6.since_server_time(
    dut_id=12345,
    start_time=test_start_time,
    db_env="VAL_1_0"
)

# Get boot messages since a record ID (for FUOTA verification)
boots = BootMsgV2.since_record_id(
    dut_id=12345,
    start_record_id=last_known_record_id,
    db_env="VAL_1_0"
)
# Check boot reason: boots[0].boot_reason_bits → "Reboot due to completing FUOTA"
```

### What CloudClient Needs to Add

The raw SDK is usable directly, but Stage 4 tests need polling-with-timeout wrappers and FUOTA plan management. This is what `CloudClient` provides on top of the SDK:

```python
class CloudClient:
    """Thin wrapper over CoreCloud SDK with polling helpers and FUOTA support."""

    def __init__(self, device_id: int, db_env: str = "VAL_1_0"):
        self.device_id = device_id
        self.db_env = db_env
        self._test_start_time = None

    def mark_test_start(self):
        """Record timestamp. All subsequent queries filter to 'since test start'."""
        self._test_start_time = datetime.now(timezone.utc)

    # ── Polling Wrappers ──────────────────────────────────────────────

    def wait_for_position(self, timeout_s: float = 120, poll_interval_s: float = 5,
                          **field_filters) -> Optional[PositionMsgV6]:
        """Poll until a PositionMsgV6 arrives since test start, optionally matching field values."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            msgs = PositionMsgV6.since_server_time(
                self.device_id, self._test_start_time, db_env=self.db_env
            )
            for msg in msgs:
                if all(getattr(msg, k) == v for k, v in field_filters.items()):
                    return msg
            time.sleep(poll_interval_s)
        return None

    def wait_for_boot(self, timeout_s: float = 180, poll_interval_s: float = 10,
                      **field_filters) -> Optional[BootMsgV2]:
        """Poll until a BootMsgV2 arrives. Used after FUOTA and power cycles."""
        # Same polling pattern as wait_for_position
        ...

    def wait_for_biometric(self, timeout_s: float = 120, poll_interval_s: float = 5,
                           **field_filters) -> Optional[BiometricDataMsg]:
        ...

    # ── Config Delivery ───────────────────────────────────────────────

    def push_gps_config(self, config: GPSConfMsg) -> bool:
        """Send GPS configuration via CoreCloud REST API."""
        resp = config.send_via_rest(
            device_id=self.device_id,
            env_namespace=self.db_env
        )
        return resp.status_code == 200

    # ── FUOTA (proposed, not yet implemented) ─────────────────────────

    def create_fuota_plan(self, firmware_build_id: int, target_device_ids: list[int],
                          stages: int = 1) -> int:
        """Create a FUOTA plan via CoreCloud DB ORM. Returns plan ID."""
        # Uses Fuotaplanstbl ORM model directly
        ...

    def wait_for_fuota_completion(self, plan_id: int, timeout_s: float = 600,
                                  poll_interval_s: float = 30) -> bool:
        """Poll Fuotaprogresshistorytbl until all targets complete."""
        ...
```

**What exists vs what's new**:

| CloudClient Method | Underlying SDK | Exists in SDK? | New Code Needed? |
|-------------------|---------------|----------------|-----------------|
| `wait_for_position()` | `PositionMsgV6.since_server_time()` | Yes | Polling wrapper only |
| `wait_for_boot()` | `BootMsgV2.since_server_time()` | Yes | Polling wrapper only |
| `wait_for_biometric()` | `BiometricDataMsg.since_server_time()` | Yes | Polling wrapper only |
| `push_gps_config()` | `GPSConfMsg.send_via_rest()` | Yes | Thin wrapper only |
| `create_fuota_plan()` | `Fuotaplanstbl` ORM model | ORM table exists | Plan builder logic new |
| `wait_for_fuota_completion()` | `Fuotaprogresshistorytbl` ORM model | ORM table exists | Polling logic new |

**The FUOTA gap**: The ORM tables for FUOTA plans exist in `db_orm_v1_0.py` (`Fuotaplanstbl`, `Fuotaprogresshistorytbl`, `Fuotasettingsperdevicetypetbl`), but no Python code creates or monitors plans. The CoreCloud backend team may have a REST API for FUOTA plan management — if so, CloudClient should use REST rather than writing to the DB directly. This is an open question (see Section 10).

---

## 5. Layer 3: Test Runner Framework — The Orchestration Layer

### What Exists Today (Code)

The manufacturing test framework provides a proven execution model:

| Component | Location | Status |
|-----------|----------|--------|
| TestStep base | `libs/python/corekinect/test/step/` | Production |
| Test container | `apps/manufacturing/alpha/src/tests/lib.py` | Production |
| Config pattern | `apps/manufacturing/alpha/src/tests/shared/config.py` | Production (ThetaFixtureConfig) |
| gRPC operator | `deploy/manufacturing/sigma5/operator-deployment.yaml` | Production |
| K8s deployment | `deploy/manufacturing/sigma5/deployment.yaml` | Production |

### The Manufacturing Pattern (Proven)

Manufacturing tests follow a clear pattern that validation can adapt:

```python
# 1. Config dataclass — all tunable parameters
@dataclass
class ThetaFixtureConfig:
    electrical_uvlo_voltage_v: float = 3.4
    fw_flash_nrf52840_app_fw_name: str = "alpha_app_prod_8.hex"
    post_expected_num_sims: int = 2
    # ... 80+ configurable thresholds

# 2. Shared data per node — persistent state across steps
class PostTestSharedData:
    client: Optional[MtibV2Client] = None
    app_shell: Optional[ShellCommandHelper] = None
    comms_shell: Optional[CommsShellCommands] = None

# 3. Step handler — receives config, node, shared data; returns result
def step_handler(config: ThetaFixtureConfig, node: str, usr_data: dict) -> TestStepResult:
    result = TestStepResult(success=False)
    client = usr_data[node].client
    error = client.power_enable(channel=0, voltage_v=config.electrical_uvlo_voltage_v)
    if error:
        result.error = error
        return result
    result.success = True
    return result

# 4. Test assembly — steps run in sequence, nodes run in parallel
test = Test(
    steps=[step1, step2, step3, ...],
    init_func=init_nodes,       # Parallel MTIB connection setup
    deinit_func=deinit_nodes,   # Parallel cleanup
    config_type=ThetaFixtureConfig,
)
```

### What Changes for Validation

The manufacturing pattern is solid but validation needs three additions:

| Manufacturing Has | Validation Needs | Gap |
|-------------------|-----------------|-----|
| `MtibV2Client` directly | `TestContext` composing MTIB + Cloud + Fixture | New composition layer |
| `ThetaFixtureConfig` (fixed dataclass) | Fixture profile JSON (per-product, per-MTIB-node) | New fixture abstraction |
| `TestStepResult` (pass/fail + details) | Same, plus power trace artifacts, UART logs, backend message snapshots | Artifact collection |
| gRPC operator dispatches tests | K8s Job controller dispatches tests | New orchestration model |
| Parallel execution across MTIB nodes | Single DUT per test pod (one node per K8s Job) | Simpler execution model |
| No CoreCloud interaction | CoreCloud polling, config delivery, FUOTA plans | CloudClient integration |

### The Key Architectural Difference

Manufacturing runs **multiple devices in parallel** on multiple MTIB nodes from a single test runner pod. The operator dispatches to runners, each runner runs steps across N nodes via ThreadPoolExecutor.

Validation runs **one device per K8s Job**. The pipeline controller creates a Job for each (product, stage, MTIB-node) tuple. The Job pod connects to exactly one MTIB node. No multi-node parallelism inside the pod — parallelism comes from multiple Jobs running simultaneously on different nodes.

This simplifies the validation test runner significantly: no `usr_data[node]` lookup, no ThreadPoolExecutor fan-out, no node removal on failure. The TestContext owns one MTIB connection, one CloudClient, one fixture profile.

---

## 6. The Bridge: TestContext

TestContext is the composition layer that unifies the three pillars into a single API for test functions. It's described in `stage4-product-tests.md` Section 6 and `stage3-integration-tests.md` Section 4, but doesn't exist as code yet.

### TestContext API (Stage 4)

```python
class TestContext:
    """Injected into every test function. One per test pod."""

    # ── Pillars (initialized from env vars + fixture profile) ──────

    mtib: MtibV2Client          # Direct MTIB V2 gRPC client
    cloud: CloudClient          # CoreCloud polling + config delivery
    fixture: FixtureController  # Abstract actions → physical pins
    uart: UartDemuxer           # Prefix-routed UART streams
    power: PowerProfiler        # Power measurement + trace storage
    logs: LogAccess             # Device log queries (from UART capture)

    # ── Stage 3 Only ──────────────────────────────────────────────

    harness: HarnessTransport   # concord_harness getter/setter/inject/event

    # ── Lifecycle ─────────────────────────────────────────────────

    device_id: int              # CoreCloud device ID (from env)
    firmware_hex: str           # Path to firmware artifact (from env / MinIO)
    product: str                # "alpha", "sigma5" (from env)
    build_variant: str          # "debug", "release" (from env)

    # ── Convenience Methods ───────────────────────────────────────

    async def flash_firmware(self, hex_path: str = None):
        """Flash firmware via J-Link. Defaults to self.firmware_hex."""
        hex_path = hex_path or self.firmware_hex
        err = self.mtib.power_disable(channel=0)
        err = self.mtib.power_disable(channel=1)
        await asyncio.sleep(0.5)
        err, session = self.mtib.debug_connect(target_id="nrf52840", probe_id="auto")
        err, result = self.mtib.flash_program(
            session_id=session.session_id,
            filename=hex_path,
            erase_before=True, verify_after=True, reset_after=False
        )
        self.mtib.debug_disconnect(session.session_id)

    async def power_on(self, voltage_v: float = 4.5):
        """Power DUT at specified voltage and wait for boot."""
        self.cloud.mark_test_start()
        self.uart.start_capture()
        self.mtib.power_enable(channel=0, voltage_v=voltage_v)
        await asyncio.sleep(3)  # Boot settle time

    async def power_off(self):
        """Power off DUT and stop UART capture."""
        self.uart.stop_capture()
        self.mtib.power_disable(channel=0)
        self.mtib.power_disable(channel=1)

    async def wait_for_boot(self, timeout_s: float = 30):
        """Wait for BootMsgV2 in CoreCloud confirming device booted."""
        boot = self.cloud.wait_for_boot(timeout_s=timeout_s)
        if not boot:
            raise TimeoutError(f"No BootMsgV2 within {timeout_s}s")
        return boot
```

### How TestContext Gets Initialized

The validation runner creates TestContext from environment variables injected by the K8s Job:

```python
# validation_runner.py (initialization, not yet implemented)

def create_test_context() -> TestContext:
    ctx = TestContext()

    # MTIB connection (from K8s Job env)
    mtib_host = os.environ["MTIB_HOST"]        # e.g., "10.4.45.33"
    mtib_port = int(os.environ.get("MTIB_PORT", "50052"))
    ctx.mtib = MtibV2Client(ClientConfig(net=NetConfig(addr=mtib_host, port=mtib_port)))
    ctx.mtib.connect()

    # CoreCloud (from Vault-injected env vars)
    device_id = int(os.environ["DEVICE_ID"])
    db_env = os.environ.get("CLOUD_ENV_NAMESPACE", "VAL_1_0")
    ctx.cloud = CloudClient(device_id=device_id, db_env=db_env)
    ctx.device_id = device_id

    # Fixture profile (from Concord DB, injected as JSON env or mounted file)
    fixture_json = os.environ.get("FIXTURE_PROFILE_PATH", "/etc/concord/fixture.json")
    ctx.fixture = FixtureController(ctx.mtib, fixture_json)

    # UART demuxer (routes prefixed lines to harness vs logs)
    ctx.uart = UartDemuxer(ctx.mtib)

    # Power profiler (wraps MTIB power measurement RPCs)
    ctx.power = PowerProfiler(ctx.mtib)

    # Log access (reads from UART capture buffer)
    ctx.logs = LogAccess(ctx.uart)

    # Firmware artifact (downloaded from MinIO by the runner before test start)
    ctx.firmware_hex = os.environ.get("FIRMWARE_HEX_PATH", "/tmp/firmware.hex")
    ctx.product = os.environ["PRODUCT"]
    ctx.build_variant = os.environ.get("BUILD_VARIANT", "release")

    return ctx
```

### How TestContext Maps to Manufacturing Patterns

| Manufacturing Pattern | TestContext Equivalent | Adaptation |
|----------------------|----------------------|------------|
| `MtibV2Client` in `usr_data[node].client` | `ctx.mtib` | Direct reference, no node lookup |
| `boot_and_lock_shells()` | `ctx.uart.open_shell("nrf52840")` | UartDemuxer wraps shell creation |
| `ThetaFixtureConfig.electrical_uvlo_voltage_v` | `ctx.fixture.profile["power"]["dut_voltage"]` | Fixture profile replaces config fields |
| `mtib_servers.enable_power(node, 4.5)` | `ctx.mtib.power_enable(channel=0, voltage_v=4.5)` | Direct MtibV2Client call |
| `response, err = shell.send_command("post")` | `ctx.uart.shell("nrf52840").send_command("post")` | Via UartDemuxer |
| No CoreCloud | `ctx.cloud.wait_for_position(...)` | New pillar |
| No fixture abstraction | `ctx.fixture.button.press()` | New abstraction layer |

---

## 7. FixtureController: Translating Abstract Actions to Hardware

FixtureController is the layer that decouples test logic from physical wiring. Without it, every test would contain raw GPIO pin numbers.

### The Problem

```python
# WITHOUT FixtureController (brittle, hardware-specific)
ctx.mtib.gpio_write(pin=0, value=True)   # What does pin 0 do? Button? On-skin? Charger?
await asyncio.sleep(0.1)
ctx.mtib.gpio_write(pin=0, value=False)
```

### The Solution

```python
# WITH FixtureController (self-documenting, portable)
await ctx.fixture.button.press(duration_s=0.1)
```

### Fixture Profile JSON

Each MTIB node has a fixture profile stored in Concord's database (Node model, `fixtureProfile` field). The profile maps abstract actions to physical pin assignments:

```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "revision": "1.2",
  "power": {
    "dut_channel": 0,
    "dut_voltage_v": 4.5,
    "charger_channel": 1,
    "charger_voltage_v": 5.0,
    "boot_settle_s": 3
  },
  "button": {
    "gpio_pin": 0,
    "active_low": true,
    "debounce_ms": 50
  },
  "on_skin": {
    "gpio_pin": 1,
    "active_high": true
  },
  "charger_relay": {
    "gpio_pin": 5,
    "active_high": true
  },
  "peltier": {
    "enable_gpio_pin": 3,
    "sensor_adc_channel": 2,
    "pid": { "kp": 2.0, "ki": 0.5, "kd": 0.1 }
  },
  "led_sensor": {
    "red_adc_channel": 0,
    "green_adc_channel": 1,
    "blue_adc_channel": 3
  },
  "nfc_reader": {
    "interface": "i2c",
    "bus": 1,
    "address": 85
  },
  "motion": {
    "type": "linear_actuator",
    "motor_channel": 0
  },
  "uart": {
    "app_port": "uart1",
    "comms_port": "uart0"
  },
  "swd": {
    "target_ids": ["nrf52840", "nrf9151"],
    "speed_khz": 4000
  }
}
```

### FixtureController Implementation

```python
class FixtureController:
    """Maps abstract fixture actions to MTIB RPCs via fixture profile."""

    def __init__(self, mtib: MtibV2Client, profile_path: str):
        with open(profile_path) as f:
            self.profile = json.load(f)
        self.mtib = mtib
        self.button = ButtonController(mtib, self.profile.get("button", {}))
        self.on_skin = ContactController(mtib, self.profile.get("on_skin", {}))
        self.charger = RelayController(mtib, self.profile.get("charger_relay", {}))
        self.peltier = PeltierController(mtib, self.profile.get("peltier", {}))
        self.led = LedSensorController(mtib, self.profile.get("led_sensor", {}))
        self.motion = MotionController(mtib, self.profile.get("motion", {}))

class ButtonController:
    def __init__(self, mtib: MtibV2Client, config: dict):
        self.mtib = mtib
        self.pin = config["gpio_pin"]
        self.active_low = config.get("active_low", True)
        self.debounce_ms = config.get("debounce_ms", 50)

    async def press(self, duration_s: float = 0.1):
        """Simulate button press for given duration."""
        active = not self.active_low   # active_low: press = LOW
        self.mtib.gpio_write(pin=self.pin, value=active)
        await asyncio.sleep(duration_s)
        self.mtib.gpio_write(pin=self.pin, value=not active)
        await asyncio.sleep(self.debounce_ms / 1000)

    async def long_press(self, duration_s: float = 3.0):
        """Simulate long button press (e.g., for SOS trigger)."""
        await self.press(duration_s=duration_s)

class ContactController:
    def __init__(self, mtib: MtibV2Client, config: dict):
        self.mtib = mtib
        self.pin = config["gpio_pin"]
        self.active_high = config.get("active_high", True)

    async def enable(self):
        """Simulate skin contact (enable electrode)."""
        self.mtib.gpio_write(pin=self.pin, value=self.active_high)

    async def disable(self):
        """Remove skin contact simulation."""
        self.mtib.gpio_write(pin=self.pin, value=not self.active_high)
```

### Why This Matters

The same test code works on any MTIB node with the right fixture profile:
- Different MTIB revisions (1.1 vs 1.2) have different GPIO expanders → different pin numbers
- Different products (Alpha vs Sigma5) have different fixture layouts
- Future fixture revisions can change pin assignments without changing test code
- The fixture profile is the **contract** between test code and physical hardware

---

## 8. Concrete Walk-throughs: PRD Test → Code → Infrastructure

### Example 1: PRDTST-331 — Sleep Current (Power-Only Test)

**What the PRD says**: "Device sleep current must be <50µA after 60s of inactivity."

**Layers touched**: MTIB only (power measurement). No CoreCloud, no fixture actions.

```python
# tests/test_power.py

async def test_sleep_current(ctx: TestContext):
    """PRDTST-331: Verify device sleep current is within budget."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await asyncio.sleep(60)  # Wait for device to enter sleep

    # Measure power for 10 seconds
    trace = ctx.power.measure(channel=0, duration_s=10)

    assert trace.avg_ua < 50, f"Sleep current {trace.avg_ua}µA exceeds 50µA budget"

    # Store power trace as artifact
    ctx.power.save_trace(trace, "sleep_current")
    await ctx.power_off()
```

**Infrastructure flow**:
```
test_sleep_current()
    → ctx.flash_firmware()
        → ctx.mtib.debug_connect("nrf52840")
        → ctx.mtib.flash_program("alpha_release.hex")
    → ctx.power_on()
        → ctx.mtib.power_enable(channel=0, voltage_v=4.5)
    → ctx.power.measure(channel=0, duration_s=10)
        → ctx.mtib.power_measure(channel=0, duration_s=10)
        → Returns PowerMeasurement(avg_ua=32.1, min_ua=28.5, max_ua=41.2)
    → ctx.power.save_trace(trace, "sleep_current")
        → Upload to MinIO: validation/pipelines/{id}/stages/4/artifacts/sleep_current.json
```

### Example 2: PRDTST-324 — Motion Detection Threshold (MTIB + CoreCloud)

**What the PRD says**: "Device must detect motion within 5s of continuous motion start and send a position message with `is_in_motion=True` within 30s."

**Layers touched**: MTIB (motor control) + CoreCloud (position message verification).

```python
# tests/test_motion.py

async def test_motion_threshold(ctx: TestContext):
    """PRDTST-324: Motion detection triggers position message."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Start continuous motion via fixture linear actuator
    await ctx.fixture.motion.start(speed_mm_s=15, distance_mm=10)

    # Wait for position message with is_in_motion=True
    msg = ctx.cloud.wait_for_position(
        timeout_s=30,
        poll_interval_s=3,
        is_in_motion=True
    )

    await ctx.fixture.motion.stop()
    assert msg is not None, "No motion-triggered position message within 30s"
    assert msg.flags_update_reason == 3, f"Expected motion update reason (3), got {msg.flags_update_reason}"
    await ctx.power_off()
```

**Infrastructure flow**:
```
test_motion_threshold()
    → ctx.flash_firmware() + ctx.power_on() + ctx.wait_for_boot()
        → [same as Example 1]
        → ctx.cloud.wait_for_boot() → polls BootMsgV2.since_server_time()
    → ctx.fixture.motion.start(speed_mm_s=15)
        → ctx.mtib.motor_output(channel=0, speed=15, distance=10)   [MTIB gRPC]
    → ctx.cloud.wait_for_position(is_in_motion=True)
        → loop: PositionMsgV6.since_server_time(device_id, test_start)  [CoreCloud DB]
        → filter: msg.is_in_motion == True
        → Returns PositionMsgV6 or None after timeout
    → ctx.fixture.motion.stop()
        → ctx.mtib.motor_stop(channel=0)
```

### Example 3: PRDTST-327 — On-Skin Biometric Detection (Fixture + CoreCloud)

**What the PRD says**: "When skin contact is detected, device must begin biometric monitoring and send a BiometricDataMsg with heart_rate > 0 within 60s."

**Layers touched**: MTIB (GPIO for on-skin electrode) + CoreCloud (biometric message verification).

```python
# tests/test_biometric.py

async def test_on_skin_biometric(ctx: TestContext):
    """PRDTST-327: On-skin detection triggers biometric monitoring."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Simulate skin contact via electrode
    await ctx.fixture.on_skin.enable()

    # Wait for biometric message with valid heart rate
    msg = ctx.cloud.wait_for_biometric(timeout_s=60, poll_interval_s=5)

    await ctx.fixture.on_skin.disable()

    assert msg is not None, "No BiometricDataMsg within 60s of skin contact"
    assert msg.heart_rate > 0, f"Heart rate is {msg.heart_rate}, expected > 0"
    assert msg.spo2 > 0, f"SpO2 is {msg.spo2}, expected > 0"
    await ctx.power_off()
```

**Infrastructure flow**:
```
test_on_skin_biometric()
    → ctx.fixture.on_skin.enable()
        → FixtureController.on_skin.enable()
            → ctx.mtib.gpio_write(pin=1, value=True)   [from fixture profile: on_skin.gpio_pin=1]
    → ctx.cloud.wait_for_biometric(timeout_s=60)
        → loop: BiometricDataMsg.since_server_time(device_id, test_start)  [CoreCloud DB]
        → Returns BiometricDataMsg(heart_rate=72, spo2=98, skin_temperature=33.2, ...)
```

### Example 4: PRDTST-376 — FUOTA Firmware Update (All Layers)

**What the PRD says**: "Device must accept and apply a firmware update via OTA. After update, device must boot with new firmware version and resume normal operation."

**Layers touched**: MTIB (flash mfg FW, power, UART) + CoreCloud (FUOTA plan + boot/position/biometric verification).

```python
# tests/test_fuota.py

async def test_fuota_mfg_to_release(ctx: TestContext):
    """PRDTST-376: FUOTA from manufacturing FW to production release."""

    # Step 1: Flash manufacturing firmware as baseline
    await ctx.flash_firmware(hex_path=ctx.mfg_firmware_hex)
    await ctx.power_on()
    boot = await ctx.wait_for_boot(timeout_s=60)
    assert boot is not None, "Device did not boot on mfg firmware"

    # Step 2: Create FUOTA plan targeting this device
    plan_id = ctx.cloud.create_fuota_plan(
        firmware_build_id=ctx.release_firmware_build_id,
        target_device_ids=[ctx.device_id],
        stages=1
    )
    assert plan_id is not None, "Failed to create FUOTA plan"

    # Step 3: Wait for FUOTA completion (device downloads + applies update)
    completed = ctx.cloud.wait_for_fuota_completion(
        plan_id=plan_id,
        timeout_s=600  # 10 minutes for download + apply
    )
    assert completed, f"FUOTA plan {plan_id} did not complete within 10 minutes"

    # Step 4: Wait 5 minutes (FUOTA cooldown) + verify new boot
    await asyncio.sleep(300)  # 5-minute cooldown between FUOTA completions
    ctx.cloud.mark_test_start()  # Reset timestamp for post-FUOTA checks

    boot = ctx.cloud.wait_for_boot(timeout_s=180)
    assert boot is not None, "No BootMsgV2 after FUOTA completion"
    assert boot.boot_reason_bits == 2, "Expected FUOTA boot reason (2)"

    # Step 5: Verify device resumes normal operation
    pos = ctx.cloud.wait_for_position(timeout_s=120)
    assert pos is not None, "No position message after FUOTA"

    bio = ctx.cloud.wait_for_biometric(timeout_s=120)
    # Biometric may be None if not on-skin — that's OK for FUOTA test

    net = ctx.cloud.wait_for_network_status(timeout_s=120)
    assert net is not None, "No network status after FUOTA"
    assert net.did_lte_conn, "LTE not connected after FUOTA"

    await ctx.power_off()
```

### Example 5: Stage 3 — Integration Test with Harness (Internal Visibility)

**What the test checks**: "When skin contact is detected, app state machine transitions from `off_body_e` to `low_heat_risk_e`."

**Layers touched**: MTIB (power, UART) + Harness (state observation + event injection). No CoreCloud — Stage 3 uses the harness for verification, not the backend.

```python
# alpha_fw/.concord/tests/integration/test_state_machine.py

async def test_skin_contact_transition(ctx: TestContext):
    """Verify state transition on skin contact via concord_harness."""
    await ctx.flash_firmware()  # Instrumented build: CONFIG_CONCORD_HARNESS=y
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Verify initial state via harness getter
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e"

    # Inject skin contact event (can't physically trigger in all fixtures)
    await ctx.harness.inject("sensor.touch", "detected")

    # Wait for state change event
    evt = await ctx.harness.wait_event("app.state_changed", timeout_s=10)
    assert evt.value == "low_heat_risk_e"

    # Verify via getter too
    state = await ctx.harness.get("app.state")
    assert state == "low_heat_risk_e"

    await ctx.power_off()
```

**Infrastructure flow**:
```
test_skin_contact_transition()
    → ctx.harness.get("app.state")
        → ctx.uart.shell("nrf52840").send_command("concord get app.state")  [UART]
        → Parse response: "app.state=off_body_e"
        → Returns "off_body_e"
    → ctx.harness.inject("sensor.touch", "detected")
        → ctx.uart.shell("nrf52840").send_command("concord inject sensor.touch detected")
    → ctx.harness.wait_event("app.state_changed", timeout_s=10)
        → UART demuxer filters lines with "[CONCORD:EVT]" prefix
        → Parses: "[CONCORD:EVT] app.state_changed=low_heat_risk_e"
        → Returns HarnessEvent(name="app.state_changed", value="low_heat_risk_e")
```

**Key difference from Stage 4**: Stage 3 uses `ctx.harness.*` for internal state observation. Stage 4 uses `ctx.cloud.*` for external verification. Same MTIB, same power control, different verification mechanism.

---

## 9. Stage 3 vs Stage 4: How the Stack Differs

| Aspect | Stage 3 (Integration) | Stage 4 (Validation) |
|--------|----------------------|---------------------|
| **Firmware build** | Instrumented (`CONFIG_CONCORD_HARNESS=y`) | Production (`CONFIG_CONCORD_HARNESS=n`) |
| **Verification mechanism** | `ctx.harness.get()`, `ctx.harness.wait_event()` | `ctx.cloud.wait_for_position()`, etc. |
| **What it proves** | Components integrate correctly (internal) | Product meets spec (external) |
| **CoreCloud usage** | Optional (Section 10 of stage3 doc) | Required (primary verification) |
| **Fixture usage** | Minimal (harness inject for most stimuli) | Heavy (button, on-skin, peltier, motion) |
| **Test ownership** | Firmware engineer (`.concord/tests/integration/`) | Validation team (Concord monorepo) |
| **UART handling** | Demuxed: harness prefix + log prefix | Capture-only: no harness, just logs |
| **Build variants tested** | Instrumented only | Debug then release (comparison) |
| **Shared infrastructure** | MTIB client, power profiler, UART capture, artifact storage | Same |

The TestContext API is **the same** for both stages. The difference is which pillars a given test uses. Stage 3 tests lean on `ctx.harness`. Stage 4 tests lean on `ctx.cloud` and `ctx.fixture`. Both use `ctx.mtib` for power and flashing.

---

## 10. What Exists Today vs What Needs to Be Built

### Exists and Ready to Use

| Component | Location | Validation Can Use As-Is? |
|-----------|----------|--------------------------|
| MTIB V2 Server (71 RPCs) | `apps/edge/mtib-server-v2/src/` | Yes |
| MtibV2Client | `libs/python/corekinect/mtib_client/v2/` | Yes |
| ShellCommandHelper | `libs/python/corekinect/mtib_client/v2/client/shell.py` | Yes |
| boot_and_lock_shells() | Same | Yes (manufacturing shell tests) |
| CoreCloud DB Interface | `libs/python/corekinect/core_cloud/db_interface.py` | Yes |
| CoreCloud REST Interface | `libs/python/corekinect/core_cloud/api_interface.py` | Yes |
| MsgBase query methods | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` | Yes |
| GPSConfMsg REST send | Same | Yes |
| FUOTA ORM tables | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` | Yes (read); plan creation TBD |
| TestStep/Test framework | `libs/python/corekinect/test/` | Adapt (see below) |
| Prisma schema (Test, TestExecution) | `prisma/schema.prisma` | Yes |
| K8s deployment patterns | `deploy/manufacturing/` | Adapt |

### Needs to Be Built

| Component | What It Does | Depends On | Complexity |
|-----------|-------------|-----------|------------|
| **TestContext** | Composes MTIB + Cloud + Fixture into unified API | MtibV2Client, CloudClient, FixtureController | Medium — mostly wiring |
| **CloudClient** | Polling wrappers over CoreCloud SDK message classes | CoreCloud SDK (exists) | Low — thin wrapper |
| **FixtureController** | Maps abstract actions to MTIB GPIO/motor/ADC pins | MtibV2Client (exists), fixture profile JSON | Medium — one class per fixture element |
| **UartDemuxer** | Routes UART lines by prefix (harness vs logs vs noise) | MtibV2Client UART streaming (exists) | Medium — state machine for prefix parsing |
| **PowerProfiler** | Wraps MTIB power measurement with trace storage | MtibV2Client PowerMeasure/PowerStream (exists) | Low — wrapper + MinIO upload |
| **LogAccess** | Queries captured UART logs by pattern/time | UartDemuxer (new) | Low — search over captured buffer |
| **HarnessTransport** | Shell command interface for concord_harness | ShellCommandHelper (exists), UartDemuxer (new) | Medium — protocol implementation |
| **ValidationRunner** | Orchestrates test lifecycle (init, flash, run tests, cleanup) | TestContext (new) | Medium — lifecycle management |
| **FuotaPlanBuilder** | Creates FUOTA plans via CoreCloud DB or REST | FUOTA ORM tables (exist) or REST API (TBD) | Medium — depends on backend team answer |
| **FuotaMonitor** | Polls FUOTA progress until completion | FUOTA ORM tables (exist) | Low — polling wrapper |
| **Fixture profile JSON** | Per-product, per-MTIB-node configuration | Physical wiring documentation | Low — one JSON per fixture |
| **concord_harness module** | Zephyr module with GETTER/SETTER/INJECT/EVENT macros | Zephyr module system | High — firmware + Python transport |
| **Pipeline controller** | K8s Job watcher, stage gates, MTIB work queue | K8s API, Prisma schema | High — core orchestration |

### Adaptation Needed

| Manufacturing Pattern | Validation Adaptation | Effort |
|----------------------|----------------------|--------|
| Multi-node ThreadPoolExecutor | Single-node per K8s Job (simpler) | Simplification |
| ThetaFixtureConfig dataclass | Fixture profile JSON (from DB) | Restructure |
| gRPC operator dispatching | K8s Job controller dispatching | New orchestration |
| TestStepResult streaming | Same, plus artifact upload to MinIO | Extension |
| `usr_data[node]` shared state | TestContext instance fields | Simplification |

---

## 11. Design Decisions That Need Resolution

### 11.1 FUOTA Plan Creation: DB ORM or REST API?

The CoreCloud DB has ORM models for FUOTA tables (`Fuotaplanstbl`, `Fuotaprogresshistorytbl`). The validation runner could write plans directly to the DB. But if the CoreCloud backend has a REST API for FUOTA plan management, that's the cleaner interface.

**Question for CoreCloud team**: Does a REST API endpoint exist for creating FUOTA plans? If so, what's the endpoint, authentication, and payload format?

**Fallback**: Use DB ORM writes. The ORM models exist and are tested in production. Direct DB writes bypass any business logic in the backend (e.g., plan validation, duplicate checking), but they work.

### 11.2 GroundModeConfigV2: REST Delivery or DB Workaround?

`GroundModeConfigV2` inherits from `MsgBase` (DB reads work) but not `ConfMsgBase` (no `.send_via_rest()`). 18 config value tests are deferred because of this. Options:

1. **CoreCloud backend adds REST endpoint** for GroundModeConfigV2 delivery. Cleanest, but requires backend work.
2. **Promote GroundModeConfigV2 to ConfMsgBase** in the SDK. Requires knowing the REST endpoint path and API field mapping.
3. **Use v0.9 ConfMsgBase.send()** which writes to `DownlinkMessagesTbl` with binary-packed message. Works for v0.9 devices but unclear if v1.0 backend processes the same downlink queue.
4. **Defer until REST API exists**. Current approach — config tests stay in "deferred" bucket.

**Question for CoreCloud team**: What is the REST endpoint for GroundModeConfigV2 delivery? Is it the same pattern as GPSConfMsg (`PUT /System/Devices/Configurations/...`)?

### 11.3 Test Framework: Adapt Manufacturing or Start Fresh?

The manufacturing TestStep/Test framework is proven but designed for multi-node parallel execution with a gRPC operator. Validation uses single-node K8s Jobs. Options:

1. **Adapt**: Reuse TestStep/Test with `nodes=[single_node]`. Minimal code, but carries multi-node abstractions that validation doesn't need.
2. **New runner**: Build a simpler runner that takes a TestContext and a list of test functions (pytest-style). Cleaner, but doesn't reuse proven code.
3. **Hybrid**: Use the TestStep result/reporting pattern but replace the Test execution model with a pytest-based discovery + execution flow.

**Recommendation**: Option 3 (hybrid). The TestStepResult dataclass and artifact patterns are good. The Test/operator execution model is manufacturing-specific. The validation runner should be pytest-based (test discovery, fixtures, markers, parametrize) with TestContext as a pytest fixture.

### 11.4 Async or Sync Test Functions?

The manufacturing tests are synchronous (blocking `time.sleep()`, blocking gRPC calls). The architecture docs show `async def test_*` with `await`. Options:

1. **Sync**: Simpler, matches manufacturing. `time.sleep()` for waits, blocking MTIB calls. Good enough for single-DUT-per-pod model.
2. **Async**: Enables concurrent operations (measure power while waiting for CloudClient poll). More complex, but allows patterns like "start power measurement, do test, stop measurement" without threading.

**Recommendation**: Start sync, add async later if needed. The single-DUT-per-pod model doesn't have enough concurrency to justify async complexity. If power profiling needs to run concurrently with test actions, use a background thread (manufacturing already does this for motion).

### 11.5 Fixture Profile Storage: DB, Mounted File, or ConfigMap?

The fixture profile JSON needs to reach the test pod. Options:

1. **K8s ConfigMap**: Mounted as a file. Version-controlled if ConfigMaps are in Helm charts.
2. **Concord DB** (Node.fixtureProfile field): Queried by the runner at startup. Already modeled in Prisma.
3. **Environment variable**: Injected as JSON string. Works for small profiles.
4. **MinIO artifact**: Downloaded at startup. Overkill for config.

**Recommendation**: Option 2 (Concord DB). The fixture profile is a property of the MTIB node, already modeled in Prisma (`Node` model). The pipeline controller queries the profile when creating the K8s Job and injects it as a mounted JSON file. This keeps profiles centralized and editable via the Concord UI.

### 11.6 UartDemuxer: Prefix-Based or Stream-Based?

Stage 3 needs to separate harness output (`[CONCORD:GET]`, `[CONCORD:EVT]`) from device logs and Zephyr kernel output. Options:

1. **Prefix-based**: Each line is routed by its prefix string. Simple, works for line-oriented output.
2. **MTIB channel-based**: Use separate UART streams (e.g., RTT for harness, UART for logs). Requires firmware support for RTT harness transport.
3. **Shell-based**: Harness commands/responses go through the shell (synchronous request/response). Events are asynchronous lines with a known prefix.

**Recommendation**: Option 3 (shell + prefix). Harness get/set/inject are shell commands (synchronous, use ShellCommandHelper). Events are asynchronous UART lines with `[CONCORD:EVT]` prefix, routed by the UartDemuxer. This matches the `stage3-integration-tests.md` Section 4.2 design and builds on the existing ShellCommandHelper pattern.

---

## 12. Implementation Priority

Based on dependencies and value delivered:

### Phase 1: Core Stack (enables first Stage 4 tests)

1. **CloudClient** — polling wrappers over CoreCloud SDK
2. **FixtureController** — abstract actions → MTIB GPIO/motor/ADC
3. **Fixture profile JSON** — Alpha product board profile
4. **TestContext** — compose CloudClient + MtibV2Client + FixtureController
5. **PowerProfiler** — wrap MTIB power measurement + artifact storage
6. **ValidationRunner** — pytest-based test discovery + TestContext fixture

**Unblocks**: Power tests (PRDTST-331, 340, 341), motion tests (PRDTST-324, 326), on-skin/biometric tests (PRDTST-327), button tests (PRDTST-325, 346), LED tests (PRDTST-338, 355), NFC test (PRDTST-337).

### Phase 2: UART + Logs (enables Stage 4 UART-based tests and Stage 3)

7. **UartDemuxer** — prefix-based routing for harness vs logs
8. **LogAccess** — search captured UART logs
9. **HarnessTransport** — shell command interface for concord_harness

**Unblocks**: Stage 3 integration tests, any Stage 4 test that needs UART log analysis.

### Phase 3: FUOTA (enables firmware update lifecycle tests)

10. **FuotaPlanBuilder** — create FUOTA plans via DB ORM or REST
11. **FuotaMonitor** — poll FUOTA progress until completion
12. **FUOTA validation flow** — 12-step orchestration

**Unblocks**: PRDTST-376, 377 (FUOTA tests), release gate validation.

### Phase 4: Pipeline Orchestration (enables automated runs)

13. **Pipeline controller** — K8s Job watcher + stage gates
14. **Build service integration** — trigger builds, download artifacts
15. **Artifact management** — MinIO upload/download patterns

**Unblocks**: Automated per-commit and weekly validation runs.

---

## 13. Relationship to Other Documents

| Document | What It Provides | This Document Adds |
|----------|-----------------|-------------------|
| `00-validation-philosophy.md` | Why we test, the pyramid, the lifecycle | How the code implements the philosophy |
| `stage3-integration-tests.md` | Harness design, test transport protocol | How harness integrates with TestContext |
| `stage4-product-tests.md` | PRD test specs, 89 test cases, domains | How each test maps through the stack |
| `stage4-fuota-validation-flow.md` | 12-step FUOTA flow | How FUOTA steps use CloudClient |
| `corecloud-library-architecture.md` | SDK analysis, message types, gaps | How CloudClient wraps the SDK |
| `09-final-architecture.md` | K8s topology, pipeline state machine | How TestContext fits in the K8s Job model |
| `../project/bom-system-implementation.md` | System-level BOM, interface agreements, effort | How test runner stack components fit in the full BOM |
