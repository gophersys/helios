# infrastructure — identity

> **Read this first (state as of 2026-07).** This repo is BOTH of the following:
> 1. **The live homelab GitOps source. This is the part you usually touch.**
>    Argo CD reconciles the running k3s cluster from
>    `platform/services/gitops/registry/` (the app-of-apps), with the workloads
>    under `apps/` and the platform add-ons under `platform/`. The live map is
>    `docs/cluster-topology.md`. The working agreement and the ledger of
>    imperative state are in `docs/debt-register.md`. A change goes branch → PR →
>    merge (CI: `.github/workflows/validate.yml`).
> 2. **An IDP framework that is still only a target — the Nx scaffolding below.**
>    `machines/`, `clusters/templates/`, `providers/`, `charts/` and `contracts/`
>    are the multi-cluster design. They are mostly skeletons and STUBs. They are
>    not what runs.
>
> The parent monorepo is **Eden** (`gophersys/eden`, checked out at
> `~/code/eden`). This repo is the git submodule `eden/infrastructure`. Never
> write `helios`: the rename is Eden invariant E7, and the old checkout path
> `~/helios` no longer exists. The "brain" ecosystem named below is the ORIGINAL
> design framing. It predates Eden, and those paths do not exist.

`gophersys/infrastructure` is the shared infrastructure-as-code source. A parent
monorepo consumes it as a git submodule: today `eden/infrastructure`, and in the
original design `brain/shared/infrastructure/` plus a pinned copy per project.

## Purpose (framework design)

Model every real piece of infrastructure — a host, a cluster, a platform service,
a reusable module — as a small, self-contained Nx project that follows the
two-file pattern: `project.json` + `ctl.sh`.

Nothing here runs on its own. The Nx runtime of the parent monorepo drives
everything. A direct call to `bash ./ctl.sh <verb>` works from any project
directory, for authoring and for troubleshooting.

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
│   ├── development/     # developer machines (one directory per real machine)
│   ├── services/        # service hosts (one directory per real machine)
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

1. **Two-file projects only.** Every runnable node is a directory that holds
   `project.json` and `ctl.sh` at its root, and nothing else. The full procedure
   is in the `development-nx-run-command` skill in brain.
2. **Nx comes from the parent monorepo.** This repo has no `nx.json`, no
   `package.json` and no `node_modules/`. The parent monorepo supplies the
   runtime. A direct `bash ctl.sh` works anywhere.
3. **Kebab-case paths.** A directory name is kebab-case. A project name is the
   path segments joined by hyphens, in lowercase.
4. **`ctl.sh` documents itself.** `usage()` lists every verb with a one-line
   description. There is no separate README at project level.
5. **Templates, not scaffolds.** A `templates/` directory holds blueprints that
   the parent's `new-*` verb copies. Do not put logic that runs inside a
   template. Keep every template static.
6. **Linux, Windows and WSL are the priority.** macOS support is present as stubs
   with `TODO:` markers. Do not implement macOS-specific behaviour without an
   explicit instruction.
