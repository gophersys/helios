# builds-move-home

phase:    red+green (speed mode, parallel authoring)
repo:     gophersys/.devcontainer
branch:   ci/builds-move-home
worktree: ~/code/.worktrees/.devcontainer-builds-home
pr:       -
attempt:  0/2

## Goal
PR 2 of everything-moves-home: build-and-push/security-nightly/weekly-bumps
run on arc-build (the pool is live, infra #184 merged, pools on the cloud
digest); free-disk steps deleted; buildx registry cache on ghcr; affected-
only builds (Mateo's #78: "optimize now" — warm 35m unacceptable);
base-runner RETIRED (no consumer since the pools repointed): out of
BUILD_ORDER ×2, workflows ×2 copies, smoke, nightly matrix, docs; the mini
arm64 buildx node wired inert behind SANCTIONED_PLATFORMS (.ci/
buildx-node.sh); ghcr base-runner package archived after merge. Session
directive: merge on local gates.

## Plan
The migration plan (tasks/a878064c01c0a3994.output §.devcontainer half)
+ #78's three levers + the base-runner retirement unlocked by infra #184.

## Proven
- Prereq: infra #184 merged; pools pinned to cloud digest 9a150cbf...;
  verify-runner-image cloud 997bb6b 21/21 live.

## Blocked
(nothing)

## Next
Parallel: test author (no_billed_runner + free-disk ratchet, bounded
scheduled matrix, BUILD_ORDER/publish-order coherence at 5 images,
affected-filter coherence) ∥ implementer (everything else). Merge on local
gates; the first arc-build run is the live proof; #51 lands after.
