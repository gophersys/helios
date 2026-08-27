# inline-publish-cache

phase: green
repo: gophersys/.devcontainer
branch: perf/inline-publish-cache
worktree: ~/code/.worktrees/devcontainer-inline-cache
pr: -
attempt: 0/2

## Goal

Remove the redundant registry-cache upload from image rebuilds while preserving
warm final-stage cache hits through cache metadata embedded in the images that
the publish step already uploads.

## Plan

plan: SELF-APPROVED — all managed Dockerfiles are single-stage, so the final
published image contains every reusable layer. Make each gate and rehearsal read
the published `:latest`, make the publish build export an inline cache, and hold
that topology in a hermetic generator test. Do not dispatch an image build until
Mateo approves its measured preflight.

## Proven

- RED — run 33113679068 spent 442.0 seconds exporting `base-cache` under
  `mode=min`; two layer uploads alone took 265.6s and 315.1s.
- RED — the current generator writes a separate registry cache during the gate
  build and writes no inline cache during the image publish.
- GREEN — generated CI has one `type=inline` export per enabled publish job,
  three `<image>:latest` readers per job, and zero `*-cache` references.
- GREEN — `bash ./ctl.sh validate` passes in the pinned cloud image.
- GREEN — all 29 hermetic test files pass in the pinned cloud image.
- GREEN — GHCR contains only `base`, `cloud`, and `buildkit`; the other 18
  packages were deleted under Mateo's explicit authorization.

## Blocked


## Next

Commit, open the pull request, and run the lightweight remote gates. Present a
base/cloud cold-build preflight before merging.
