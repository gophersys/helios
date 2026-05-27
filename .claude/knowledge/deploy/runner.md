# Deploy — test-runner image and its enforcement layers

The **test-runner** is the K8s Job image that pulls a test package, installs
it, and runs pytest against the fixture. It lives at
[`deploy/runner/`](../../../../deploy/runner/) and is built and pushed as
part of `nx update platform`.

This file describes the runner's structure AND the four-layer enforcement
that prevents the corekinect → runner version-skew failure mode observed
in the v0.12.0 → v0.12.3 release sequence (see
[`workflows/version-skew.md`](../workflows/version-skew.md)).

Refresh this file when: the image's baked-in dependencies change, any of
the four enforcement layers is altered, or the runner's entrypoint flow
changes.

## What the image bakes in

| Path | Why it ships in the image |
|---|---|
| `libs/python/corekinect/` | The Python SDK that test packages import (`from corekinect import ...`). |
| `libs/protocols/mtib/` | Generated mtib gRPC stubs that corekinect imports at runtime. |
| `tools/corectl/` | Diagnostic and download CLI invoked from `entrypoint.sh` for some flows. |

The image is rebuilt and pushed on every `nx update platform` run. The
problem: Nx only rebuilds projects in the affected graph, and **without
implicit dependencies declared**, a change to corekinect would NOT mark
the runner as affected — leaving stale runner pods running new test
packages.

## The four enforcement layers

| Layer | Where | What it does |
|---|---|---|
| 1 | `deploy/runner/project.json` `implicitDependencies` | Nx affected-graph marks the runner dirty on any change to corekinect/protocols/corectl. |
| 2 | `deploy/ctl.sh` SHA gate | Before `update`, compares the runner image's bundled corekinect git SHA against `HEAD`. Fails the deploy if drifted. |
| 3 | `/concord-release` skill release-range gate | Before version bump, checks `git diff $LAST_TAG..HEAD -- libs/python/corekinect/ libs/protocols/mtib/ tools/corectl/`; if non-empty, asserts test-runner is in the release build set. |
| 4 | `deploy/runner/entrypoint.sh` semver gate | Reads `frameworkVersion` from the downloaded `concord.yaml`, compares against the runner's bundled corekinect version. Fails (with operator-friendly message) if the constraint is violated. |

Layer 1 is the Nx-affected hook. Layer 2 catches a hand-built local image
drifting from a CI build. Layer 3 catches a missed runner rebuild at
release-cut time. Layer 4 catches a runner that's already deployed
running a test package newer than its bundled SDK.

Escape hatches (loud-log when used):
- `CONCORD_FORCE_STALE_RUNNER=1` — bypass Layer 2.
- `--force-no-runner-rebuild` — bypass Layer 3.
- `CONCORD_FORCE_STALE_PACKAGE=1` — bypass Layer 4.

## Layer 1 — Nx implicitDependencies

`deploy/runner/project.json` declares:

```json
"implicitDependencies": [
  "corekinect",
  "protocols",
  "corectl"
]
```

These are project NAMES (the `name` field in each project's `project.json`),
not source paths. Nx uses these to add edges to the project graph: an
edit to any file under those projects' source roots marks `test-runner`
as affected.

Verify in the devcontainer:
```
nx show projects --affected --files libs/python/corekinect/__init__.py
# test-runner MUST appear in the output
```

The contract is pinned by
[`deploy/runner/tests/test_project_dependencies.py`](../../../../deploy/runner/tests/test_project_dependencies.py),
runnable as `nx run test-runner:unit-test`.

If you rename a project, update BOTH the `implicitDependencies` list AND
the `REQUIRED_IMPLICIT_DEPENDENCIES` tuple at the top of the test file.

## Layer 2 — ctl.sh runtime SHA gate

The runner Dockerfile bakes the workspace's `libs/python/corekinect/`
tree SHA into the image as:
- `ENV COREKINECT_GIT_SHA=<sha>` (readable via `docker image inspect`)
- A line in `/etc/concord-runner-build-info` (readable from inside a
  running pod for correlation)

The SHA is computed by `_corekinect_sha()` in `deploy/ctl.sh`:
```
git log -1 --format=%H -- libs/python/corekinect/   # primary
git ls-tree -d HEAD libs/python/corekinect | awk    # fallback
sed -n '4p' .git-build-info                          # last resort
```

Passed to the build via `--build-arg COREKINECT_GIT_SHA` from
`cmd_build` (see the `runner|test-runner)` branch).

Before `cmd_deploy` runs (inside `cmd_update`), the gate
`_check_runner_corekinect_freshness <env>` reads the baked SHA from
`docker image inspect <registry>/concord-test-runner:<env>` and
compares it against `_corekinect_sha`.

Behavior matrix:

| Baked SHA       | Workspace SHA | Result |
|-----------------|---------------|--------|
| matches         | (any)         | pass silently (`✓ runner freshness: ...`) |
| diverges        | (any)         | **fail**, name the drift, point to `CONCORD_FORCE_STALE_RUNNER=1` |
| absent / "unknown" | (any)      | warn + pass (legacy image — pre-Phase-D builds) |
| local image missing | (any)     | warn + pass (registry-only or other-node build) |

Escape hatch: `CONCORD_FORCE_STALE_RUNNER=1` downgrades the
divergence-fail to a screaming-banner warn-and-continue. Use only for
emergencies where you understand the cost.

**Manufacturing-safety note:** the runner deployed at v0.12.3 (the one
serving the active session `cmpn99zoa0088i6ahaxcz0tcq`) was built
BEFORE this layer existed and therefore has no `COREKINECT_GIT_SHA`
baked in. The "absent / unknown" row above is what protects that
session — the v0.12.4 first-deploy will warn and pass through, NOT
refuse, so manufacturing is never blocked by the gate enabling itself.
After v0.12.4 ships, every subsequent rebuild populates the var and
the gate becomes hard-fail on real drift.

The gate is sourceable for testing: `deploy/ctl.sh` is guarded by
`if [[ "${BASH_SOURCE[0]}" != "${0}" ]] || [[ "${CONCORD_CTL_NO_DISPATCH:-0}" == "1" ]]`,
so the test harness in
[`deploy/runner/tests/test_ctl_runner_freshness_gate.py`](../../../../deploy/runner/tests/test_ctl_runner_freshness_gate.py)
can source the file and call the gate function directly without
triggering the main dispatcher.

## Layer 3 — /concord-release skill range gate

(Wired in Phase D Layer 3 — see commit history on
`chore/enforce-runner-corekinect-coupling`.)

## Layer 4 — entrypoint.sh semver gate

(Wired in Phase D Layer 4 — see commit history on
`chore/enforce-runner-corekinect-coupling`.)

The Layer 4 check is **semver-compatible**, not strict-SHA. The runner
must satisfy the test package's `frameworkVersion` constraint
(e.g., `>=0.9.0`), not match a specific git SHA. This avoids
unnecessarily blocking older-but-still-compatible test packages from
running on a freshly deployed newer runner. The active manufacturing
session's package (`dev-99490cd3-1779845120`,
`frameworkVersion: ">=0.9.0"`) MUST continue to satisfy runners ≥ 0.9.0.

## When you touch this area

- Adding a new baked-in dependency to the runner Dockerfile? Add it to
  `implicitDependencies` AND the test's required-list AND this file.
- Changing the semver check semantics in `entrypoint.sh`? Update the
  Layer 4 section here AND `workflows/version-skew.md`.
- Modifying an escape hatch? Note it here and in
  `workflows/version-skew.md`.

## Related

- [`workflows/version-skew.md`](../workflows/version-skew.md) — the
  canonical incident this enforcement is built against.
- [`../rules/version-coupling.md`](../../rules/version-coupling.md) —
  auto-loaded "if you touch X, you MUST also Y" rules.
- [`ctl-sh.md`](ctl-sh.md) — the deploy CLI that the Layer 2 gate lives in.
