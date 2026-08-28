---
min_role: DEVELOPER
---
# Real-Time Validation View

A validation session takes minutes to complete. You should not have to wait for it to finish before you know whether `test_boot` passed. The run detail page at `/validation/runs/<session-id>` connects to the server over WebSocket and updates the DOM as events arrive -- no polling, no page reload.

## What updates in real time

When the reporter API receives events from the test runner, the server broadcasts them over Socket.IO. The run detail page listens and mutates the DOM directly:

**Test timeline cards.** Each test appears as a card the moment the runner calls `report/test-start`. The card shows the test name and module, with a "running" indicator. When `report/test-result` arrives, the card updates to show pass/fail status, duration, and any measurements attached to the result.

**Progress bar.** A horizontal bar at the top of the test list fills as tests complete. It tracks total tests (from the `report/test-list` payload sent at session start) against completed tests.

**Summary header.** While the session is ACTIVE, the header shows the run name, product, serial number, and a live status badge. When `report/finish` arrives with final counts, the badge flips to PASSED or FAILED and the header displays total/passed/failed counts.

## Event sequence

The reporter API expects this call order from the test runner:

```
POST /v2/sessions/<id>/report/start          → session becomes ACTIVE
POST /v2/sessions/<id>/report/test-list       → frontend pre-populates expected tests
POST /v2/sessions/<id>/report/test-start      → card appears (one per test)
POST /v2/sessions/<id>/report/test-result     → card updates with outcome
  ... repeat test-start/test-result for each test ...
POST /v2/sessions/<id>/report/finish          → session completes, header updates
```

Each `test-result` payload carries:

| Field | Type | Required |
|-------|------|----------|
| `testName` | string | yes |
| `module` | string | yes |
| `passed` | boolean | yes |
| `durationS` | float | yes |
| `errorMessage` | string | no -- present on failures |
| `measurements` | object | no -- key-value pairs like `{ "currentMa": 18.2 }` |

## Failed tests

When a test fails, its card turns red and shows the error message. Measurements still display -- a failure like "Current 45mA exceeds 33mA limit" paired with `{ "currentMa": 45.2 }` gives you both the assertion context and the raw value in one glance.

If any test in the session fails, the final `report/finish` sets the session status to FAILED. The header badge reflects this immediately.

## Connection behavior

The page opens a Socket.IO connection on mount and subscribes to events for the specific session ID. If the connection drops (network hiccup, server restart), the page falls back to periodic HTTP polling until the socket reconnects. A page reload always fetches the latest state from the REST API and re-establishes the socket.

For completed sessions, the page renders the final state from the API response -- no socket needed.

---

See also: [Run detail](run-detail.md) for the full page layout including UART panel and artifacts, [Results](results.md) for interpreting completed session outcomes.
