# smoke-v2

phase:    red
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
(nothing yet)

## Blocked
Landing blocked by #98 (lever PR touches .ci/smoke.sh; it merges first, then
this branch rebases). Test authoring is NOT blocked.

## Next
dev-test-author writes the 4 red tests and PROVES each fails for the right
reason: version-coverage.test.sh, smoke-contract.test.sh, guest-checks.test.sh,
publish-order.test.sh (UNSMOKED_TODAY emptied) + stub docker extensions.
