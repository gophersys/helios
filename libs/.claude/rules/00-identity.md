# Repository Identity — gophersys/libs

## Purpose

`gophersys/libs` is the shared-library submodule consumed by every
project monorepo in the brain ecosystem. It hosts reusable libraries
grouped by implementation language:

- `go/`         — Go libraries (16), the bulk of the repository
- `typescript/` — TypeScript / Node libraries (4), the `@eden/*` scope

Those two are the whole list, and `LANG_SUBTREES` in the top-level
`ctl.sh` is its one home. `python/`, `rust/`, `zephyr/` and `protocols/`
were described here as though they held libraries; each held a single
`.gitkeep` and they were removed. A subtree is created when a library
lands in it — not in advance of one.

This repository is authored inside the brain meta-monorepo at
`brain/shared/libs/` and is also published standalone as
`github.com/gophersys/libs` for consumption as a git submodule from each
project monorepo under `projects/<p>/shared/libs/`.

## Boundary

A library belongs in `libs/` only if it is:

1. **Reusable** across more than one project monorepo, and
2. **Domain-independent** (not tied to a single product's business logic).

Product-specific code — even if shared across multiple applications
within the same project — stays inside that project's monorepo under
`projects/<p>/shared/`, not here.

## Authoring contract

Every library directory under a language subtree (`<lang>/<lib-name>/`)
follows the `development-nx-run-command` pattern:

- Exactly two files in the library root drive all tooling:
  - `project.json` — Nx wiring; targets are `nx:run-commands` wrappers
    that delegate to `bash ./ctl.sh`.
  - `ctl.sh` — bash source of truth for every verb (`build`, `test`,
    `lint`, etc.). Must be `chmod +x`.
- `ctl.sh` MUST pass `shellcheck` cleanly and use `set -Eeuo pipefail`.
- Verbs are uniform across a subtree (e.g. every Python lib has
  `build | test | lint | typecheck | publish`), so a consumer can invoke
  `nx run <lib>:test` without reading source.

See `brain/.claude/skills/development-nx-run-command/` for the full
authoring recipe.

## Commit identity

**ATTRIBUTION IS IDENTITY** (Mateo, 2026-08-25). This section previously
required every commit to be authored `Mateo Segura` and forbade AI attribution
"of any kind". That ruling has been **REVERSED** and this text is superseded by
`eden/.claude/rules/git-process.md` §13, which is the single home for the rule.
The reason for the reversal: an unattributed agent commit reads as a human's,
and that is a false record.

- **Solo agent work** is authored `Claude <claude-agent@gophersys.noreply>`,
  with no trailer.
- **Joint interactive work** is authored Mateo, with a `Co-Authored-By: Claude`
  trailer.
- **An agent NEVER commits, approves or comments as "Mateo."** An agent's pull
  request comment identifies itself and names the authority it acts under.
- These govern the git **author** field only. The **committer** stays the human
  account whose credential pushes, because an agent has no GitHub identity yet —
  so a commit today honestly reads `author=Claude`, `committer=Mateo Segura`.

Where this file and `git-process.md` §13 ever disagree, **§13 wins**: the later
process supersedes the earlier one, and the rule lives in one home, not two.

Commit messages follow Conventional Commits; subject lines are imperative,
≤72 chars, no trailing period.
