---
min_role: DEVELOPER
---
# Run Detail

The run detail page at `/validation/runs/<session-id>` is the single view for understanding what happened during a validation session. It renders differently depending on whether the session is still running or has completed.

## Session lifecycle

A session moves through these states:

| Status | Meaning |
|--------|---------|
| **ACTIVE** | Tests are executing. The page shows live updates via WebSocket. |
| **PASSED** | All tests passed. Final counts and timing are locked in. |
| **FAILED** | One or more tests failed. The header shows the failure count. |

The transition from ACTIVE to PASSED or FAILED happens when the test runner calls `report/finish` with the final tally.

## Header

The header section displays:

- **Run name** -- the session name assigned at creation (e.g., "Smoke Run alpha_b0 main #47")
- **Status badge** -- color-coded: green for PASSED, red for FAILED, blue for ACTIVE
- **Product name** -- which product this run targets
- **Serial number** -- the DUT serial under test
- **Pass/fail counts** -- rendered with `.text-success` for passed, visible once tests complete

For active sessions, the status badge pulses. For completed sessions, it is static.

## Test list

Tests are grouped by module (the `module` field in each test). A sidebar shows module names as clickable stage tabs -- selecting one filters the center panel to tests in that module.

Each test entry shows:

- Test name (e.g., `test_idle_current`)
- Pass/fail indicator
- Duration
- Measurements, if the reporter included them (`bootTimeMs`, `currentMa`, etc.)
- Error message on failure

Click a test entry to expand its detail panel with full assertion output and UART context.

## Device record

The session creates a device record from the serial number passed at session creation. The device entry tracks the DUT under test and links to any prior validation history for that serial. The serial number appears in the header metadata.

## Test executions

Each test in the runner's test list becomes a test execution record in the database. The execution tracks:

- Which test ran (name + module)
- Start time and duration
- Pass/fail outcome
- Measurements (key-value pairs stored as JSON)
- Error message if the test failed

Three tests in the suite means three execution records. The run detail page renders one card per execution.

## UART panel

Below the test list, a resizable UART panel shows device serial output captured during the session. The panel renders when telemetry data is available -- for sessions driven by real MTIB hardware, this includes MCUboot output, application logs, and manufacturing shell responses. Simulated sessions (reporter-only, no MTIB) may show an empty panel.

## Artifacts

Completed sessions may have downloadable artifacts -- typically a zip containing UART logs, power traces, and test output. The download endpoint is:

```
GET /v2/sessions/<session-id>/download
```

Returns a zip file if artifacts were captured, or 404 if the session was simulated without a K8s job. The UI shows a download button when artifacts exist.

## Fixture and build references

The session stores references to the fixture that ran it and the build run that triggered it. These appear in the session config:

- `nodeId` -- the MTIB node that executed the tests
- `productId` -- the product under test
- `buildRunId` -- the build whose artifacts were validated (when queue-triggered)
- `fixtureId` -- the physical fixture where the DUT sits

These references let you trace any session back to the specific build, fixture, and node involved.

---

See also: [Real-time view](realtime.md) for WebSocket-driven live updates during active sessions, [Results](results.md) for comparing completed runs, [Queue](queue.md) for how sessions get scheduled.
