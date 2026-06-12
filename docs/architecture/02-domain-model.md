# 02 — Domain Model

> Status: Draft · 2026-06-12 · Canonical home for entity definitions and schema ownership.
> Wire-visible entities are ultimately defined once in `libs/protocols` (Protobuf, buf); this
> document is their conceptual source. Upstream definitions cited, not duplicated: Evidence, Spec
> envelope, harness senses → `spec-driven-implementation-system.md`; Cell vector → corpus doc 04.

## 1. Platform entities

| Entity | Definition |
|---|---|
| **Organization / User** | Tenancy root; RBAC principal. The central cluster is multi-tenant from v1 (ADR-0012); local-as-a-cluster and byo-authority projects are effectively single-tenant. Entities and tenancy keys exist from day 1 (07 §6). |
| **Project** | The unit a user creates and operates. Owns exactly one Monorepo, a set of enabled Archetypes, Connector bindings, Environments, budgets, and dashboards. |
| **Monorepo** | The project's single git repository, Eden-hosted (built-in git), mirrored to external SCM via connectors. All artifacts — specs, code, schemas, pipelines, decisions — live in it; git is the audit trail. |
| **Workspace** | A provisioned development environment attached to a Monorepo: browser editor or remote-VS-Code session, or an agent pod. Pod/session lifecycle is owned by S2's orchestrator over the `workspaceprovider` port; what runs *inside* an agent pod (harness invocation, tool grants, transcript capture) is owned by the F4 agent connector (05 §2). |
| **AssistantSession** | An interactive in-app agent session over project data (runs, transcripts, dashboards, FinOps, drift events). Runs through the F4 connector with read-scoped tool grants; surfaced by S1; its transcript is stored and redacted like any Run's (07 §3). |
| **Environment** | Stage enum: `development · test · staging · production`. Selects wiring/values only (P6). |
| **Platform (substrate)** | The runtime-substrate port: `docker-compose · kubernetes · bare-host · vm`. Selects mechanism only (P6). Cloud vendors appear as *managed adapters of substrates* (EKS/GKE/AKS/DO ⊂ kubernetes), not as substrates themselves. |
| **Connector** | A binding of an Eden port family to a provider adapter with credentials: see 05 for anatomy (contract, adapter, capability manifest, conformance suite, credential profile, usage meter, drift detector). |
| **CapabilityManifest** | Machine-readable declaration of which optional contract capabilities an adapter implements; drives graceful degradation in the UI and the engine. |
| **Credential** | A vaulted, scoped secret bound to a Connector. Never enters agent context; agents receive short-lived scoped tokens through the `secrets` port (07 §2). |
| **UsageRecord** | Metered consumption: provider spend (polled via connectors) and token spend (metered by the agent layer), unified for FinOps views (S9). |
| **DriftEvent** | A detected divergence between Eden's desired state and observed external state within a connector's ownership domain, with provenance and proposed RemediationActions (05 §5). |
| **RemediationAction** | One of `adopt` (import the external change as an authored artifact), `revert` (restore desired state), `fork` (branch the divergence for human ruling). |

## 2. Process entities

| Entity | Definition |
|---|---|
| **Cell** | A typed software category: the invariant 10-phase spine + a 5-parameter vector (D1 change arity, D2 author/build determinism, D3 evidence kind, D4 delivery, D5 scale) + topology selector. Canonical: corpus doc 04. v1 cells: `go-backend`, `svelte-ui`. |
| **Spec** | The unit of work: `{Contract, Template-ref, Tests, Gate}` — four roles behind interfaces (spec-driven §1). Versioned; invalidatable by Evidence; amending its tests is a governed act. |
| **Contract** | The frozen seam between components: a Go interface, a proto service, a token schema. Frozen at an interface-negotiation gate before implementation begins (09 §4). |
| **Template** | A per-cell scaffold with typed holes — in Go: interface + `panic("unimplemented")` stubs + `_test.go` written first. Implementation = decompression under verification (filling the typed holes until the pre-written tests pass). |
| **Evidence** | The verification envelope interface — Claim, Verdict, Confidence, Reproducibility, CostToReproduce, Provenance, Staleness, opaque Payload (spec-driven §4). Gates read the envelope only. |
| **Gate** | A policy over Evidence: promote iff verdict passes, confidence exceeds threshold, not stale, reproducibility acceptable — plus test-power (mutation score) where feasible. Human-gate policy per phase: `auto · approve · edit` (04 §5). |
| **Run** | One execution of a phase (or pipeline) by an agent or swarm: inputs, artifact outputs, Evidence, Transcript, token/cost ledger, validation failures, retries. Fully persisted and queryable. |
| **Swarm** | A phase execution fanned over independent artifacts (one agent per ServiceContract, component, or rule). Independence is established at planning time by disjoint FileLease sets; operational semantics in 04 §7. |
| **FileLease** | An exclusive write claim over a declared file set, assigned per work package in the ImplementationPlan and released on completion. Overlapping leases across concurrent packages are a planning error, not a merge problem. |
| **Transcript** | The complete conversation/event stream of an agent execution, stored as a first-class object on plane (b) of observability (P9). |
| **Phase artifact** | A schema-validated document flowing between phases (ProjectSpec, RequirementsArtifact, DomainModel, ServiceContract, ImplementationPlan, SourceChange, ReleaseCandidate, DeploymentRecord, Observation — 04 §4). |
| **Archetype (Stack)** | A versioned, pluggable technology-stack module: monorepo scaffold + library wiring + CI pipeline + test harness + deployment manifests + the prompts/schemas used to extend it. Defines both `create` and **`graft`** (add to an existing monorepo) operations. |
| **Graft** | The defined operation that adds or removes an Archetype on an existing Monorepo at any point in its life — the mechanism behind "stacks are pluggable at any time". |
| **TokenBudget** | Hard ceilings per run/phase/project with escalation policy (e.g. promote to a stronger model) and cost-aware abort (04 §6). |

## 3. Library entities

| Entity | Definition |
|---|---|
| **Pattern** | A canonical port + discipline (configuration, dependencies, errors, observability, logging, testing, secrets, management, transport, environment, platform, evidence, persistence, identity). Canonical: 10 §4. |
| **Library** | A pattern rendered into one ecosystem under HNS-1 naming, with its own module/package, fakes, and conformance suite. |
| **Release / Adoption state** | The dev→release→adopt state machine (AUTHORED→OVERRIDE→RELEASED→ADOPTED); on `main`, every app↔library edge must be ADOPTED (remote-pinned). Canonical: 10 §8. |
| **Knowledge rule** | A versioned, sourced, oracle-backed rule compiled to a checker; ships only with proven uplift (docs/research/03). |

## 4. Relationships

```
Organization ─┬─ Project ─── Monorepo ─┬─ Workspace*          (editor sessions, agent pods)
              │      │                 ├─ Archetype*  ──(graft)──▶ Monorepo
              │      │                 └─ PhaseArtifact* / Spec* / Run* / Transcript*
              │      ├─ Connector* ──┬─ Credential
              │      │               ├─ CapabilityManifest
              │      │               ├─ UsageRecord*
              │      │               └─ DriftEvent* ── RemediationAction*
              │      ├─ Environment* × Platform(substrate)     (independent axes, P6)
              │      └─ TokenBudget / FinOps view
              └─ RBAC policies / AssistantSession*
Cell ── Spec ── {Contract, Template, Tests, Gate} ── Run ── Evidence ──▶ Gate decision
```

## 5. Schema ownership

| Schema | Source of truth | Consumers |
|---|---|---|
| Wire/domain messages & services | `libs/protocols` (Protobuf, buf; Connect transport) | Go backend, Svelte client, agent pods |
| Phase artifact schemas | `schemas/document/v1/` in the eden monorepo (11, ADR-0011) | Process engine, CI validation, agents, dashboards |
| Theme/design-system schema | photosphere (DTCG-shaped ThemeDoc + component manifest) | Design-system connector family, `svelte-ui` cell |
| agents.yaml (agent configuration) | upstream portable-agent-config schema → `agentconfiguration` library | Agent layer (05 family F4) |
| Knowledge rule schema | `poc/knowledge` rule YAML (to be promoted into the knowledge pipeline) | Knowledge libraries, eval harness |
