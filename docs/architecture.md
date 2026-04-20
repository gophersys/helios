# architecture

This repository is a shared submodule plugged into every monorepo in the
brain ecosystem. It models real-world infrastructure as a collection of
small Nx projects (`project.json` + `ctl.sh`). The parent monorepo
(brain, or a project monorepo) provides the Nx runtime; this submodule
provides the authoritative definitions.

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
machines/hosts/*             (physical + virtual hosts)
        │
        │   machines/roles/*      (Ansible roles)
        │   machines/scripts/*    (BW-backed ephemeral scripts)
        ▼
Bitwarden vault              (single source of secrets)
```

Arrows are consumption, not orchestration. Every arrow crosses a file
system boundary (module source paths or chart dependencies); nothing
reaches up.

## Layer responsibilities

- **machines/** owns host reality. Each host is a directory with
  `identity.yaml` + optional Ansible overrides. Roles install the OS
  baseline, networking (Tailscale), secrets client (Bitwarden CLI), and
  developer capabilities. Scripts are the bridge between an operator's
  shell and the Bitwarden vault — load, purge, SSH, tailscale-provision,
  and index regeneration.

- **clusters/** owns Kubernetes reality. Cluster instances reference
  providers/* for their Terraform modules; they bind to machines/* when
  the provider is `kubernetes-manual` (k3s on enrolled hosts).

- **providers/** is a Terraform module library — pure code, no state.

- **platform/** owns cluster-wide shared services. Applications never
  install their own Postgres or ingress controller; they consume the
  cluster-level service via an interface (DB connection string, ingress
  hostname, NATS URL).

- **charts/** is the Helm archetype library. Applications pick one and
  supply values. This is the only place Deployment/StatefulSet/Ingress
  manifests live.

## Submodule lifecycle

Changes land here on a feature branch, PR, merge to `main`. The
consuming submodule pointers (in `brain/shared/infrastructure/` and
`brain/projects/<p>/infrastructure/`) are bumped from the parent monorepo
via the `propagate` verb (top-level `ctl.sh propagate`). Propagation is
not triggered from inside this repo.

## What is intentionally NOT here

- No `nx.json`, no `package.json`, no `node_modules/`. The parent
  monorepo provides Nx.
- No repo-level chat-tool metadata files. Operational conventions live
  under `.claude/rules/`; free-form transcripts do not.
- No secrets of any kind, including example/development credentials.
