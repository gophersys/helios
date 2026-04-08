---
min_role: DEVELOPER
---
# Build Monitoring

You triggered a build -- manually or via git push -- and need to know when it finishes, whether it succeeded, and what went wrong if it did not. The build detail page gives you all of that in real time.

## Build detail page

Navigate to **Builds** and click any build row, or go directly to `/builds/<build-run-id>`. The page loads three sections: header, job list, and build log.

**Header** -- the build name (or ID prefix if unnamed), branch (`concord-main`, `release/v1.0`), and a status badge. The badge updates automatically as the build progresses:

| Status | Meaning |
|--------|---------|
| PENDING | Build created, waiting for a worker |
| QUEUED | Worker assigned, waiting for toolchain container to start |
| RUNNING | Compilation in progress |
| SUCCESS | All jobs completed without error |
| FAILED | One or more jobs failed |
| ERROR | Infrastructure failure (container crash, network timeout) |
| CANCELLED | Manually cancelled before completion |

A build transitions through PENDING, QUEUED, RUNNING, and then lands on one of the terminal states. Most firmware builds complete within 5--20 minutes depending on the Zephyr tree size and Kconfig complexity.

## Job list

Each build run contains one or more jobs. A Smoke-stage build for Alpha B0 typically has two jobs (one per target: nRF52840 app processor, nRF9151 comms coprocessor). A Regression-stage build can have six or more.

Jobs appear as a list with individual status badges. Each badge follows the same PENDING through SUCCESS/FAILED progression. Click a job to jump to its portion of the build log.

Jobs run in parallel when the build worker has capacity. A single failing job marks the parent build as FAILED once all sibling jobs finish or time out.

## Build log

The log panel shows compilation output as it streams from the build container. Lines accumulate in real time -- you can watch `west build` progress, CMake configuration, linker output, and artifact emission.

The log grows throughout the build. Take two snapshots 30 seconds apart while the status is RUNNING and the second will be longer. Once the build reaches a terminal status, the log is frozen.

The log endpoint is also available via API:

```bash
curl https://concord.local/v2/builds/runs/<build-run-id>/log \
  -H "Authorization: Bearer <token>"
```

Returns `200` with log text if available, `204` if the build has not started writing logs yet.

## Checking status via API

Poll the build run endpoint to track status programmatically:

```bash
curl https://concord.local/v2/builds/runs/<build-run-id> \
  -H "Authorization: Bearer <token>"
```

The response includes `status`, `branch`, `createdAt`, and `jobs` with per-job status. Useful for CI scripts that need to gate on build completion before proceeding to validation.

## After completion

A successful build produces [artifacts](artifacts.md) -- hex files, CFW files, and `build.json` metadata. The build detail page shows a **Download** button once the build reaches SUCCESS.

A failed build still has a log. Read it from the bottom up: the last error is usually the linker or compiler failure. Common causes: missing Kconfig symbol, board overlay typo, SDK version mismatch.

For how to trigger builds, see [Triggering Builds](triggering-builds.md). For build pipeline internals, see [CI Integration](ci-integration.md).
