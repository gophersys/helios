# go-vulnerabilities

phase:    pr
repo:     gophersys/libs
branch:   fix/go-vulnerabilities
worktree: ~/code/.worktrees/libs-vulns
pr:       -
attempt:  0/2

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
