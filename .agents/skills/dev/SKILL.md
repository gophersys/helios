---
name: dev
description: Develop, test, review, and deliver changes in Eden through its cloud devcontainer and Nx project targets.
---

# Eden development

## Boundary

The host has one job: from the Eden checkout, run `devcontainer cloud`. Do all
repository work inside that container. Once inside, use Nx as the public task
interface; do not ask a developer or agent to invoke `ctl.sh` directly.

Use this command shape:

```text
nx <verb> <project> [-c <configuration>]
```

Prefer the shared verbs `start`, `stop`, `check`, `test`, `build`, `review`,
`publish`, and `deploy`. Use `local`, `staging`, or `production` configurations
when environment behavior differs. A project may implement a target with a small
script or tool, but that implementation is private behind Nx.

## Work

1. Read `AGENTS.md`, `CLAUDE.md`, and `docs/engineering/system.json`.
2. Create an isolated worktree and branch from the current remote default branch.
3. Define the smallest vertical slice and its observable proof.
4. Prove the missing behavior fails, implement it, and prove it succeeds through
   the narrowest relevant Nx target.
5. Use `nx affected` before broad repository work. Run expensive builds only when
   narrower evidence cannot cover the risk.
6. Keep scripts short and project-local. If an action is reusable, implement it in
   a library or tool and expose it through an Nx target.
7. Commit with Conventional Commits, open a pull request, read the actual checks
   and review output, then merge only proven work.

## Agents and CI

Local developers, Codex, Claude, CI runners, and remote agents use the same image
and Nx targets. Harness adapters may explain discovery differences, but may not
define a second development process. Never place credentials in the repository,
Nx configuration, command arguments, or committed environment files.

## Stop conditions

Ask before deployments, releases, secret-store mutations, destructive cleanup,
or an operation expected to exceed ten minutes. A missing tool or credential is a
failure, not permission to fall back to a host implementation.
