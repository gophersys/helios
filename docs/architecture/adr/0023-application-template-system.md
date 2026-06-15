# ADR-0023: Application template system — the http-gateway scaffold

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Mateo (ratified the forks 2026-06-14; grounded in the `MateoSegura/IOTEA-archive` prior art)

## Context

The 11+ Go libraries are ADR-0020 gate-green and Milestone-B (ADR-0022) stood up the runtime: real
agent pods on docker + kubernetes over a NATS/JetStream bus, Vault secrets, a two-axis deploy, and a
stateless gateway. What is still authored from scratch is the **application** itself — a developer (or
an agent) facing a blank `main.go` re-derives the composition root, the HTTP pipeline layout, the data
layer, and the deploy wiring every time, with no enforced discipline and every freedom to drift from
the library contracts.

IOTEA's prior art shows the alternative: applications are instantiated from a **template** that
assembles the shared libraries one way — a pure composition root, a typed data layer, an OpenAPI
contract, a uniform request pipeline. The libraries (`edenhttp`, `secrets`, `observability`,
`configuration`, `errors`, `orchestrator`, `workspaceprovider`, `deploy/servicespec`) already own every
hard part; an application template's job is **composition discipline**, not reimplementation.

This ADR rules the application-template system and its first instance, `http-gateway`. The detailed
build spec is `docs/architecture/16-application-template-system.md` (ADR-0010 four-class scheme).

## Decision

### 1. A new `application-templates` git submodule

Application templates live in a NEW submodule, `gophersys/application-templates`, mounted at
`application-templates/` (peer of `libs/`, `infrastructure/`, `.devcontainer/`). Its layout mirrors
`libs/`: an `_ctl/template.sh` shared dispatcher (verb bodies once, mirroring `libs/go/_ctl/lib.sh`),
an ecosystem subtree (`go/`), and thin per-template `ctl.sh` dispatchers + `project.json` Nx wiring.
The four-phase phase-gate pipeline of ADR-0020 is REUSED for templates (architecture → implementation
→ testing → qa); an app is "done" only past `phase-gate qa`.

### 2. sqlc over pgx for the data layer

The data layer is `persistence/` = `schema/` + `migrations/` + sqlc-`generated/`: typed queries
emitted by sqlc against a checked schema, NOT string-built SQL. `persistence/` is its own Nx codegen
sub-project; migrations apply to the REAL postgres in the integration lane. The package/dir name is
`persistence` (HNS-1: never `db`/`repo`/`store`). A route's `execute` stage is the only one that
touches the Querier, through an injected port.

### 3. The 5-files-per-route rule; authz is a field, not a file

Every route is exactly five files — `route.go` / `parse.go` / `validate.go` / `execute.go` /
`effect.go` — each owning one stage of the edenhttp 6-stage pipeline. **Authorization is the
declarative `Required Grant` field on the `edenhttp.Handler`** the `route.go` assembles, NOT a sixth
file or a bespoke middleware: the pipeline's AUTHORIZE stage checks the verified `Identity` covers it.
The grant grammar stays in `edenhttp` (one concept, one home); the route only names its grant.

### 4. OpenAPI-first + test-client codegen (two codegen axes)

`contract/openapi.yaml` is the architecture of the API surface — a route does not exist until it is
described there. There are exactly two codegen axes, each its own Nx sub-project: **persistence**
(sqlc) and **clients** (oapi-codegen → a typed Go test client in its own module). The testing lane
drives the running handlers THROUGH the emitted client, proving the contract and the implementation
agree. (Whether the SERVER types are also generated — spec-first all the way — is the open fork
OD-16-openapi; the template ships spec-first.)

### 5. Reuse `orchestrator.Substrate`; reuse `deploy/servicespec`; reuse the libs — never reinvent

Substrate detection (docker vs kubernetes) reuses the `orchestrator.Substrate` F1 enum, not a parallel
concept. The deploy surface reuses eden's `deploy/servicespec` renderer (one typed `ServiceSpec` →
both compose + Helm). The composition root assembles the libraries the IOTEA way —
`configuration` → `secrets` (REAL Vault via `vaultadapter`) → `observability` → substrate-detect →
`edenhttp.New` → `signal.NotifyContext` drain — adding NO new HTTP-pipeline, redaction, observability,
provisioning, or rendering code. A template's `go.mod` carries no module-level `replace`; siblings
resolve via the workspace `go.work`.

### 6. `objectstorage` is a gated library, not part of this template

Blob/object storage (presigned uploads, artifact persistence) is a real need many applications share,
but it is a LIBRARY concern (`libs/go/objectstorage`, already seeded in `go.work`) gated through the
ADR-0020 pipeline — NOT something the http-gateway template embeds. A template that needs it assembles
the library at its composition root like any other; the template stays minimal.

### 7. `.claude/` enforcement travels with the template

Each template carries its own `.claude/rules/` (the CRUD authoring loop: add-resource →
five-files-per-route → schema-and-migrations → openapi-and-clients → test-loop) injected at
SessionStart, plus a `hooks/` placeholder for the lifecycle hooks wired at plugin promotion. They
EXTEND the shared `libs/.claude/rules/`, so an agent extending a generated app stays on the same
discipline the template was built on.

## Consequences

- **Easier:** standing up a new Eden service — instantiate the template, add resources by the
  five-file rule, regenerate, gate. The composition root, data layer, deploy, and authoring discipline
  come for free and are uniform across services. Library contracts are honored by construction (the
  template never re-implements them), so the cohesion contract holds across the app/library seam.
- **Harder / now invalid:** authoring an Eden service from a blank `main.go`, or collapsing a route
  into one file, or adding authz as a separate middleware, or hand-writing SQL / a client — the
  phase-gate + the `.claude` rules reject these. A route undocumented in `openapi.yaml` is not
  exercised by the test loop, so drift fails fast.
- **Propagation:** `.gitmodules` gains the submodule; `go.work` gains the two buildable modules
  (`use`) and the `configuration` pin (`replace`); the architecture doc set gains doc 16 and this
  ADR; `open-decisions.md` gains the seven open forks. The HTML render (`node
  docs/tools/render-html.mjs`) must be regenerated (not done here by hand — generated artifact rule).
- **Alternatives rejected:** (a) a generator CLI that emits a one-off app and walks away — rejected
  because it leaves no living discipline (the generated app drifts with no gate); a template that
  STAYS a gated, versioned artifact keeps the bar. (b) Authz as a sixth route file or a route-table
  middleware — rejected because it splits the authorization decision from the handler it guards;
  the `Required` field keeps it co-located and declarative. (c) An ORM over pgx — rejected for sqlc's
  typed-query-against-checked-schema model (no runtime query building, no reflection). (d) Embedding
  object storage in the template — rejected per #6 (it is a gated library concern).
