# base-cloud-fast-path

phase: green
repo: gophersys/.devcontainer
branch: ci/base-cloud-fast-path
worktree: ~/code/.worktrees/devcontainer-base-cloud-fast-path
pr: -
attempt: 0/2

## Goal

Make `base` and `cloud` the only active image products while retaining the other
image declarations in an explicitly disabled state. Dev and CI containers carry
all slow or stable tools; startup may install only intentionally volatile inputs
whose measured cold p90 is below 10 seconds.

## Plan

plan: SELF-APPROVED — disabling four currently unnecessary products greatly
reduces build fan-out, but deleting their definitions would make reactivation
needlessly destructive; keep one manifest-level enable switch and make generated
workflows honor it. Add a policy gate that rejects slow/unbounded startup installs
and prove both enabled-set and startup-policy checks red before implementation.
Build/publish only after targeted and repository gates establish the affected set.

Affected: image manifest, workflow generator, generated provider workflows,
startup scripts, and focused policy tests. Excluded: deleting dormant image source,
changing application code, cluster rollout, and runtime secrets. Agent setup changes
must retain both Claude and Codex pins in the shared image contract.

## Proven

- RED — `bash _ctl/tests/activation-policy.test.sh`: 4 checks, 3 failed; `active_image_names` was absent and all six manifest rows lacked an explicit boolean `enabled` field.
- RED — `bash _ctl/tests/startup-policy.test.sh`: 5 checks, 5 failed; Base startup contained the Claude curl installer and two global npm installs, while Base declared none of the three harness pins and never ran the shared agent bake.
- GREEN — manifest activation is explicit: base/cloud active; mobile, embedded,
  hardware, and ui retained but operationally rejected. Generated publish and
  nightly workflows fan out only over the active set.
- GREEN — Base bakes pinned Claude, OMP, and Codex through the shared component;
  post-create is offline and verifies those baked versions instead of installing.
- GREEN — focused activation/smoke/startup checks: 54 checks, 0 failures.
- GREEN — repository policy suite: every feature-affected test passes. The sole
  remaining full-suite failure is the pre-existing host yq 4.53.3 diagnostic
  spelling (`line 45` versus pinned 4.53.6's `L45.C5`); the devcontainer gate
  runs the pinned tool.

## Blocked


## Next

Commit, push, open the PR, then run the pinned devcontainer gate before any
base/cloud build preflight.
