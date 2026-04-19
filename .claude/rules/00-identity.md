# Repository Identity — gophersys/libs

## Purpose

`gophersys/libs` is the shared-library submodule consumed by every
project monorepo in the brain ecosystem. It hosts reusable libraries
grouped by implementation language plus a language-agnostic protocol
layer:

- `typescript/` — TypeScript / Node libraries
- `python/`     — Python libraries
- `rust/`       — Rust crates
- `zephyr/`     — Zephyr RTOS modules and subsystems
- `protocols/`  — schema and protocol definitions (protobuf, JSON Schema,
  OpenAPI, etc.) that generate bindings into the language subtrees

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

All commits in this repository MUST be authored by:

- **Name:** `Mateo Segura`
- **Email:** `mateo.segura413@gmail.com`

Configure via repo-local `git config user.name` / `user.email` when
cloning fresh. Commit messages follow Conventional Commits; subject
lines are imperative, ≤72 chars, no trailing period. Commit messages
MUST NOT contain AI / LLM / assistant attribution of any kind.
