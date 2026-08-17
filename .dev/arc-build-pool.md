# arc-build-pool

phase:    red
repo:     gophersys/infrastructure
branch:   feat/arc-build-pool
worktree: ~/code/.worktrees/infra-arc-build
pr:       -
attempt:  0/2

## Goal
A second ARC scale set `arc-build` (additive — arc-org untouched) runs the
image builds on the homelab: cloud image at a pinned sha, minRunners 0 /
maxRunners 6, nodeAffinity to the three 14Gi pve-00 workers, work sizeLimit
20Gi, runAsUser 0 (cloud ends USER dev; a 0400 root-owned key.pem would be
unreadable). PR 1 of the everything-moves-home migration (#96); PR 2 moves
the three workflows. Trigger: 1805/2000 hosted minutes, $0 budget.

## Plan
Approved under §4 delegation with the blocking question ANSWERED BY
MEASUREMENT: pve-00 thin pool = 816GB at 29.15% used (~578GB free; lvs run
2026-08-17) -> maxRunners 6 with 30Gi dind limits is safe. Partition
framing confirmed over single-pool-12: blast-radius isolation (a broken
build pool cannot starve validate/review). Full plan:
tasks/a878064c01c0a3994.output. Files: app-arc-runners-build.yaml (new,
from app-arc-runners-org.yaml), 41-image-warmer-config.yaml (+cloud:latest),
verify-runner-image.sh (repo as arg 1), verify-buildx-key.sh (mode-vs-user
assertion), docs rows + the stale no-buildx claim corrected. Preconditions
before merge: manifest inspect + smoke-passed sha + verify-runner-image
cloud <sha> + helm-template dry-run per ci-runners.md. Deferred: dind/
buildkit digest pins, cache backend change, mini-as-macOS-runner (grounded:
not on tailnet, no runtime, nothing consumes iOS artifacts), arc-org
changes, SANCTIONED widening.

## Proven
- pve-00 thin pool measured: data 816.21g at 29.15% (the plan's blocking
  question) — maxRunners 6 / 30Gi dind limit approved on that number.

## Blocked
(nothing)

## Next
dev-test-author: fixture reds — test-verify-runner-image.sh (the verifier
reports the repository it was asked about; red while IMAGE_REPO is the
hardcoded base-runner constant) + the verify-buildx-key mode-vs-user case
(a runner container without runAsUser:0 + a 0400 root-owned secret = FAIL;
red while the assertion is absent).
