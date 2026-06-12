# eden

**Eden** is an opinionated platform for building and operating software systems with agentic
engineering — the discipline layer (process, contracts, evidence, observability) packaged as a
product. This is its monorepo, currently in the architecture/bootstrap phase.

> Formerly "helios" (ADR-0002 records the rename; the GitHub repo rename to `gophersys/eden` is a
> pending gated change). Nx workspace seeded from `gophersys/template`, with three shared
> submodules and a baseline CI layer.

## Start here

- **`docs/README.md`** — the documentation scheme and map.
- **`docs/architecture/README.md`** — the canonical architecture set (charter, principles,
  decomposition, process model, connectors, bootstrap ladder, ADRs). Read this before touching
  anything.
- **`docs/architecture/09-build-execution-plan.md`** — what gets built first and how.

## Structure

```
eden/
├── docs/                   # documentation (scheme in docs/README.md)
├── schemas/                # machine-validated artifact schemas (E2; schemas/README.md)
├── tools/                  # repo tooling: documentvalidator (doc 11 §8)
├── apps/                   # deployables: backend/, frontend/, desktop/, agent/ (to be created)
├── poc/                    # proofs of concept — donor material, gated salvage (poc/README.md)
├── .devcontainer/          (submodule — gophersys/.devcontainer: base images)
├── infrastructure/         (submodule — gophersys/infrastructure: machines, clusters)
├── libs/                   (submodule — gophersys/libs: language-partitioned libraries)
├── .ci/                    # baseline CI — ctl.sh verbs + provider shims
└── .github/workflows/      # symlinks into .ci/providers/github/
```

Clone with submodules, or initialize after the fact:

```bash
git submodule update --init --recursive
```

## CI

Every verb runs across the whole monorepo via `nx run-many` / `nx affected`:

```bash
bash .ci/ctl.sh affected-check   # canonical PR gate: lint, typecheck, test
bash .ci/ctl.sh validate         # shellcheck + nx run-many -t validate
bash .ci/ctl.sh build-all
```

The verbs no-op gracefully until `nx` is installed (`yarn install`).
`.github/workflows/*.yml` are symlinks into `.ci/providers/github/` — the provider directory is
the source of truth.

## Conventions

- Projects follow the `project.json` + `ctl.sh` pattern; Nx targets wrap `bash ./ctl.sh <cmd>`.
- Everything else — naming, commit rules, agent rules — lives in `CLAUDE.md` (ratified in
  ADR-0010; canonical naming standard: `docs/architecture/10-library-system.md` §5).
