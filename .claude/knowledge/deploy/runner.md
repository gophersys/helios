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

The `/concord-release` skill runs a release-range gate in
[`Phase 1.5`](../../skills/concord-release/SKILL.md), between
pre-flight and the version-bump branch creation. The gate is a
standalone bash script:

[`scripts/release-gates/check-runner-affected.sh <last_tag> [<head_ref>]`](../../../scripts/release-gates/check-runner-affected.sh)

What it does:

1. `git diff --name-only $LAST_TAG..$HEAD_REF -- libs/python/corekinect/ libs/protocols/mtib/ tools/corectl/`
2. If empty → exit 0 silent (most releases land here).
3. If non-empty → run `nx show projects --affected --base=$LAST_TAG --head=$HEAD_REF`.
4. If `test-runner` is in the affected list → exit 0 with an
   info-banner naming what changed and confirming the rebuild.
5. If `test-runner` is NOT in the affected list → exit 1 with a
   clear remediation pointing at Layer 1
   (`deploy/runner/project.json` `implicitDependencies`).

Escape hatch: `CONCORD_FORCE_NO_RUNNER_REBUILD=1` downgrades the
hard-fail to a loud warn-and-continue. Use only with explicit user
approval — the deployed runner WILL be stale.

**Inconclusive fallback (submodule caveat):** when `nx` cannot
resolve the `base..head` range — most common when running from
inside a devcontainer where `concord` is a submodule of the umbrella
`work/` workspace and the parent `.git/modules` is not mounted, OR
when running from the host where `nx` itself isn't on PATH — the gate
detects the failure (patterns: `not a git repository`,
`Command failed: git diff`, `command not found`) and treats it as
**inconclusive — pass through with a loud warning**. The operator
must then visually confirm "Test runner" appears in `cmd_build`'s
output during Phase 9/10 of the release. Mirrors Layer 2's
"missing local image → warn + pass" behavior so a submodule-mount
limitation never blocks a real release.

To bypass the inconclusive fallback (i.e., get a real answer), set
`NX_AFFECTED_CMD="<a-wrapper-that-runs-nx-from-a-context-that-can-see-the-range>"`
or run the gate from a standalone (non-submodule) clone of concord.

Contract pinned by
[`scripts/tests/test_check_runner_affected.py`](../../../scripts/tests/test_check_runner_affected.py)
(11 tests covering: empty range, runner-in-set, runner-missing for
each of the three paths-of-interest, unrelated change, escape
hatch, usage error, nx-failure-inconclusive, and the SKILL.md wiring).

## Layer 4 — entrypoint.sh framework-constraint gate

After the test package is downloaded and extracted, BEFORE pytest is
invoked, `entrypoint.sh` runs the standalone Python gate:

[`deploy/runner/check_framework_constraint.py <path-to-concord.yaml>`](../../../deploy/runner/check_framework_constraint.py)

The gate reads the test package's `package.framework` constraint from
its `concord.yaml` (the canonical key — verified against the live
sigma5_manufacturing manifest 2026-05-26) and asserts that the runner
image's bundled `corekinect.__version__` satisfies it.

### Why semver-compatible, not strict-SHA

The check is implemented with `packaging.specifiers.SpecifierSet`
(PEP 440). A strict-SHA equality check would unnecessarily block
older-but-still-compatible test packages from running on a freshly
deployed newer runner. Concrete example:

- The active session on panel `0AW2` (session `cmpn99zoa0088i6ahaxcz0tcq`,
  test package `dev-99490cd3-1779845120`) declares
  `package.framework: ">=0.9.0"` in its concord.yaml.
- After v0.12.4 ships, the runner has `corekinect.__version__ == "0.12.4"`.
- `0.12.4` satisfies `>=0.9.0` → gate passes → manufacturing
  continues without interruption.

A strict-SHA check would reject this and block manufacturing.

### Behavior matrix

| Constraint | Runner version | Force var | Exit | Output |
|---|---|---|---|---|
| `>=0.9.0` | `0.12.4` | unset | 0 | `✓ ... satisfied by corekinect 0.12.4` |
| `>=1.0` | `0.8.0` | unset | 1 | hard error with constraint, runner version, and `corectl test refresh-framework && corectl test upload` remediation |
| `>=1.0` | `0.8.0` | `1` | 0 | 6-line banner warning + pass |
| `<1.0,>=0.9` | `1.0.0` | unset | 1 | upper-bound violation |
| `~=0.12.0` | `0.13.0` | unset | 1 | compatible-release upper bound |
| (absent / empty) | any | unset | 0 | warn-and-pass — legacy v1 manifests fall back to permissive |
| `hilarious garbage` | any | unset | 2 | parse error |
| (manifest missing) | any | unset | 2 | "concord.yaml not found at ..." |

Escape hatch: `CONCORD_FORCE_STALE_PACKAGE=1` downgrades the
violation-fail to a 6-line loud-warn banner and passes. Use only for
emergency triage where you understand the implication (tests will run
against a corekinect version they weren't validated against).

### Failure propagation to http-api (Option B)

Decision: **Option B — exit non-zero from the runner pod, let the
existing failure-detection path mark the run FAILED**, rather than
Option A (have entrypoint.sh POST `report/finish` itself).

Rationale:
- `report/finish` is gated by `@require_auth` and expects a real JWT,
  not the runner's API-key model. Minting a token in bash would
  require new auth plumbing.
- The Phase D P2 visibility batch (next branch,
  `fix/manifest-load-failure-visibility`) is already going to harden
  http-api's "all-tests-skipped → FAILED with errorMessage" path
  AND surface `run.errorMessage` in the frontend. The gate's
  non-zero exit feeds into that path cleanly: runner pod exits 1
  → no further heartbeats → existing timeout-failure handler kicks in
  → run shows FAILED. After P2 lands, the operator also sees the
  errorMessage that explains the constraint mismatch.
- Adds zero new code-surface to the gate itself.

If a future tightening is needed (e.g., the operator wants the FAILED
status to appear instantly rather than after the heartbeat-timeout
window), revisit and switch to Option A — but only after the http-api
exposes a runner-friendly authenticated channel for terminal-failure
reporting.

### Wiring

`deploy/runner/Dockerfile` copies the script to `/app/check_framework_constraint.py`:
```dockerfile
COPY deploy/runner/check_framework_constraint.py /app/check_framework_constraint.py
RUN chmod +x /app/entrypoint.sh /app/check_framework_constraint.py
```

`deploy/runner/entrypoint.sh` invokes it in a new "Step 2.5" block
between the extract and the pip-install:
```bash
if [ -f /app/concord.yaml ]; then
    if ! python3 /app/check_framework_constraint.py /app/concord.yaml; then
        gate_exit=$?
        echo "[runner] framework-constraint gate refused the run (exit ${gate_exit})."
        exit ${gate_exit}
    fi
fi
```

`deploy/runner/requirements.txt` pins `packaging==24.2` explicitly
(it was already a transitive dep via pip).

Contract pinned by
[`deploy/runner/tests/test_framework_constraint_gate.py`](../../../deploy/runner/tests/test_framework_constraint_gate.py)
— 14 tests including:
- `test_active_session_emulation_must_pass` (synthesized constraint
  `>=0.9.0` + runner 0.12.4)
- `test_real_sigma5_manufacturing_concord_yaml` (real live
  concord.yaml copied from
  `/home/mateo/work/manufacturing/sigma5_manufacturing/concord.yaml`,
  evaluated against a stubbed corekinect 0.12.4)

Both must pass — they are the tonight-manufacturing safety case.

### Future hardening (not in scope for v0.12.4)

The active session's `framework: ">=0.9.0"` is intentionally
permissive — it lets the runner upgrade freely. If we later want to
tighten it (e.g., to `~=0.12.0` so a 0.13.x runner upgrade requires
an explicit re-test), that change lives in the **test app's**
concord.yaml (`sigma5_manufacturing`, `sigma5_validation`, etc.) and
flows through `corectl test upload`. The runner-side gate does not
need any change for that tightening — it just evaluates whatever
PEP 440 specifier the test app declares.

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
