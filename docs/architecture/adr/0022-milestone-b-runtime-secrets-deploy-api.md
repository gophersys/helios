# ADR-0022: Milestone-B architecture — supervising provider, Vault secrets, deploy local/prod, NATS→SSE api

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Mateo (ratified the four forks 2026-06-13; grounded in the `MateoSegura/IOTEA-archive` prior art)

## Context

The 11 Go libraries are ADR-0020 gate-green (the seams are cut: `workspaceprovider` provisions
workspaces behind a docker + kubernetes adapter port; `agentsession` spawns harness CLIs and
normalizes their stream; `orchestrator` reconciles desired→actual over those ports; `secrets` is a
`Reference`/`Mediator` redaction port). Milestone B turns this from "verified against fakes,
single-node" into "real agent pods at scale on docker AND k8s, over a NATS/JetStream bus, with
secrets and a chat UI" ([[harness-platform-architecture]], [[eden-secrets-and-deploy-architecture]]).

Before building, the IOTEA prior art was studied (its `libs/engine/runtime` ran across docker AND
k8s; its `deploy/` rendered local-vs-prod; its `libs/secrets` is Vault-backed; its http-api is a
Fiber control plane). Four forks were put to Mateo and ratified. This ADR records the rulings; the
detailed build spec is `docs/architecture/15-milestone-b-runtime.md` (forthcoming per ADR-0010).

## Decision

### 1. Secrets → Vault now, ephemeral per-session role

The `secrets` lib's `Mediator` gains a **Vault backend** now, adopting IOTEA's proven dual-mode
bootstrap: **local = userpass** (env username/password → Vault token), **production = Kubernetes
ServiceAccount** whose token a Vault sidecar exchanges for a token written to `/vault/secrets/token`.
The per-agent boundary is an **ephemeral Vault role + least-privilege policy minted per agent
SESSION** (created and destroyed by the `agentsession` lifecycle), path-scoped to exactly that
agent's secrets — the strict-by-default isolation. An agent pod resolves its bundle from one KV
path at sidecar boot (the bootstrap credential stays low-privilege). **Local runs a REAL Vault —
the official `hashicorp/vault` image with a thin one-shot init/unseal bootstrap step (NOT `-dev`
in-memory mode, and NOT a bespoke self-unsealing Vault image like IOTEA built; Mateo, 2026-06-13:
"i want the real thing")** — so local and production exercise the SAME real Vault (real auth,
real path-scoped policies, persistence), local↔prod fidelity. The `secrets.Use` + env-scrubbing
no-leak contract is unchanged; the Vault backend slots behind the existing port (composition root).

### 2. Deploy local-vs-production, two-axis, supporting services out-of-band

A `deploy/<plane>/{local,production}` layout mirrors IOTEA: **local = docker-compose** (the
`workspaceprovider` dockeradapter world), **production = a Helm chart** (the kubernetesadapter
world), one Nx/`ctl.sh` target selecting the stage, image-tag-as-environment-contract (`<svc>:local`
load vs `<registry>/<svc>:<tag>` push, one Dockerfile). The **supporting stack** (NATS/JetStream +
Postgres + Vault) is stood up **OUT-OF-BAND** by a `ctl.sh`/helm step — the platform
(orchestrator/agents) assumes it exists; the orchestrator does NOT reconcile the platform's own
substrate. A single typed Go **`ServiceSpec`** renders to BOTH compose and Helm (one source of
truth, no hand-maintained drift). Agent pods dogfood the `.devcontainer` base image family.
**Dev credentials load via the standard `.env` convention** (Mateo, 2026-06-13): a committed
`.env.example` (+ `.env.<environment>.example`) template carries placeholders only; the real
`.env.<environment>` (e.g. `.env.development`) is gitignored and NEVER committed. `deploy local`
loads `.env.development` into the process env AND seeds the local Vault from it (IOTEA-style: log
in to the just-started Vault, `kv put` each value under the agent's path) — so harness credentials
reach the spawned agents through Vault, not loose files. (Replaced the earlier `.dev-secrets/` dir.)

### 3. http-api = stateless NATS→SSE bridge + REST-POST control

The gateway is **stateless**: `GET /sessions/{id}/events` is a **NATS→SSE bridge** serving the
per-session event stream from `agent.<id>.events` via JetStream durable replay (reconnect by
`Last-Event-ID`/`from-seq`); any gateway replica serves any session. **Control** (prompt/steer/
abort/stop/kill) is **REST POST** that publishes to `agent.<id>.control`. The control endpoints
adopt IOTEA's clean **6-stage handler pipeline** (parse → validate → authorize → execute → respond
→ action) and a uniform response envelope, in a new `edenhttp` lib (HNS-1 full naming; never
`httputil`). IOTEA has NO streaming — the SSE half is Eden-new. `namespace:action` grant grammar
(IOTEA's RBAC) doubles as the per-tool sandbox vocabulary.

### 4. The supervising ("fat") provider + the Entrypoint capability

`workspaceprovider` **absorbs runtime supervision** — it becomes IOTEA's `manager.Manager`: beyond
provision/teardown it **supervises** the workload (a global label-filtered docker-events / k8s
pod-watch), **normalizes** Docker actions and k8s pod phases into ONE platform-neutral
`Event`/`Status` space, and does **reconcile-from-reality** (list-by-label re-adoption on restart).
It gains an **Entrypoint/workload-pod capability** (OD-15 option-a, now ratified): the container's
main process IS the workload (the PID-1 agent-runtime sidecar) on docker AND k8s — native
liveness/restart/OOM, and the kubernetes OOM-discriminator surfaces natively. The **orchestrator
thins**: it owns desired-state (`DesiredStore`) and reconciles, but **Probes the provider's
supervised Status** rather than raw heartbeats. **NATS = the soft control signal** (the
orchestrator publishes prompt/steer/stop/kill to `agent.<id>.control`; the in-pod PID-1 is
subscribed and acts); the **docker/k8s API = the hard lifecycle** (the provider kills the
container/pod). OTel trace context rides every NATS message.

This is a **contract revision** of the frozen `workspaceprovider` (ADR-0016 §1): un-freeze →
extend §7 with the supervision + Entrypoint surface → re-record `.apibaseline` → re-freeze. It
**resolves OD-15** (adopt option-a) and amends OD-14's egress story onto the workload-pod path.

## Consequences

- The agent-pod runtime sidecar is PID-1 (a graceful-shutdown state machine: `signal.NotifyContext`
  → typed termination reason → cancel → drain → cleanup → OTel flush), spawning the harness via
  `agentsession` in-process and owning its NATS conn + heartbeat.
- `workspaceprovider` grows (supervision + Entrypoint) — a deliberate, gated surface expansion, not
  scope creep: it is the one place pod lifecycle lives, so the orchestrator and gateway stay simple.
- Build order (each its own gated workflow, ADR-0020): Codex adapter → secrets Vault backend → the
  supervising provider + Entrypoint (contract revision) → NATS/JetStream + the PID-1 agent-runtime →
  thin orchestrator over real pods → stateless gateway (NATS→SSE) + `edenhttp` → git-backed
  `agent-configs/` + strict sandbox → Svelte 5 chat UI + Playwright real E2E → deploy local/prod.
- Real tests, no mocks throughout: every piece is proven on the real substrate (docker + k3d + a
  real NATS) in the devcontainer before it is called done.

This ADR extends ADR-0008 (agentsession), ADR-0016 (the workspaceprovider contract it revises),
and ADR-0020 (the gate every new lib passes); it is the build spec's parent ruling.
