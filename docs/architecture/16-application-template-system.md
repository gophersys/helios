# 16 — Application template system

> Status: Draft for review · Created: 2026-06-14 · Owner: Mateo · Ratifies: ADR-0023
> Canonical spec for the Eden **application-template** system: the gated, versioned scaffolds that
> assemble the shared Go libraries into a complete, deployable service. Sits downstream of the
> library system (doc 10), the library pipeline (doc 14, ADR-0020), and Milestone-B (ADR-0022); it
> reuses, never reinvents, what those own.

## 1. Thesis ✅

An Eden **application** is not authored from a blank `main.go`. It is instantiated from an
**application template**: a scaffold that ASSEMBLES the shared `gophersys/libs/go/*` libraries the
IOTEA way — a pure composition root, the edenhttp 6-stage pipeline, a sqlc/pgx data layer, an
OpenAPI-first contract — and is engineered to the SAME bar as a library (the four-phase pipeline, no
shortcuts, real substrates). The unit of reuse is a whole **service shape**, not a single component.

The first template is **`http-gateway`**: an OpenAPI-first, sqlc/pgx HTTP service. It is the worked
reference this spec describes; later templates (a worker, a cron job, an event consumer) are siblings
under the same `_ctl` + phase-gate machinery.

> The libraries already solved every hard part (the HTTP pipeline, redaction, observability,
> substrate provisioning, deploy rendering). A template's job is **composition discipline**, not
> reimplementation — so the cohesion contract (one concept, one home, doc 10 §9) holds across the
> app/library seam too. 🔶

## 2. Where it lives — the submodule 🧩 (ADR-0023 #1)

Application templates live in a **new git submodule**, `gophersys/application-templates`, mounted at
`application-templates/` in the eden monorepo (peer of `libs/`, `infrastructure/`, `.devcontainer/`
in `.gitmodules`). Separate repo, separate commits — the same boundary rule the other submodules
follow.

```
application-templates/
├── _ctl/template.sh        # shared verb bodies + the phase-gate sequencer (one home)
├── go/                     # the Go ecosystem subtree (mirrors libs/go/)
│   └── http-gateway/       # the first template
└── README.md
```

The layout deliberately mirrors `libs/`: an `_ctl/` shared dispatcher library, an ecosystem subtree
(`go/`), thin per-template `ctl.sh` dispatchers. A consumer runs `nx run http-gateway:build` /
`:phase-gate` exactly as for a library — uniform Nx wiring, no special case.

## 3. The control plane — `_ctl/template.sh` + phase-gate ✅ (ADR-0023, mirrors ADR-0020)

The verb BODIES live ONCE in `application-templates/_ctl/template.sh` (the app-side analogue of
`libs/go/_ctl/lib.sh`); each per-template `ctl.sh` is a thin dispatcher that sets its metadata (the
slug, the coverage floor, the integration tools, the codegen sub-projects) and sources the shared
library. This is "one concept, one home" applied to the build verbs (doc 10 §9).

The four-phase SDLC pipeline of ADR-0020 is REUSED, not re-invented — a template is gated
phase-by-phase:

| Phase | Gate (`bash ./ctl.sh phase-gate <phase>`) checks |
|---|---|
| **architecture** | the frozen contract is present (`contract/openapi.yaml`) + the skeleton compiles |
| **implementation** | build + vet + lint (shared strict config) + the fake conformance GREEN |
| **testing** | unit + the integration lane on REAL substrate (postgres, k3d/kind) + coverage |
| **qa** | vuln + sast + secretscan + maintainability (hnslint) + the no-shortcuts grep (ADR-0017) |

`phase-gate all` runs 1→4 short-circuiting. An application is "done" only past `phase-gate qa`.
"phase" is the SDLC step — never the environment "stage" (the pipeline-vocabulary rule).

## 4. The data layer — sqlc over pgx ✅ (ADR-0023 #2)

`persistence/` is the typed data layer, NOT string-built SQL:

- `schema/schema.sql` — the DDL sqlc type-checks queries against.
- `schema/queries/*.sql` — named queries (`-- name: X :one|:many|:exec`); sqlc emits one typed Go
  method each.
- `migrations/NNNN_*.sql` — numbered goose-style up/down migrations that APPLY the schema to a real
  database; the integration lane runs them against the REAL postgres.
- `generated/` — the sqlc output (the Querier + row models). Generated, never hand-edited.

`persistence/` is its own Nx codegen sub-project (`http-gateway-template-persistence`) so the data
layer regenerates independently; the parent template's `generate` verb delegates to it. The
package/dir name is `persistence` — never `db`/`repo`/`store` (HNS-1 rule 11). A route's **execute**
stage is the only one that touches the Querier, and it calls it through an injected port.

## 5. OpenAPI-first + the two codegen axes ✅ (ADR-0023 #4)

`contract/openapi.yaml` is the **architecture of the API surface**: a route does not exist until its
path + operation + schema are described there. There are exactly **two codegen axes**, each its own
Nx sub-project, both driven by the parent `generate` verb:

| Axis | Sub-project | Source → Output |
|---|---|---|
| **persistence** | `…-persistence` | `schema/` + queries → `persistence/generated/` (sqlc, pgx/v5) |
| **clients** | `…-client-go` | `contract/openapi.yaml` → `clients/go/generated/` (oapi-codegen) |

The emitted Go client is the **test/integration client**: the testing lane drives the running
handlers THROUGH it, so the contract and the implementation are proven to AGREE — a
documented-but-unimplemented route fails, an implemented-but-undocumented one is never exercised. The
client lives in its OWN Go module so its codegen deps never enter the gateway's dependency graph.

> Whether the SERVER types are also generated from the spec (spec-first all the way) or the spec is
> EMITTED from the handler types (code-first) is the **open fork OD-16-openapi**. The template ships
> spec-first; the generator axis is wired so either resolution is a small change. 🧩

## 6. The 5-files-per-route rule ✅ (ADR-0023 #3)

Every route is one `edenhttp.Handler[Request, Response]` decomposed into EXACTLY five files, each
owning one stage of the edenhttp 6-stage pipeline (the pipeline lives in `edenhttp`; the rule is how
a route is laid out over it):

| File | Stage | Owns |
|---|---|---|
| `route.go` | (assembly) | wire the handler from the four stage funcs, **declare `Required`** (the Grant), register the route |
| `parse.go` | PARSE | decode the request into the typed `Request` |
| `validate.go` | VALIDATE | check the parsed input is well-formed (pure — no port) |
| `execute.go` | EXECUTE | the business step → typed `Response` (the ONLY stage that touches a port) |
| `effect.go` | ACTION | the after-respond side effect (audit/telemetry); its error is logged, never surfaced |

**Authorization is NOT a sixth file.** It is the declarative `Required Grant` field on the
`edenhttp.Handler` the `route.go` assembles — the pipeline's AUTHORIZE stage checks the verified
`Identity` holds a grant that `Covers` it. The grant grammar lives once in `edenhttp`; the route only
NAMES its grant (`edenhttp.NewGrant("ns", "action")`). The worked reference is
`internal/api/v1/ping/`.

> Why five, not one: each stage is independently testable (validate is pure; execute is the only port
> touch), every route is decomposed the SAME way, and the no-shortcuts gate is meaningful (a
> half-built route is a missing stage, not buried in a 200-line handler). 🔶

## 7. Libs assembly — the IOTEA way ✅ (ADR-0023 #5)

The composition root (`cmd/gateway/main.go`) owns ONLY the wiring; the libraries own all behavior. It
assembles them in order, each through its `New(configuration, dependencies)` spine:

| Step | Library | What the composition root does |
|---|---|---|
| 1 | `configuration` | parse the process environment ONCE at the edge into the frozen `Environment`; a missing required value is a typed startup error |
| 2 | `secrets` (+ `vaultadapter`) | build the redaction `Mediator` over the REAL Vault backend (token-file in kubernetes, userpass locally); the ONLY place a credential value is resolved |
| 3 | `observability` (+ `slogadapter`) | build the `Provider` the server emits structured Events on; the stage value arrives here (doc 10 §2) |
| 4 | substrate detect | `internal/server/runtime.DetectSubstrate` reuses `orchestrator.Substrate` (the F1 enum) — docker vs kubernetes, by the projected SA-token / hint |
| 5 | `edenhttp` | `server.New` resolves the JWT secret once (via `secrets.Use`, zeroized) → builds the dev-JWT `HMACVerifier` → `edenhttp.New` spine → mounts the public probes + the authenticated `/v1` routes |
| 6 | stdlib `signal` | `signal.NotifyContext(SIGINT, SIGTERM)` → serve → graceful `Shutdown` drain |

The deploy surface (`deploy/servicespec.go`) REUSES eden's `deploy/servicespec` renderer (ADR-0022
#2): one typed `ServiceSpec` renders to BOTH a docker-compose service and a Helm chart — no
hand-maintained drift, no re-implemented rendering. The substrate-detect reuses
`orchestrator.Substrate` rather than minting a parallel "docker | kubernetes" concept.

**Reuse, never reinvent** is the load-bearing invariant: the template adds composition + the
five-file route discipline + the two codegen axes; it adds NO new HTTP-pipeline, redaction,
observability, provisioning, or rendering code.

## 8. AI instrumentation — `.claude/` enforcement ✅ (ADR-0023)

Each template carries its own `.claude/rules/` injected at SessionStart, so an agent extending a
GENERATED app follows the same discipline the template was built on (the CRUD authoring loop):

| Rule | Scope |
|---|---|
| `00-add-resource.md` | the ordered loop (contract → five files → schema/migration → regenerate → test) |
| `10-five-files-per-route.md` | the cardinal structural rule; authz is the `Required` field |
| `20-schema-and-migrations.md` | sqlc-over-pgx; the schema/migration lockstep; typed queries |
| `30-openapi-and-clients.md` | OpenAPI-first; emit the clients; never hand-edit generated |
| `40-test-loop.md` | the phase-gate sequence + the no-shortcuts / real-substrate bar |

These EXTEND the shared `libs/.claude/rules/` (naming, interface-design, error-handling, the library
pipeline, the test taxonomy) — those still apply; these add the app shape. `.claude/hooks/` is a
placeholder for the lifecycle hooks (SessionStart inject, PostToolUse lint, PreToolUse/Stop
phase-gate), wired when the template is promoted to a registered plugin (mirroring
`libs/plugins/project-go/`).

## 9. Module & workspace facts ✅

- A template's `go.mod` requires the `gophersys/libs/go/*` siblings at `v0.0.0` and carries **NO
  module-level `replace`** — the monorepo `go.work` owns sibling resolution (the standing rule).
  `go.work` gains `application-templates/go/http-gateway` and its `clients/go` in the `use` block,
  and `configuration` in the workspace `replace` block (the +incompatible-graph pin the vault SDK
  forces, same as the other libs).
- The `deploy/` and `clients/go/` directories are SEPARATE Go modules: deploy is a build-time
  renderer (GOWORK=off, a `replace` to the in-repo `deploy/servicespec` — the sanctioned exception,
  since servicespec is a build-tool module deliberately kept out of `go.work`, not a `go.work`
  sibling); the client module isolates its codegen deps from the gateway's graph.
- **Devcontainer-first**: every Go verb runs in `base-devcontainer` over `/workspace`; the skeleton
  builds, vets, and lints clean in-container (`go build ./...`, the shared `libs/.golangci.yml`).

## 10. Open forks (register, not prose) 🧩

Recorded in `docs/architecture/open-decisions.md` (OD-15-bom, OD-16-pagination, OD-16-openapi,
OD-16-row-authz, OD-16-roles, OD-16-chart, OD-16-secrets-injection). They are not blockers: each is a
field/value/render-target change against the shipped skeleton, not a redesign.
