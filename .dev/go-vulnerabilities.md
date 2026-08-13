# go-vulnerabilities

phase:    submit
repo:     gophersys/libs
branch:   fix/go-vulnerabilities
worktree: ~/code/.worktrees/libs-vulns
pr:       10
attempt:  1/2

## Goal

Clear GO-2026-5970: `golang.org/x/text` v0.37.0 is CALLED by `go/secrets` and
`go/workspaceprovider`, and it is fixed in v0.39.0. When this lands, the `vuln`
verb passes for both libraries and eden#7 loses 1 of its 3 blockers.

## Plan

APPROVED, and the SCOPE CHANGED TWICE. My brief was wrong on both original
advisories; the planner refuted it by running govulncheck rather than reading my
summary.

**GO-2026-5856 — not this repository's to fix.** CVE-2026-42505, an ECH privacy
leak in `crypto/tls`. A Go TOOLCHAIN bug: vulnerable in go1.26.0-1.26.4, fixed in
go1.26.5. Genuinely CALLED in 5 libraries. The whole fix is `ARG GO_VERSION` in
`.devcontainer/base/Dockerfile`, which belongs to the drop-arm64 feature — same
file, same base image republish. Moved there.

**GO-2026-5668 — no action.** Not reachable, and it has already stopped being
reported. Do not bump it, do not allowlist it. Recorded so nobody re-opens it.

**GO-2026-5970 — the one nobody named, and the only one this repository fixes.**

**Scope change 2 (phase 7): `go/objectstorage` dropped.** It does not CALL
x/text, so it was never part of the advisory. Including it made a library with
pre-existing manifest drift an AFFECTED project and turned the gate red on a
security fix. Its drift is tracked as its own task, which includes its x/text
bump.

## Proven

Every line below was run in `ghcr.io/gophersys/base:latest` (--platform
linux/amd64, worktree bind-mounted at its own absolute path, submodule gitdir
`/Users/mateo/code/eden/.git/modules/libs` mounted, host module cache at
`/home/dev/go/pkg/mod`, cictl built from `/Users/mateo/code/cictl` into
`/usr/local/bin`).

- RED, before the bump. `bash go/_ctl/vulnerability_test.sh` → rc=1:
  `secrets CALLS a vulnerable golang.org/x/text: GO-2026-5970
  golang.org/x/text@v0.37.0 fixed=v0.39.0 via .../secrets/vaultadapter.Login`,
  and the same for `.../workspaceprovider/dockeradapter.Exec`.
- RED in the real gate. `go/secrets` and `go/workspaceprovider` → rc=1,
  `[error] vuln: called vulnerabilities NOT accepted: GO-2026-5970`.
- GREEN, after. `bash go/_ctl/vulnerability_test.sh` → rc=0, read from `rc=$?`:
  `2 test(s) hold; 2 of 2 proven able to fail`. Both fail under their recorded
  pre-bump scans, so neither is vacuous.
- GREEN in the real gate. `go/secrets` → rc=0 `[ok] vuln: OK (no called
  vulnerabilities)`. `go/workspaceprovider` → rc=0 `[ok] vuln: OK (all called
  vulnerabilities are accepted-risk allowlisted)` — GO-2026-5970 gone, only the
  pre-existing docker/docker pair remains, and that allowlist is on origin/main.
- THE REPOSITORY'S OWN PR GATE. `bash .ci/ctl.sh affected-gate-fast` → rc=0.
  Affected = `go/secrets`, `go/workspaceprovider`. All 5 dimensions PASS for
  both: build, golangci-lint+hnslint+cohesion, apidiff, vet, unit+conformance
  under -race.
- `bash .ci/ctl.sh validate` → rc=0, and it RAN: the shell suites report
  `5 test(s) hold; 4 of 5 proven able to fail` and `2 test(s) hold; 2 of 2
  proven able to fail`.
- CONTROL, so caused is not confused with surfaced. A detached worktree at
  `origin/main`, `go/objectstorage`, `bash ./ctl.sh phase-gate implementation`
  → 5 of 5 dimensions FAIL, rc=1. objectstorage is broken on main independently
  of this branch.

### The one unrelated version move, and why it is forced

`golang.org/x/sync v0.20.0 → v0.21.0` in `secrets`. `x/text@v0.39.0`'s own go.mod
carries `require golang.org/x/sync v0.21.0 // indirect`, so MVS selects it; it
cannot be pinned back without a downgrade `replace`. Same cause for the
`x/tools v0.44.0 → v0.47.0` go.sum line in `workspaceprovider`. Nothing else
moved in any of the 4 manifest files.

## Blocked

Nothing blocks this PR.

Two findings this feature SURFACED, both filed and neither included here:

- **The PR gate reports green when cictl is absent.** `.ci/ctl.sh:74` reads
  `mapfile -t projects < <(affected_projects)`, and `affected_projects` opens
  with `require_cmd cictl` whose failure path is `exit 127`. Process substitution
  is a subshell, so that exit kills only the subshell; `mapfile` reads an empty
  stream and the caller returns 0 with "no affected projects — clean no-op".
  Measured on this very branch: without cictl the gate said no affected projects
  and returned 0; with cictl the affected list was 3 libraries and the gate
  returned 1. Must be fixed before the .ci layer is rolled to the other repos.
- **`go/objectstorage` fails 5 of 5 gate dimensions on `origin/main`**, from
  manifest drift. `go mod tidy` alone is NOT the fix: it adds 4 requirements the
  go.mod never declared, into the main require block rather than the ADR-0020
  test-only block. Nothing enforces tidiness — `grep tidy` across `go/_ctl`,
  `.ci/` and `.github/workflows/` returns nothing.

## Next

Phase 6 — poll the checks on the pull request. Read the log of any check that
goes green suspiciously fast, and record in this file what it actually ran.

## Phase 7 — attempt 1, the merge tier failed

`merge tier (affected-gate-substrate)` FAILED after 11m42s on PR #10.

```
panic: test timed out after 10m0s
  running tests:
    TestK3d_ProvisionRunExecFilesTeardown (22s)
FAIL github.com/gophersys/libs/go/workspaceprovider/kubernetesadapter  600.011s
```

WHAT PASSED FIRST, so the scope of the failure is exact:
- `go/secrets` substrate — every package ok, across all 3 lanes (integration,
  lifecycle, load). `vaultadapter` 33.6s, `platformconnectoradapter` 25.6s.
- `go/workspaceprovider` — `dockeradapter` ok at 90.3s, and 5 internal packages ok.
- Only `kubernetesadapter`, the k3d/kind lane, ran out of its 10-minute package
  budget.

CAUSED OR SURFACED — being measured, not assumed. No CI run in recent history has
exercised this tier for `go/workspaceprovider`, because the tier runs only over
AFFECTED projects and nothing had touched that library. So history cannot answer
it and a control is the only way.

CONTROL: PR #11, branch `control/k3d-timeout-baseline`, a draft that never merges.
It is 1 comment appended to `kubernetesadapter/client.go` and nothing else — just
enough to make the same library affected, WITHOUT the x/text bump.

- same timeout there → pre-existing in the k3d lane, this PR only surfaced it,
  and the timeout is filed as its own defect
- green there → the bump is implicated and this feature returns to phase 3

An x/text bump causing a k3d cluster provision to hang is not plausible, but
plausibility is not evidence and this organization has been wrong on exactly that
kind of guess before.

### Control result — SURFACED, not caused. This feature is exonerated.

| run | change | in flight at the alarm | result |
| --- | --- | --- | --- |
| #10 | x/text v0.37.0 -> v0.39.0 | TestK3d_ProvisionRunExecFilesTeardown (22s) | FAIL 600.011s |
| #11 | 1 comment, no dependency change | TestKind_Conforms (2m28s) | FAIL 600.014s |

Same package, same 600s wall, WITHOUT the bump. The different test name is
expected: the panic names whichever test held the floor when the 10-minute alarm
fired, not the culprit.

Cause: `go/_ctl/lib.sh` runs `go test -tags integration ./... -count=1` with NO
`-timeout` flag, so Go's default 10m per package applies, and `kubernetesadapter`
provisions BOTH a k3d and a kind cluster in one package. For scale from the same
runs: dockeradapter 93s, secrets/vaultadapter 33.6s, every other package under 1s.

It had never run in CI before, because the substrate tier selects only AFFECTED
projects and nothing had touched go/workspaceprovider. This was never a passing
check that broke — it was an unrun check.

Filed as its own task with the timeout-vs-split decision left OPEN, not guessed.
PR #11 is closed and its branch deleted, local and remote.

## Next

Phase 8 — the final stop. This PR is complete and its own gate is green; the only
red is a pre-existing lane failure proven to be independent of it. It needs
Mateo's merge approval, and a decision on whether to merge over a red substrate
tier or fix task #42 first.
