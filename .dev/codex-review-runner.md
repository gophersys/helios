# codex-review-runner

phase:    plan
repo:     gophersys/infrastructure
branch:   fix/codex-review-runner
worktree: ~/code/.worktrees/infrastructure-codex-review-runner
pr:       -
attempt:  0/2
plan:     SELF-APPROVED — deploy only the isolated review pool; changing general build pools before the review bootstrap is proven expands blast radius without helping the dependency cycle.

## Goal
The `arc-review` pool runs the immutable cloud image that passed the Codex 0.150.1 smoke test, so cictl can invoke the supported strict configuration without mutating runner pods at runtime.

## Plan
Replace both review-pool image homes (runner and externals init container) with the same immutable cloud digest. Prove the old live runner reports Codex 0.146.0, run the repository pin/manifest gates, merge through GitOps, wait for Argo sync, and exercise a real review job. Exclude `arc-org`, `arc-build`, image-warmer policy, cictl behavior, and secret changes. This deploys agent infrastructure but does not change canonical Claude/Codex instrumentation.

## Proven
- RED — live `arc-review` on the old immutable runner image reached cictl but `codex` rejected `view_image`; earlier immutable-image probe reported `expected=0.150.1 actual=0.146.0`.
- Published source artifact — `.devcontainer` run `33103358791` completed cloud publish/manifest verification for head `26be3354`; `ghcr.io/gophersys/cloud:26be335` resolves to `sha256:359334d77d8fee3372fa9672be37f04d121bc294426622ae3d5161e90b9d2a0c`.

## Blocked


## Next
Change the two `arc-review` image references and run the narrow pin checks.
