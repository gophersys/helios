# gophersys/libs

Shared-library submodule consumed by every project monorepo in the
brain ecosystem. Libraries are grouped by implementation language, with
a language-agnostic protocol layer that generates bindings into each
language subtree.

## Layout

```
libs/
├── typescript/   # TypeScript / Node libraries
├── python/       # Python libraries
├── rust/         # Rust crates
├── zephyr/       # Zephyr RTOS modules and subsystems
├── protocols/    # schemas (protobuf, JSON Schema, OpenAPI, ...) → bindings
├── project.json  # repo-wide Nx meta-targets (status, validate, propagate)
└── ctl.sh        # repo-wide control script (bash source of truth)
```

Each language subtree has its own `README.md` describing the expected
library layout, verbs, and cache policy for that language.

## Consumption model

This repository is authored inside the brain meta-monorepo at
`brain/shared/libs/` and is also published standalone as
`github.com/gophersys/libs`. Each project monorepo consumes it as a git
submodule at `projects/<p>/shared/libs/`, pinning a specific commit.

Consumers never depend on loose files — they consume published
libraries:

- A project's TypeScript app imports from `@gophersys/<lib>` (npm) or
  references `shared/libs/typescript/<lib>` by path.
- A firmware project's `west.yml` references `shared/libs/zephyr/<mod>`
  by path.
- Generated bindings from `protocols/` are re-exported through the
  matching language subtree's wrapper libraries.

## Authoring contract

Every library under a language subtree follows the
`development-nx-run-command` skill. The authoring rules are brief:

1. Exactly two files in the library root: `project.json` + `ctl.sh`
   (plus whatever the language manifest requires, e.g. `Cargo.toml`,
   `pyproject.toml`, `package.json`).
2. `project.json` targets are all `nx:run-commands` wrappers that
   delegate to `bash ./ctl.sh <verb>`. No logic lives in `project.json`.
3. `ctl.sh` is the bash source of truth. It MUST:
   - Start with `set -Eeuo pipefail`
   - Pass `shellcheck` cleanly
   - Be `chmod +x`
   - Answer `bash ./ctl.sh help` with one indented line per verb, and
     those verbs must match the `project.json` targets (drift is
     enforced by running `help`, not by reading the source — see
     `validate` below)
4. Verbs are consistent per subtree so consumers can invoke
   `nx run <lib>:<verb>` without reading source. Per-subtree verb
   catalogues live in each subtree's `README.md`.

See `brain/.claude/skills/development-nx-run-command/` for the full
reference (hard rules, verb catalogue, templates).

## Repo-wide commands

The top-level `ctl.sh` exposes meta-verbs that operate across every
library in the repo:

```
bash ./ctl.sh status      # inventory: lib count per subtree
bash ./ctl.sh validate    # shellcheck every ctl.sh, every <lang>/_ctl/*.sh
                          # and every *_test.sh, jq-validate every
                          # project.json, enforce drift between targets and
                          # the verbs each ctl.sh's own `help` prints, and
                          # run every *_test.sh suite
bash ./ctl.sh propagate   # fan out the current commit to every consuming
                          # project monorepo (only valid when this repo is
                          # checked out as brain/shared/libs/)
help                      # show usage
```

The matching Nx targets (`nx run libs:status`, `nx run libs:validate`,
`nx run libs:propagate`) are thin wrappers around the same script.

## Propagation

`propagate` is only meaningful when this repo is checked out inside
brain at `brain/shared/libs/`. It delegates to
`brain/.claude/scripts/propagate.sh libs`, which walks every project
monorepo, updates its submodule pointer to the current `libs` commit,
and opens the required PRs. In a standalone clone of `gophersys/libs`
the command refuses and explains how to propagate from brain.

## Commit identity

All commits MUST be authored by `Mateo Segura
<mateo.segura413@gmail.com>`. Messages follow Conventional Commits,
subject ≤72 chars imperative mood, no trailing period, no AI / LLM
attribution. Local git config is captured in `.claude/rules/00-identity.md`.

## Getting started as a consumer

```bash
# From a project monorepo:
git submodule add https://github.com/gophersys/libs shared/libs
git submodule update --init --recursive

# Inspect what's available:
cd shared/libs && bash ./ctl.sh status
```

Once populated, individual libraries are consumed by referencing them
through the project's Nx workspace or the appropriate language package
manager.
