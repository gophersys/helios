# container-nx-workflow

phase:    plan
repo:     gophersys/eden
branch:   feat/container-nx-workflow
worktree: /Users/mateo/code/.worktrees/eden-container-nx-workflow
pr:       -
attempt:  0/2

## Goal

Make `devcontainer cloud` the single host entry into Eden, with Codex authenticated,
then make Nx the only developer and agent workflow interface inside the container.

## Plan

Add a small delegating devcontainer shim, persistent container-side Codex credentials
seeded from the host, and one canonical Eden `dev` skill shared by the Codex and Claude
adapters. Prove the shim contract without building an image, then smoke-test the real
installed entrypoint against the existing cloud image.

plan: SELF-APPROVED — the main risk is shadowing the upstream CLI, mitigated by passing
every command except the explicit Eden `cloud` extension straight through unchanged.

## Proven


## Blocked


## Next

Write and run the failing entrypoint contract test.
