# infrastructure

Shared infrastructure-as-code source for the brain ecosystem. Consumed as a
git submodule at:

- `brain/shared/infrastructure/` — canonical editable copy.
- `brain/projects/<project>/infrastructure/` — pinned per-project copy.

This repo has no Nx workspace of its own. The parent monorepo (brain, or a
project monorepo) provides the Nx runtime. Every project inside this repo
is authored as exactly two files at its root — `project.json` and `ctl.sh`
— following the `development-nx-run-command` skill.

## Top-level layout

```
infrastructure/
├── machines/           # physical and virtual hosts (Ansible + Tailscale)
├── clusters/           # Kubernetes clusters (cloud and manual)
├── providers/          # reusable Terraform modules per cloud
├── platform/           # cluster-level shared services (Helm)
├── charts/             # blessed Helm chart archetypes
└── docs/               # architecture, contracts, secrets guide
```

Everything is progressive-disclosure. A project exists when there's a real
thing to model — no speculative scaffolding. Templates exist so scaffolding
a new machine, cluster, or chart is one command away.

## Entry points

- `bash ./ctl.sh help` — top-level verbs.
- `bash machines/ctl.sh help` — machine-level verbs.
- `bash clusters/ctl.sh help` — cluster-level verbs.
- `docs/README.md` — full documentation index.

## Conventions

- Git identity for every commit: `Mateo Segura <mateo.segura413@gmail.com>`.
- Commit signing disabled locally (`git config commit.gpgsign false`).
- Conventional Commits for all messages (`feat`, `fix`, `refactor`, etc.).
- Secrets are fetched from Bitwarden just-in-time onto tmpfs and scrubbed
  on exit. See `docs/secrets-guide.md`.
- Linux, WSL, and Windows are priority platforms. macOS support is a stub
  and marked as such wherever it appears.
