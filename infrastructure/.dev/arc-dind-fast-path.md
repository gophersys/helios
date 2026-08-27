# arc-dind-fast-path

phase: green
repo: gophersys/infrastructure
branch: fix/arc-dind-fast-path
worktree: ~/code/.worktrees/infrastructure-arc-dind-fast-path
pr: -
attempt: 0/2

## Goal

ARC jobs remain isolated and run their work inside the declared devcontainer,
while Docker-in-Docker starts reliably and avoids downloading the same large job
image from an empty cache on every run.

## Plan

plan: SELF-APPROVED — persistent mutable Docker state shared across concurrent jobs
would improve cache hits but weaken isolation and risk corruption. Prefer a bounded,
immutable preload/cache design attached to each ephemeral runner, with digest pins,
readiness checks, resource limits, and a measured startup assertion. Prove the current
pod template has no usable nested-daemon cache before implementing the smallest safe
shared home across ARC pools.

Affected layer: platform/services/ci/arc-runners plus its GitOps values and focused
verifiers. Excluded: secrets, runner credentials, application workflows, and manual
production mutation until the Git change has passed review and deployment is separately approved.

## Proven

- RED — `bash scripts/test-verify-dind-pins.sh`: the repository had no verifier
  and every ARC DinD home used the moving `docker:dind` tag.
- GREEN — org, build, warmer, and runner verification pods all pin Docker DinD
  29.7.2 by one immutable multi-platform index digest. The CI verifier rejects
  a missing, floating, divergent, or duplicate ref before GitOps can merge it.


## Blocked


## Next

Run repository validation, then open the PR. Deployment remains a separately
approved GitOps operation.
