# noninteractive-container-start

phase: pr
repo: gophersys/eden
branch: fix/noninteractive-container-start
worktree: /Users/mateo/code/.worktrees/eden-noninteractive-container-start
pr: -
attempt: 0/2

## Goal

Ensure `devcontainer cloud` never pauses for Corepack confirmation.

## Plan

Declare Corepack's non-interactive environment at the container boundary and prove
the devcontainer contract exposes it. plan: SELF-APPROVED — no behavior changes
beyond suppressing an installation prompt.

## Proven

- RED: `bash .devcontainer/test-entrypoint.sh` exited 1 with `Corepack download prompt is not disabled`.
- GREEN: the same command printed `devcontainer entrypoint contract: PASS`.
- `jq empty`, ShellCheck style, and `git diff --check` exited 0.

## Blocked


## Next

Submit and merge the focused fix.
