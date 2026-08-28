# Eden agent entrypoint — Codex

Read [`docs/engineering/README.md`](docs/engineering/README.md) before changing
the repository. Its machine-readable contract is
[`docs/engineering/system.json`](docs/engineering/system.json).

## Work here

- Eden is the deployable product and the organization workspace. Libraries,
  infrastructure, tools, research, and development images live here directly.
- Enter from the host with `devcontainer cloud`, then use Nx for every public
  development action. Read [`.agents/skills/dev/SKILL.md`](.agents/skills/dev/SKILL.md)
  when changing the repository. `ctl.sh` is a private Nx implementation detail.
- Work in an isolated Git worktree. Preserve uncommitted and unpublished work.
- Use Conventional Commits and the real agent identity. Never impersonate Mateo
  or another harness.
- Run development and CI commands inside the pinned devcontainer unless a
  repository command explicitly says otherwise.
- Never commit secrets. Eden uses declared secret references and external
  secret stores.
- Prefer small vertical slices. Do not create parallel implementations of an
  existing concept; cite its canonical home.

## Codex adapter

- `AGENTS.md` contains only always-loaded routing and safety guidance.
- Reusable workflows belong in `.agents/skills/`; mechanical checks belong in
  hooks, scripts, linters, or `ctl.sh`.
- Use subagents only for independent work with explicit ownership. Each writing
  agent gets its own worktree.
