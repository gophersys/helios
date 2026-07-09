# infrastructure — identity

> **Reality check (2026-07): read this first.** This repo is BOTH:
> 1. **The live homelab GitOps source (what you'll usually touch).** Argo CD
>    reconciles the running k3s cluster from `platform/services/gitops/registry/`
>    (app-of-apps) with workloads under `apps/` and platform add-ons under
>    `platform/`. The live map is `docs/cluster-topology.md`; the working
>    agreement + imperative-state ledger is `docs/debt-register.md`. Changes go
>    branch → PR → merge (CI: `.github/workflows/validate.yml`).
> 2. **An aspirational IDP framework (the Nx scaffolding described below).**
>    `machines/`, `clusters/templates/`, `providers/`, `charts/`, `contracts/`
>    are the multi-cluster design — mostly skeletons/STUBs, not what runs.
> The parent monorepo is **`helios`** (the Eden monorepo): this repo is the git
> submodule `helios/infrastructure`. The "brain" ecosystem below is the ORIGINAL
> design framing and predates helios — those paths don't exist.

`gophersys/infrastructure` is the shared infrastructure-as-code source,
consumed as a git submodule by the parent monorepo (today: `helios/infrastructure`;
originally designed for `brain/shared/infrastructure/` + per-project pins).

## Purpose (framework design)

Model every real-world piece of infrastructure — hosts, clusters, platform
services, reusable modules — as a small, self-contained Nx project following
the two-file pattern: `project.json` + `ctl.sh`.

Nothing here runs on its own; the parent monorepo's Nx runtime drives
everything. Directly invoking `bash ./ctl.sh <verb>` works from any
project directory for authoring and troubleshooting.

## Structure

```
infrastructure/
├── README.md
├── .gitignore
├── .claude/
│   ├── rules/           # this directory
│   └── skills/          # (empty — shared skill lives in brain)
├── project.json         # top-level: status, validate, generate-index, propagate
├── ctl.sh               # top-level control
│
├── machines/            # hosts under Ansible + Tailscale
│   ├── hosts/           # one directory per real machine
│   ├── templates/       # blueprints to scaffold new hosts
│   ├── roles/           # Ansible roles (common, platform-*, developer-*, ...)
│   ├── scripts/         # shared bash scripts (secrets, SSH, Tailscale, index)
│   ├── groups/          # host groupings (by-purpose, by-location)
│   ├── project.json     # machines-level Nx wiring
│   └── ctl.sh
│
├── clusters/            # Kubernetes clusters (cloud + manual)
│   ├── instances/       # one directory per real cluster
│   ├── templates/       # cluster blueprints
│   ├── project.json
│   └── ctl.sh
│
├── providers/           # reusable terraform modules per cloud
│   ├── aws/
│   ├── azure/
│   ├── oracle/
│   └── kubernetes-manual/
│
├── platform/            # cluster-level shared services
│   ├── ingress-tls/
│   ├── secrets-external-operator/
│   ├── observability/
│   ├── database-postgresql/
│   └── messaging/
│
├── charts/              # blessed Helm chart archetypes
│   ├── stateless-app/
│   ├── stateful-app/
│   ├── job/
│   ├── cronjob/
│   └── ingress-app/
│
└── docs/
```

## Conventions

1. **Two-file projects only.** Every runnable node is a directory with
   `project.json` + `ctl.sh` and nothing else at its root. See the
   `development-nx-run-command` skill in brain for the full recipe.
2. **Nx via parent monorepo.** This repo has no `nx.json`, no
   `package.json`, no `node_modules/`. The parent monorepo provides the
   runtime. Direct `bash ctl.sh` works anywhere.
3. **Kebab-case paths.** Directory names are kebab-case. Project names are
   path segments joined by hyphens, lowercase.
4. **Self-documenting ctl.sh.** `usage()` lists every verb with a one-line
   description. No separate README at the project level.
5. **Templates not scaffolds.** `templates/` directories hold blueprints
   copied by the parent's `new-*` verb. Do not put logic that runs inside
   a template — keep them static.
6. **Linux + Windows + WSL are priority.** macOS support is present as
   stubs with `TODO:` markers; do not implement macOS-specific behavior
   without an explicit directive.
