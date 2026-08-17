# smoke-v2

phase:    green
repo:     gophersys/.devcontainer
branch:   ci/smoke-v2
worktree: ~/code/.worktrees/.devcontainer-smoke-v2
pr:       -
attempt:  0/2

## Goal
Every pin in versions.env and the base-family ARGs is version-asserted in the
smoke, gate-critical tools are exercised on real fixtures, pnpm is pinned, and
all 6 images smoke before they publish. Mateo's words: "check that the tools do
indeed work, and that also the version is correct" — local and CI 1:1.

## Plan
Approved by the orchestrator under standing-orders §4 delegation (Mateo away),
2026-08-16. Full plan: tasks/ade4d1687e00d6aec.output (planner run). Shape:
- .ci/smoke.sh becomes the HOST driver: one generic resolve_pin reading BOTH
  pin homes (versions.env + base/Dockerfile ARGs), per-image classification,
  fixture embedding via stdin, one docker run.
- .ci/image-checks.sh (new): GUEST comparator + tiered functional checks.
- .ci/fixtures/: go/{go.mod,main.go}, Dockerfile, compose.yaml, echo.proto,
  buf.yaml (~40 lines total).
- versions.env +PNPM_VERSION; cloud+base Dockerfiles corepack pnpm@latest ->
  @${PNPM_VERSION}.
- Both build-and-push.yml copies: base/flutter/zephyr/zephyr-devbox get
  push:false+load:true -> smoke -> push-from-cache (the cloud/base-runner
  shape). publish-order.test.sh UNSMOKED_TODAY -> empty.
- 3 commits: engine+pnpm | functional checks+fixtures | workflow gating.
Key risks recorded by the planner: per-tool version-string formats (per-row
extractor, empty match FAILS); zsh ZSH_VERSION collision (table var, prefix
compare for apt pins); delve needs ptrace (a denial FAILS — demotion is
Mateo's call); golangci-lint with GOPROXY=off; heredoc delimiter assertion;
runtime delta estimated +4-8 min per newly gated image, measured on first
main run.

## Proven
- RED (2026-08-16, commit 7b82fe7): `bash ./ctl.sh test` exits 1 with exactly
  the 4 intended red files — version-coverage 6/19 failed, smoke-contract
  12/15, guest-checks 7/8, publish-order 2/28 (baseline 28/0) — and every
  other suite at its baseline. Each red was proven to fail for the feature's
  reason (missing SMOKE_LIST_PINS listing, argv-not-stdin payload, absent
  .ci/image-checks.sh (127), 4 jobs publish with a bare push:true).
  Counter-stimulus checks (FOO_VERSION append, GH_VERSION delete, dual-class,
  off-taxonomy class) all watched to fire. shellcheck -x -S style rc=0.
  `bash ./ctl.sh validate` rc=0.
- Test-author note recorded: 3 draft checks originally asserted non-zero
  status alone and PASSED on 127 — rewritten to demand status AND names.

## Seams (the tests define them; the implementer builds them)
1. `SMOKE_LIST_PINS=1 bash .ci/smoke.sh <image>` prints `<NAME>|<class>` per
   pin, exits 0, calls docker not once. Classes: asserted | not-a-version |
   not-in-this-image. Pin home: cloud -> versions.env; base family ->
   base/Dockerfile version-shaped ARGs.
2. `.ci/image-checks.sh` reads rows `<PIN>|<expected>|<command>[|extractor]`
   from the PIN_TABLE environment variable (script text travels on stdin).
3. The guest payload names itself `image-checks.sh`. No VERSIONS_ENV override
   seam — smoke.sh derives its root from its own location.

## Blocked
Landing blocked by #98 (lever PR touches .ci/smoke.sh; it merges first, then
this branch rebases). Test authoring is NOT blocked.

## Next
dev-test-author writes the 4 red tests and PROVES each fails for the right
reason: version-coverage.test.sh, smoke-contract.test.sh, guest-checks.test.sh,
publish-order.test.sh (UNSMOKED_TODAY emptied) + stub docker extensions.
