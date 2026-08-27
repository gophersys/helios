# base-cloud-foundation

phase:    plan
repo:     gophersys/.devcontainer
branch:   perf/base-cloud-foundation
worktree: ~/code/.worktrees/devcontainer-base-cloud-foundation
pr:       -
attempt:  0/2

## Goal
Make base and cloud the fast, stable dual-architecture foundation: prove warm ARM64 inline-cache reuse, minimize rebuilds to true inputs, isolate stable tool families for cache reuse, and leave one short authoritative explanation of the design and measured costs.

## Plan
plan: SELF-APPROVED — the risk is optimizing Dockerfile shape without reducing wall time; every structural change must be justified by cold/warm layer timings and a real CI proof.

1. Extract per-platform and per-layer timings from the repaired cold run and record the baseline outside generated workflow prose.
2. Prove the newly published inline cache with a warm dual-architecture build that ships nothing; fail if ARM64 repeats expensive installation layers.
3. Tighten affected-input contracts so base changes only for its Dockerfile, pinned versions, shared build scripts, and actual generator inputs; cloud consumes the immutable base output without rebuilding base for cloud-only edits.
4. Restructure base into independently cached system, Go, Node-agent, and Python tool families where the measured invalidation chain currently couples unrelated pins.
5. Delete obsolete cache topology and documentation residue; keep one concise architecture decision and operational timing table.
6. Run local devcontainer gates, a real warm CI proof, Codex review, cleanup, and merge. Report cold and warm costs in minutes.

## Proven
- Repaired run `33118737619` completed green. Base retry job `98687483042`: total 19m13s; AMD64 gate 9m07s; smoke 9s; dual-arch publish 8m38s; manifest verification 43s. Cloud: total 20m07s; gate 10m46s; publish 7m27s; verify 1m07s.
- ARM64 worker ended the successful cold publish without disk exhaustion after infrastructure PR #212 established named state and bounded GC.

## Blocked


## Next
Download the successful job logs and extract per-platform layer timing and cache-hit evidence.
