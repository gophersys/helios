# go-vulnerabilities

phase:    red
repo:     gophersys/libs
branch:   fix/go-vulnerabilities
worktree: ~/code/.worktrees/libs-vulns
pr:       -
attempt:  0/2

## Goal

Clear the 2 govulncheck advisories that block gophersys/eden#7:
  GO-2026-5856  reported in forge, objectstorage, secrets
  GO-2026-5668  reported in orchestrator, workspaceprovider

When this is done, the vuln verb passes for those 5 libraries and eden#7 loses 1
of its 3 blockers.

## Plan

APPROVED, and the SCOPE CHANGED. My brief was wrong on both counts, and the
planner refuted it by running govulncheck rather than reading my summary.

**GO-2026-5856 — not this repository's to fix.** CVE-2026-42505, an ECH privacy
leak in `crypto/tls`. It is a Go TOOLCHAIN bug, vulnerable in go1.26.0-1.26.4,
fixed in go1.26.5. Reachable and genuinely CALLED in all 5 libraries. The entire
fix is `ARG GO_VERSION` in `.devcontainer/base/Dockerfile:59`, which belongs to
the drop-arm64 feature — same file, and both need the same base image republish.
Moved there.

**GO-2026-5668 — no action.** Not reachable, and it has already stopped being
reported. Do not bump it, do not allowlist it. Recorded so nobody re-opens it.

**GO-2026-5970 — the one nobody named, and the only one this repository fixes.**
An `x/text` bump. Without it eden#7 stays red, and it was in nobody's list of
blockers.

So this feature is now exactly 1 thing: the `x/text` bump for GO-2026-5970 in the
libraries that carry it.

**Also required, outside this worktree:** eden's `go.work` toolchain directive
moves 1.26.4 -> 1.26.5, because leaving the workspace floor behind permits a
vulnerable toolchain to build Eden even after the image is fixed. That is an eden
change and it follows the base image publish.

## Proven

- The advisories come from eden's affected-gate on gophersys/eden#7, where the
  failed tasks were forge:vuln, secrets:vuln, platformgateway:vuln,
  orchestrator:vuln and objectstorage:vuln.
- Nothing else is proven yet. The planner was told to run govulncheck itself and
  not to trust that second-hand summary, including whether each advisory is
  REACHABLE rather than merely present in a dependency.

## Blocked

Nothing. The 2 out-of-repo pieces are sequenced, not blocking: the Go bump ships
with drop-arm64, and eden's go.work follows the image publish.

## Next

Phase 2: prove the x/text advisory red before the bump.
