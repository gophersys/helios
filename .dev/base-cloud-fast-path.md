# base-cloud-fast-path

phase: intake
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


## Blocked


## Next

Inventory the manifest/generator and write the failing enabled-set and startup-cost policy tests.
