# .devcontainer — identity and conventions

This repo (`gophersys/.devcontainer`) is a shared submodule consumed by
every project monorepo in the brain ecosystem. Its role is to provide the
base container images used both for local development (VS Code
devcontainer) and as the CI runtime that GitHub Actions invokes `nx
affected` inside.

## Purpose

- Single source of truth for the base images every brain-ecosystem project
  depends on.
- Keeps local dev and CI execution environments byte-for-byte identical.
- Provides a place to bump a toolchain version (Node, Python, Go, Rust,
  Flutter, Zephyr SDK) exactly once and have the change flow to every
  project via the shared-change propagation mechanism.

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── .claude/
│   └── rules/
│       └── 00-identity.md       # (this file)
├── images/
│   ├── base/                    { Dockerfile, project.json, ctl.sh }
│   ├── node/                    { Dockerfile, project.json, ctl.sh }
│   ├── python/                  { Dockerfile, project.json, ctl.sh }
│   ├── go/                      { Dockerfile, project.json, ctl.sh }
│   ├── rust/                    { Dockerfile, project.json, ctl.sh }
│   ├── flutter/                 { Dockerfile, project.json, ctl.sh }
│   └── zephyr/                  { Dockerfile, project.json, ctl.sh }
└── .github/workflows/
    └── build-and-push.yml       # on push to main: publish every image to ghcr.io/gophersys/<name>
```

## Conventions

1. **No Nx workspace of its own.** This repo has no `nx.json`, no
   `package.json`, no `node_modules/`. The parent project monorepo
   provides the Nx runtime. Every operation must be runnable as plain
   `bash ./ctl.sh <cmd>` from within this repo.
2. **Two-file project rule.** Every image directory under `images/*`
   contains exactly two wiring files at its root — `project.json` and
   `ctl.sh` — plus the `Dockerfile` that is this project's actual
   artifact source. No READMEs per image; the per-image `ctl.sh usage()`
   is the spec.
3. **No `CLAUDE.md` files.** Repo-specific conventions live here, in
   `.claude/rules/`. The parent brain repo loads its top-level rules
   independently.
4. **Human-authored voice.** Commit messages, comments, and docs contain
   no AI/LLM attribution of any kind.

## Per-image verb catalog

Each image's `ctl.sh` implements the following verbs. All four targets
exist in `project.json` as `nx:run-commands` wrappers. `cache: false` on
every target — Docker has its own cache layer and duplicating it in Nx
causes confusion.

| Verb | Action | Cache |
|---|---|---|
| `build` | `docker build -t ghcr.io/gophersys/<name>:latest .` | false |
| `push` | `docker push ghcr.io/gophersys/<name>:latest` | false |
| `pull` | `docker pull ghcr.io/gophersys/<name>:latest` | false |
| `inspect` | `docker image inspect ghcr.io/gophersys/<name>:latest` | false |
| `help` | Print the usage block from `ctl.sh` | n/a |

## Repo-root verb catalog

The repo-root `ctl.sh` orchestrates the full set:

| Verb | Action |
|---|---|
| `build-all` | Build every image in dependency order (`base → node, python, go, rust → flutter, zephyr`) |
| `push-all` | Push every image to the registry |
| `list` | Print the managed image refs |
| `validate` | shellcheck every `ctl.sh`, `jq` every `project.json`, hadolint every `Dockerfile` if available |
| `propagate` | Fan out a submodule bump to every consuming project (delegates to brain) |
| `help` | Usage |

## Dependency graph

```
            base
      ┌──────┼──────┬──────┐
      │      │      │      │
    node  python   go    rust
      │      │
   flutter zephyr
```

Declared in three places that MUST stay in sync:

- `BUILD_ORDER` in `./ctl.sh` — runtime sequential order for `build-all`.
- `dependsOn` in each image's `project.json` — Nx dependency graph.
- `needs:` in `.github/workflows/build-and-push.yml` — CI job dependencies.

When changing the graph, update all three in the same commit.

## Shared-change propagation

This repo is mirrored as a submodule into every project monorepo under
`<project>/.devcontainer/`. Changes made here are not visible to projects
until each project bumps its submodule pointer.

The canonical flow:

1. Edit here (never inside a project's mirror).
2. Commit and push to `origin/main`.
3. Run `bash ./ctl.sh propagate` from within the brain checkout (the
   verb delegates to `brain/.claude/scripts/propagate.sh`, which owns
   the project list).
4. Propagation is approval-gated — see the brain-level rules on approval
   gates and shared-change propagation.

Direct edits inside a project's mirror are forbidden and detected by
brain's drift auditor.

## Git hygiene

- Git identity is set per-repo (never touches the global config):
  `user.name = Mateo Segura`, `user.email = mateo.segura413@gmail.com`.
- `commit.gpgsign = false` per-repo.
- Conventional Commits for every commit. `feat`, `fix`, `refactor`,
  `docs`, `test`, `chore`, `perf`, `ci`, `build`.
- No force-pushes to `main`.
