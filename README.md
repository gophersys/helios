# infrastructure

Shared infrastructure-as-code for the brain ecosystem — the Internal
Developer Platform that every project in brain runs on top of.

Consumed as a git submodule at:

- `brain/shared/infrastructure/` — canonical editable copy.
- `brain/projects/<project>/infrastructure/` — pinned per-project copy.

This repo has no Nx workspace of its own. The parent monorepo (brain, or
a project monorepo) provides the Nx runtime. Every runnable node is
authored as two files — `project.json` + `ctl.sh` — per the
`development-nx-run-command` skill.

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

- A **cluster** (layer 2) is composed of **machines** (layer 1) whose hosts
  the **providers** (layer 3) know how to provision.
- A cluster is bootstrapped with every `platform/core/*` (layer 4) and the
  `platform/services/*` components its identity.yaml opts into.
- Apps (outside this repo) shape themselves via **charts** (layer 5) and
  consume the platform through **contracts** (layer 6) — they never couple
  directly to platform implementations.
- **Docs** (layer 7) is the big-picture source when a new contributor (or
  future-you) opens this repo cold.

## Progressive disclosure

Every layer holds real content only where there's a real consumer today.
Everywhere else is `README.md` stubs describing the intended shape. Growing
the repo means:

1. A real need appears (a new cluster, a new service, a new app).
2. Scaffold from a template (`new-host`, `new-cluster`, `new-cluster-node`,
   `new-app`).
3. Fill in the stubs for the layers the new thing touches.
4. Commit.

## Entry points

- `bash ./ctl.sh help` — top-level verbs (status, validate, generate-index,
  propagate).
- `bash machines/ctl.sh help` — machine-level verbs (new-host, status, ...).
- `bash clusters/ctl.sh help` — cluster-level verbs (new-cluster, status, ...).
- `bash .ci/ctl.sh help` — CI orchestration (validate, release-check, ...).

Per-layer README.md files walk you through that layer's shape. Start there
when navigating cold.

## Conventions

- Git identity for every commit: `Mateo Segura <mateo.segura413@gmail.com>`.
- Conventional Commits for all messages (`feat`, `fix`, `refactor`, etc.).
- No AI/LLM/assistant attribution anywhere in the repo.
- Secrets are fetched from Bitwarden just-in-time onto tmpfs and scrubbed
  on exit. See `docs/secrets-guide.md`.
- Linux, WSL, and Windows are priority platforms. macOS support is a stub
  and marked as such wherever it appears.

## Status

Today's shape is the **foundation** — every layer has its skeleton + docs,
but only three leaves have real content:

- `machines/services/arm-builder/` — ported working scripts.
- `clusters/instances/app-prod/identity.yaml` — real cluster declared.
- `contracts/*.md` — drafted interfaces (v0).

Everything else is a stub awaiting its first real consumer.
