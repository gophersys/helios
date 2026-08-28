# container-nx-workflow

phase:    pr
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

- RED: `.devcontainer/test-entrypoint.sh` exited 1 with `missing executable scripts/devcontainer`.
- GREEN: `bash .devcontainer/ctl.sh test` printed `devcontainer entrypoint contract: PASS`.
- `shellcheck -S style scripts/devcontainer .devcontainer/ctl.sh .devcontainer/post-start.sh .devcontainer/test-entrypoint.sh` exited 0.
- `jq empty .devcontainer/devcontainer.json` and `git diff --check` exited 0.
- `devcontainer up --workspace-folder <worktree>` completed in 22.5 seconds using the existing image; the cold workspace dependency install took 19.1 seconds.
- Inside the container, `nx test devcontainer` completed successfully and printed `devcontainer entrypoint contract: PASS`.
- Inside the container, `codex login status` printed `Logged in using ChatGPT`.
- `uv run --with pyyaml .../quick_validate.py` printed `Skill is valid!` for both `.agents/skills/dev` and `.claude/skills/dev`.

## Blocked


## Next

Push the branch and open the pull request.
