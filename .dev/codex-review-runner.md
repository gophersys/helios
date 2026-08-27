# codex-review-runner

phase:    pr
repo:     gophersys/infrastructure
branch:   fix/codex-review-runner
worktree: ~/code/.worktrees/infrastructure-codex-review-runner
pr:       -
attempt:  0/2
plan:     SELF-APPROVED — deploy only the isolated review pool; changing general build pools before the review bootstrap is proven expands blast radius without helping the dependency cycle.

## Goal
The ARC pools run the immutable cloud image that passed the Codex 0.150.1 smoke test, so cictl can invoke the supported strict configuration without mutating runner pods at runtime.

## Plan
Replace every declared ARC/warmer pin home with the same immutable cloud digest. The initial review-only slice was revised after RED proved `verify-warmer-pins` deliberately requires one digest across three pool files and two warmer files; weakening that invariant would create a special-case pin and cold-pull gap. Prove the old live runner reports Codex 0.146.0, run the repository pin/manifest gates, merge through GitOps, wait for Argo sync, and exercise a real review job. Exclude cictl behavior and secret changes. This deploys agent infrastructure but does not change canonical Claude/Codex instrumentation.

## Proven
- RED — live `arc-review` on the old immutable runner image reached cictl but `codex` rejected `view_image`; earlier immutable-image probe reported `expected=0.150.1 actual=0.146.0`.
- Published source artifact — `.devcontainer` run `33103358791` completed cloud publish/manifest verification for head `26be3354`; `ghcr.io/gophersys/cloud:26be335` resolves to `sha256:359334d77d8fee3372fa9672be37f04d121bc294426622ae3d5161e90b9d2a0c`.
- RED — review-only pin change: `bash ctl.sh verify-warmer-pins` failed with `the files disagree on the cloud digest — a pin bump missed a home` (1 new versus 4 old file-level homes).
- GREEN — all declared pin homes updated: `bash ctl.sh verify-warmer-pins` reported one digest across 3 pool files + 2 warmer files, no privilege, and 3 control-plane nodes excluded.
- `bash ctl.sh verify-registry`: 18 checked, 1 external-chart skip, 0 failures.
- `bash ctl.sh validate`: 6 project files parsed, 35 shell scripts linted, `validate: OK`.
- `bash ctl.sh verify-runner-image cloud 26be335`: the real ARC+dind pod shape passed all checks, including root/gid 123, Docker API and container run, toolchain, sudo, and `run.sh` readiness.

## Blocked


## Next
Push the promotion PR, obtain independent review, and use a bounded live review-pool canary to break the old-runner review bootstrap cycle.
