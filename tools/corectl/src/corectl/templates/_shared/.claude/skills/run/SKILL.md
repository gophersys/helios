---
name: run
description: Run one stage's tests against a local fixture (MTIB) — pre-upload sanity check on real hardware
user-invocable: true
argument-hint: "<stage_name> [-m <marker>] [-t <timeout>]"
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Run a stage locally

Execute one stage's pytest suite against a fixture in front of you. Use this between `/validate` (which is offline) and `/upload-dev` (which goes to the platform) to confirm the change works on real hardware before publishing.

Arguments: $ARGUMENTS — first arg is the stage name; optional `-m <marker>` filters tests, `-t <timeout>` overrides per-test timeout in seconds.

## Pre-flight

1. **Stage must exist.** Confirm `concord.yaml stages.<stage>` is defined and `tests/<stage>/` has at least one `test_*.py`.
2. **Fixture must be reachable.** Validate that `MTIB_HOSTS` is set in the environment (`echo $MTIB_HOSTS`) — comma-separated `<addr>:<port>` of the MTIB(s) wired to the DUT(s) you'll run against. Without this, the autoconf plugin will fail to bind the slot fixture and the run dies before any test starts.
3. **Manifest in sync.** `corectl test sync` (no --apply) — abort if drift, fix first via `/sync-with-backend`.

## Run

```bash
corectl test run <stage>                              # default per-test timeout
corectl test run <stage> --marker <marker_name>       # subset filter
corectl test run <stage> --timeout 120                # per-test timeout override
corectl test run <stage> --verbose                    # full pytest -v output
```

## What `corectl test run` does

- Sets `STAGE=<stage>` and `RUNNER_MODE=ephemeral` env vars.
- Pytest collects everything under `tests/<stage>/`.
- The autoconf plugin instantiates the fixture, opens the slot(s), and injects them into each test as the `slot` fixture.
- The reporter plugin batches step events; without a `CONCORD_RUN_ID`, events stay local and stream to stdout instead of the platform.
- Exits non-zero on any failed test — the same gate `/upload-dev` and CI use.

## Reading the output

- `PASSED` per test = green; `FAILED` = inspect the traceback + the recorded measurements.
- When a step fails, the reporter prints the step name + the value that violated the predicate. Look for the most recent `assert_and_record` call in the test file at that line.
- A test that hangs past its timeout is killed by pytest-timeout — usually means a `slot.uart.expect(...)` is waiting on output the DUT didn't send.

## After a clean run

Move on to `/upload-dev` to publish the version and let it run on the platform's fixtures.

## After a failed run

Engage the **test-debugger** agent (`Task` tool with `subagent_type: test-debugger`). It collects the failing test source, fixture state, and recent diffs, then proposes a minimal fix.

## What you may NOT do

- Do not run with `MOCK_MODE=true` and pretend a real fixture validated the change. Mock mode skips hardware interactions; passing tests there mean nothing about the bench.
- Do not edit `tests/<stage>/` mid-run to "fix" a failure. Stop the run, edit, re-validate, re-run.
