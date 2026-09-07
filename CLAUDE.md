# Eden agent entrypoint — Claude Code

Read [`docs/README.md`](docs/README.md) and [`.eden/model.json`](.eden/model.json)
before changing the repository.

## Work here

- Eden starts as a framework-neutral Nx workspace. Add applications, libraries,
  tools, and infrastructure only when a concrete slice needs them.
- Enter from the host with `devcontainer cloud`, then use Nx for every public
  development action. Read [`.claude/skills/dev/SKILL.md`](.claude/skills/dev/SKILL.md)
  when changing the repository. `ctl.sh` is a private Nx implementation detail.
- Work in an isolated Git worktree. Preserve uncommitted and unpublished work.
- Use Conventional Commits and the real agent identity. Never impersonate a
  user or another harness.
- Run development and CI commands inside the pinned devcontainer unless a
  repository command explicitly says otherwise.
- Never commit secrets. Eden uses declared secret references and external
  secret stores.
- Prefer small vertical slices. Do not create parallel implementations of an
  existing concept; cite its canonical home.

## Claude Code adapter

- `CLAUDE.md` contains only always-loaded routing and safety guidance.
- Reusable workflows belong in `.claude/skills/`; mechanical checks belong in
  Nx targets backed by small scripts or tools.
- Use subagents or agent teams only for independent work with explicit
  ownership. Each writing agent gets its own worktree.
