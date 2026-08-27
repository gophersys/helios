# promote-cloud-4b42d5b

phase: green
repo: gophersys/infrastructure
branch: chore/promote-cloud-4b42d5b
worktree: ~/code/.worktrees/infrastructure-promote-cloud-4b42d5b
pr: -
attempt: 0/2

## Goal

Promote the verified base/cloud fast-path runner image from `.devcontainer`
commit `4b42d5b` into every ARC cloud pin without changing credentials, scheduling,
or mutable runtime state.

## Plan

plan: SELF-APPROVED — update the existing digest homes atomically and use the
repository's pin verifier plus manifest validation. Opening the GitOps PR is
safe; merging/deploying it remains a distinct production rollout decision.

Published source: `ghcr.io/gophersys/cloud:4b42d5b`
Verified index digest: `sha256:470a117514e6d1ab23ab937b46e0fabe087ffdb1cd39b4345cfa3aa25a194a8a`

## Proven

- RED — all five GitOps homes still resolved to the previous cloud index
  `sha256:359334d...d2a0c`, not the newly published digest.
- GREEN — nine references across the three ARC pools and two warmer resources
  now resolve to `sha256:470a117...194a8a`.
- GREEN — warmer pin coherence, immutable DinD pinning, and full infrastructure
  validation pass locally.


## Blocked


## Next

Open the promotion PR and let remote validation run. Do not merge until the
GitOps rollout is explicitly authorized.
