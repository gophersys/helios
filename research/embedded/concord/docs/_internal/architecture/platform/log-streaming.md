# Runtime Log Streaming Architecture

This document describes how test runtime logs are captured, stored, and displayed in the frontend.

## Overview

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│ K8s Job (pytest)│───►│ Reporter     │───►│ HTTP API        │───►│ Frontend     │
│                 │    │ Plugin       │    │ (logs.py)       │    │ (WebSocket)  │
└────────┬────────┘    └──────────────┘    └────────┬────────┘    └──────────────┘
         │                                          │
         ▼                                          ▼
   stdout/stderr                              MinIO Storage
   UART logs                                  validation/runs/{id}/logs/
   Power traces
```

## Log Capture Layers

### 1. Console Output (stdout/stderr)

All `print()`, `log.info()`, and pytest output goes to K8s Job stdout:

```python
# In conftest.py — tee stdout to buffer
sys.stdout = LogStreamWriter(sys.stdout, _log_buffer, "stdout")
sys.stderr = LogStreamWriter(sys.stderr, _log_buffer, "stderr")

# On session finish — upload to API
requests.post(f"{api_url}/v2/validation/runs/{run_id}/report/log-chunk", json={
    "file": "console.log",
    "offset": 0,
    "data": base64.b64encode(log_content.encode()).decode(),
})
```

### 2. Per-Test Captured Output

The reporter plugin captures stdout/stderr/caplog per test:

```python
# In reporter.py — pytest_runtest_makereport hook
if report.capstdout:
    captured += report.capstdout
if report.capstderr:
    captured += report.capstderr
if report.caplog:
    captured += report.caplog
```

This is sent with each test result:

```python
self._post("report/test-result", {
    "testName": test_name,
    "passed": passed,
    "logOutput": captured[:10000],  # Cap at 10KB
})
```

### 3. UART Logs (per slot/DUT)

UART output is captured via the MTIB UART stream and dumped per-test:

```python
# In conftest.py — teardown
def _test_lifecycle(request, fixture_ctx):
    yield
    for slot in fixture_ctx.slots.values():
        uart_log = slot.get_uart_log()
        if uart_log:
            log_path = f"{artifacts_dir}/{request.node.name}_{slot.slot_id}_uart.log"
            with open(log_path, "w") as f:
                f.write(uart_log)
```

### 4. K8s Job Logs

The HTTP API can fetch live logs from a running Job:

```python
# GET /v2/validation/runs/{id}/logs/job
kubectl logs job/{job_name} -n {namespace} --tail=1000
```

## Storage

All logs are stored in MinIO under:

```
concord/validation/runs/{run_id}/
├── logs/
│   ├── console.log          # Full pytest stdout/stderr
│   ├── test_step_01_uart.log
│   └── ...
├── artifacts/
│   ├── power_trace.csv
│   └── ...
└── manifest.json             # Run metadata
```

## API Endpoints

### Log Chunk Ingestion

```http
POST /v2/validation/runs/{id}/report/log-chunk
Authorization: ApiKey {key}
Content-Type: application/json

{
  "file": "console.log",
  "offset": 0,
  "data": "base64-encoded-content",
  "timestamp": 1709913600.123
}
```

### Log File Retrieval

```http
GET /v2/validation/runs/{id}/logs/{file_path}?offset=0
Authorization: Bearer {jwt}

Response:
  Body: raw bytes
  Headers:
    X-Offset: 0
    X-Total-Size: 12345
```

### Run ZIP Download

```http
GET /v2/validation/runs/{id}/download
Authorization: Bearer {jwt}

Response:
{
  "data": {
    "url": "https://minio/presigned-url?..."
  }
}
```

## WebSocket Events

Live log streaming to the frontend uses Socket.IO:

```typescript
// Frontend subscribes to run room
socket.emit("join_run", { runId });

// Server broadcasts log chunks
socket.on("validation_log_chunk", (data) => {
  // data: { runId, file, offset, data, timestamp }
  const bytes = atob(data.data);
  appendToLogViewer(data.file, bytes);
});
```

Events:

| Event | Payload | When |
|-------|---------|------|
| `validation_run_start` | `{ runId }` | Session start |
| `validation_test_start` | `{ runId, testName, module }` | Test begins |
| `validation_test_result` | `{ runId, testName, passed, duration, error, skipped }` | Test ends |
| `validation_log_chunk` | `{ runId, file, offset, data }` | Log chunk received |
| `validation_run_finish` | `{ runId, total, passed, failed }` | Session end |

## Frontend Components

### Log Viewer

The run detail page includes a real-time log viewer:

```svelte
<script>
  import { onMount } from "svelte";
  import { websocket } from "$lib/services/websocket";

  let logContent = "";

  onMount(() => {
    websocket.joinRun(runId);
    websocket.on("validation_log_chunk", (data) => {
      if (data.file === "console.log") {
        logContent += atob(data.data);
      }
    });
  });
</script>

<pre class="font-mono text-sm">{logContent}</pre>
```

### Test Result Cards

Each test shows its captured output:

```svelte
{#if test.logOutput}
  <details>
    <summary>View output</summary>
    <pre>{test.logOutput}</pre>
  </details>
{/if}
```

## Manufacturing vs Validation

The same infrastructure serves both:

| Aspect | Validation | Manufacturing |
|--------|-----------|---------------|
| Test runner | pytest | pytest |
| Reporter plugin | Same | Same |
| Log storage | Same | Same |
| WebSocket events | Same | Same |
| Multi-slot | No (1 DUT) | Yes (4+ DUTs) |
| Firmware variant | debug/release | mfg only |

Manufacturing tests add per-slot UART logs:

```
logs/
├── console.log
├── test_step_01_slot-1_uart.log
├── test_step_01_slot-2_uart.log
├── test_step_01_slot-3_uart.log
└── test_step_01_slot-4_uart.log
```

## Usage

### Running with Log Streaming

```bash
# Set environment variables
export CONCORD_RUN_ID="cm123..."
export CONCORD_API_URL="https://concord.example.com"
export CONCORD_API_KEY="ck_run_abc123..."

# Run tests — logs stream automatically
cd apps/manufacturing/alpha
PYTHONPATH=.:../../../libs/python:../../../libs pytest tests_pytest/ -v
```

### Viewing Logs in Frontend

1. Navigate to `/validation/runs/{id}`
2. Click "Live Logs" tab
3. Logs stream in real-time as tests execute
4. Click "Download" to get ZIP of all artifacts
