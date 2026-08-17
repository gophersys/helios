# arc-build-pool

phase:    submit
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

## Proven (full round)
- RED (bd0408c): 3+6 fixture cases, 18 assertion-failures for the right
  reasons (incl. a 1-arg call DELETING+APPLYING a cluster Job before
  refusing). GREEN (6 commits to acc1268): 0 failures both suites; all
  local gates rc=0; validate.yml runs both suites.
- Cloud digest 9a150cbf... pinned (index) in all 3 pools; verified live:
  ctl.sh verify-runner-image cloud 997bb6b -> 21/21 in the real pod shape;
  docker probe proved uid=1000 default (runAsUser:0 = requirement); helm
  server-side dry-runs clean ×3 (field-manager lesson recorded).
- test-lint-shell caught the implementer's own live backtick-in-heredoc
  bug mid-work — the suite fired in anger before ever merging.
- MERGED ON LOCAL GATES per Mateo's session directive (remote validate
  confirms post-merge, free on arc-org).

## Next
Argo syncs on merge -> pools restart on cloud. Watch one validate run
prove the repointed arc-org live. Then PR 2 (.devcontainer).
