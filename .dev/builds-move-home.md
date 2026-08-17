# builds-move-home

phase:    submit
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
- Prereq: infra #184 merged; pools live on cloud digest (kubectl verified).
- RED reproduced on pre-impl tree: 21 feature reds (+3 git-archive artifacts).
- GREEN: 19 files, 560 checks, 0 failed; yq ×8; cmp ×3 pairs byte-identical;
  BUILD_ORDER agreement by hand.
- affected.sh EXECUTED on 9 controlled commits — all answers correct (docs
  → nothing; base → base+3 children; _delta → cloud; versions.env → all;
  dispatch/tag/no-payload/zero-sha → build-all; unknown image rc 2).
- buildx-node.sh drilled on 6 worlds incl. the exact mTLS remote-driver
  line of ci-substrate.md:390; arm64-inert proven.
- Context-availability audit caught the implementer's own job-level
  runner.temp (GitHub would reject the workflow) — moved to step env.
- 64 ratchet checks (test author 32fdd41): no billed runner ever, bounded
  scheduled matrices, declaration-driven retirement, filter coherence,
  8 mutation drills.
- KNOWN HOLE, documented in the workflow header: event.before diffs the
  previous PUSH not the last successful BUILD (cancelled/failed runs can
  skip a change); escape hatch = re-run/dispatch; durable fix recorded
  (diff from the registry's image revision label).
- MERGED ON LOCAL GATES per the session directive; the first arc-build run
  is the live proof.

## Blocked
(nothing)

## Next
Parallel: test author (no_billed_runner + free-disk ratchet, bounded
scheduled matrix, BUILD_ORDER/publish-order coherence at 5 images,
affected-filter coherence) ∥ implementer (everything else). Merge on local
gates; the first arc-build run is the live proof; #51 lands after.
