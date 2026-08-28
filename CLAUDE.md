# Eden agent entrypoint — Claude Code

Read [`docs/engineering/README.md`](docs/engineering/README.md) before changing
the repository. Its machine-readable contract is
[`docs/engineering/system.json`](docs/engineering/system.json).

## Work here

- Eden is the deployable product and the organization workspace. Libraries,
  infrastructure, tools, research, and development images live here directly.
- Use the nearest named process when it is active. Until then, use the existing
  `ctl.sh` and Nx targets and record the proof you actually ran.
- Work in an isolated Git worktree. Preserve uncommitted and unpublished work.
- Use Conventional Commits and the real agent identity. Never impersonate Mateo
  or another harness.
- Run development and CI commands inside the pinned devcontainer unless a
  repository command explicitly says otherwise.
- Never commit secrets. Eden uses declared secret references and external
  secret stores.
- Prefer small vertical slices. Do not create parallel implementations of an
  existing concept; cite its canonical home.

## Claude Code adapter

- `CLAUDE.md` contains only always-loaded routing and safety guidance.
- Reusable workflows belong in `.claude/skills/`; mechanical checks belong in
  hooks, scripts, linters, or `ctl.sh`.
- Use subagents or agent teams only for independent work with explicit
  ownership. Each writing agent gets its own worktree.
- Existing `.claude/rules/` remain compatibility inputs until each rule is
  promoted to a process or mechanical gate.
