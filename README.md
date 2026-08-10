# infrastructure

Shared infrastructure-as-code for the brain ecosystem. It is the Internal
Developer Platform that every project in brain runs on.

It is consumed as a git submodule at:

- `brain/shared/infrastructure/` — the canonical editable copy.
- `brain/projects/<project>/infrastructure/` — the pinned copy for one project.

This repo has no Nx workspace of its own. The parent monorepo (brain, or a
project monorepo) supplies the Nx runtime. Every runnable node is authored as 2
files — `project.json` and `ctl.sh` — per the `development-nx-run-command` skill.

## The seven layers

```
infrastructure/
│
├── machines/                 # 1. Individually-managed hosts (Ansible + Tailscale)
│   ├── development/          #    dev workstations (laptops, desktops, WSL)
│   ├── services/             #    standalone servers (bastions, builders, edge)
│   ├── templates/ roles/
│   ├── scripts/              #    fleet-wide enrollment / secrets / SSH helpers
│   └── groups/
│
├── clusters/                 # 2. Kubernetes clusters (collectively managed)
│   ├── instances/
│   │   └── <cluster>/        #    one real cluster
│   │       ├── identity.yaml
│   │       ├── nodes/        #    cluster-member hosts (same identity shape as machines/)
│   │       └── overlays/     #    per-cluster platform value overrides
│   ├── templates/            #    cluster archetypes (EKS, AKS, OKE, manual-k3s)
│   └── scripts/              #    cluster-level operations (future)
│
├── providers/                # 3. Terraform — HOW compute is created
│   ├── compute-unit/         #    cloud-neutral "give me a 2vCPU arm64 box" interface
│   ├── oracle/ aws/ azure/ hetzner/ bare-metal/   # per-cloud implementations
│   ├── kubernetes-manual/    #    K3s install / join / upgrade helpers
│   └── state-backend/        #    where Terraform state itself lives
│
├── platform/                 # 4. What runs ON clusters — the "backend"
│   ├── core/                 #    non-negotiable cluster bootstrap (CNI, ingress,
│   │                         #    cert-manager, storage, ESO, metrics, netpol)
│   └── services/             #    opt-in, version-pinned shared services
│                             #    (observability, databases, messaging, backup, ...)
│
├── charts/                   # 5. Helm archetypes — HOW consumer apps shape themselves
│   ├── stateless-app/
│   ├── stateful-app/
│   ├── job/ cronjob/ ingress-app/ worker-pool/
│
├── contracts/                # 6. The APP–PLATFORM INTERFACE
│   ├── observability.md      #    how apps emit logs/metrics/traces
│   ├── secrets.md            #    how apps receive Bitwarden-backed secrets
│   ├── databases.md          #    how apps request a Postgres/Redis
│   ├── ingress.md            #    how apps expose HTTPS routes with automatic TLS
│   ├── identity.md           #    how apps gate a route with platform SSO (future)
│   └── messaging.md          #    how apps publish/consume NATS
│
└── docs/                     # 7. Big-picture architecture + runbooks
```

## How the layers interact

- A **cluster** (layer 2) is made of **machines** (layer 1). The **providers**
  (layer 3) know how to provision the hosts of those machines.
- A cluster is bootstrapped with every `platform/core/*` component (layer 4),
  plus the `platform/services/*` components that its identity.yaml opts into.
- An app (outside this repo) shapes itself with a **chart** (layer 5) and
  consumes the platform through the **contracts** (layer 6). An app never couples
  directly to a platform implementation.
- **Docs** (layer 7) is the source for the whole picture when a new contributor,
  or you at a later date, opens this repo with no context.

## Progressive disclosure

A layer holds real content only where a real consumer exists today. Everywhere
else there is a `README.md` stub that describes the intended shape. To grow the
repo:

1. A real need appears (a new cluster, a new service, a new app).
2. Scaffold from a template (`new-host`, `new-cluster`, `new-cluster-node`,
   `new-app`).
3. Fill in the stubs for the layers that the new thing touches.
4. Commit.

## Entry points

- `bash ./ctl.sh help` — the top-level verbs (status, validate, generate-index,
  and the `verify-*` assertions).
- `bash machines/ctl.sh help` — the machine-level verbs (new-host, status, ...).
- `bash clusters/ctl.sh help` — the cluster-level verbs (new-cluster, status,
  ...).

CI is `.github/workflows/validate.yml`. It runs the same `verify-*` scripts that
`ctl.sh` runs, so a check that passes on your machine passes in CI. There is no
second CI layer. The `.ci/` directory was deleted on 2026-08-10 because nothing
invoked it — see `docs/debt-register.md` D38.

The `README.md` of each layer describes that layer's shape. Start there when you
navigate the repo with no context.

## Conventions

- The git identity for every commit is
  `Mateo Segura <mateo.segura413@gmail.com>`.
- Use Conventional Commits for every message (`feat`, `fix`, `refactor`, and so
  on).
- Do not put an AI, LLM or assistant attribution anywhere in the repo.
- A script fetches a secret from Bitwarden when it needs it, writes it to tmpfs,
  and scrubs it on exit. See `docs/secrets-guide.md`.
- Linux, WSL and Windows are the priority platforms. macOS support is a stub, and
  it is marked as a stub wherever it appears.

## Status

Today the repo is the **foundation**. Every layer has its skeleton and its docs,
but only 3 leaves hold real content:

- `clusters/instances/prod/identity.yaml` — a real cluster, declared.
- `contracts/*.md` — drafted interfaces (v0).

Everything else is a stub that waits for its first real consumer.
