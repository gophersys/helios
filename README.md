# helios

Monorepo scaffolded from the `gophersys/template` blueprint. Nx workspace
with three shared submodules and a baseline CI layer.

## Structure

```
helios/
├── .devcontainer/          (submodule — gophersys/.devcontainer)
├── infrastructure/         (submodule — gophersys/infrastructure)
├── libs/                   (submodule — gophersys/libs)
├── apps/                   # apps live here (backend/, frontend/, …)
├── .ci/                    # baseline CI — ctl.sh verbs + provider shims
├── .github/workflows/      # symlinks into .ci/providers/github/
├── nx.json
├── package.json
├── tsconfig.base.json
└── tsconfig.json
```

## Submodules

Clone with submodules, or initialize after the fact:

```bash
git submodule update --init --recursive
```

| Path | Upstream |
|---|---|
| `.devcontainer/` | `gophersys/.devcontainer` — base images (dev + CI) |
| `infrastructure/` | `gophersys/infrastructure` — machines, clusters, platform services |
| `libs/` | `gophersys/libs` — language-partitioned shared libraries |

## CI

Every verb runs across the whole monorepo via `nx run-many` / `nx affected`:

```bash
bash .ci/ctl.sh affected-check   # canonical PR gate: lint, typecheck, test
bash .ci/ctl.sh validate         # shellcheck + nx run-many -t validate
bash .ci/ctl.sh build-all
```

The verbs no-op gracefully until `nx` is installed (`yarn install`).
`.github/workflows/*.yml` are symlinks into `.ci/providers/github/` — the
provider directory is the source of truth.

## Conventions

- Apps follow the `project.json` + `ctl.sh` pattern; targets wrap
  `bash ./ctl.sh <cmd>` via `nx:run-commands`.
- Nx Cloud is disabled (`neverConnectToCloud` in `nx.json`); do not remove it.
- Conventional Commits. No AI/LLM attribution.
