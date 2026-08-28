# architecture

This repository is a shared submodule plugged into every monorepo in the brain
ecosystem. It models real-world infrastructure as a collection of small Nx
projects (`project.json` + `ctl.sh`). The parent monorepo (brain, or a project
monorepo) supplies the Nx runtime. This submodule supplies the authoritative
definitions.

## The four layers

```
applications (in consuming monorepos)
        │
        │   charts/*        (blessed Helm archetypes)
        ▼
clusters/instances/*         (Kubernetes clusters)
        │
        │   providers/*     (reusable Terraform modules)
        │   platform/*      (cluster-level shared services)
        ▼
machines/<category>/*        (physical + virtual hosts; development | services)
        │
        │   machines/roles/*      (Ansible roles)
        │   machines/scripts/*    (BW-backed ephemeral scripts)
        ▼
Bitwarden vault              (single source of secrets)
```

An arrow shows consumption, not orchestration. Every arrow crosses a file system
boundary: a module source path or a chart dependency. Nothing reaches up.

## Layer responsibilities

- **machines/** owns the host reality. Each host is a directory with
  `identity.yaml` and optional Ansible overrides. The roles install the OS
  baseline, the networking (Tailscale), the secrets client (Bitwarden CLI) and
  the developer capabilities. The scripts are the bridge between an operator's
  shell and the Bitwarden vault: load, purge, SSH, tailscale-provision and index
  regeneration.

- **clusters/** owns the Kubernetes reality. A cluster instance references
  `providers/*` for its Terraform modules. It binds to `machines/*` when the
  provider is `kubernetes-manual` (k3s on enrolled hosts).

- **providers/** is a Terraform module library. It is pure code and holds no
  state.

- **platform/** owns the shared services of a cluster. An application never
  installs its own Postgres or ingress controller. It consumes the cluster-level
  service through an interface: a database connection string, an ingress
  hostname, or a NATS URL.

- **charts/** is the Helm archetype library. An application picks one archetype
  and supplies the values. This is the only place that holds Deployment,
  StatefulSet and Ingress manifests.

## Submodule lifecycle

A change lands here on a feature branch, then a PR, then a merge to `main`. The
parent monorepo — Eden, at `eden/infrastructure` — then bumps its submodule
pointer. Nobody starts that from inside this repo.

There is no `propagate` verb. This paragraph named one, and named 2
`brain/...` paths that do not exist. Run `bash ctl.sh help` for the verbs this
repo has, and do not trust a verb name that only prose supplies.

## What is deliberately NOT here

- No `nx.json`, no `package.json` and no `node_modules/`. The parent monorepo
  supplies Nx.
- No repo-level metadata files for a chat tool. The operational conventions live
  under `.claude/rules/`; free-form transcripts do not belong here.
- No secrets of any kind, including example and development credentials.
