---
min_role: DEVELOPER
---
# Validation Results

Open **Validation** in the sidebar and click a completed run. The detail view has three levels: a top-line summary (pass/fail, total duration), a per-stage breakdown, and individual test outcomes with logs and timing.

## Test Status

| Status | Meaning |
|--------|---------|
| **Passed** | All assertions succeeded |
| **Failed** | One or more assertions did not pass -- click through for the failing assertion and UART/power logs |
| **Error** | Infrastructure problem -- the test never ran (timeout, MTIB unreachable, K8s scheduling failure) |
| **Skipped** | Dependency not met (e.g., smoke failed, so POST was skipped) |

## Comparing Runs

Select two runs from the validation list and click **Compare** to see a side-by-side diff. Useful for spotting regressions -- if `test_power_sleep` passed yesterday and fails today, the comparison highlights exactly which assertion changed.

## Exporting

Every run stores a full audit record: test case IDs, pass/fail outcomes with timestamps, device serial and fixture ID, and the firmware version under test. Export as JSON from the run detail page or via `corectl`:

```bash
corectl validate results <run-id> --format json
```
