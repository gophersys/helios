# libs/templates

> Directory README · Eden application-template system (ADR-0023; folded into `libs` per ADR-0026;
> canonical spec `docs/architecture/16-application-template-system.md`). This subtree lives in the
> `gophersys/libs` submodule — a sibling of `go/` and `typescript/` — so a template is versioned
> WITH the libraries it assembles and a lib change + its template update land in one atomic commit.

Eden application **templates** are gated, versioned scaffolds that ASSEMBLE the shared Go
libraries (`gophersys/libs/go/*`) into a complete, deployable service the IOTEA way — they do
not reinvent anything the libs already own. A template is the app-side analogue of a `libs/go`
library: engineered to the same bar (the four-phase pipeline, no shortcuts, real substrates), but
the unit of reuse is a whole **service shape**, not a single component.

## Layout

```
libs/templates/
├── _ctl/template.sh        # shared verb bodies + the phase-gate sequencer (one home; thin per-template dispatchers source it)
├── go/                     # Go application templates (one ecosystem subtree, mirroring libs/go/)
│   └── http-gateway/       # the first template: an OpenAPI-first, sqlc/pgx HTTP service
└── README.md               # (this file)
```

Each template under `go/<name>/` is an **Nx-workspace fragment**: a thin `ctl.sh` dispatcher +
`project.json` whose targets delegate to it, plus the codegen sub-projects it owns. A consumer
runs `nx run http-gateway:build` / `:test` / `:phase-gate` without reading source — uniform with
every other Nx project in the monorepo.

## The http-gateway template (the first one)

A production-shaped HTTP service: a pure composition root, the edenhttp 6-stage handler pipeline,
a sqlc/pgx data layer, an OpenAPI-first contract that emits a typed test client, and a deploy
surface rendered from the typed `deploy/servicespec`. Its load-bearing rules:

- **The 5-files-per-route rule.** Every route is exactly five files —
  `route.go` / `parse.go` / `validate.go` / `execute.go` / `effect.go` — and authorization is
  NOT a sixth file: it is the declarative `Required` Grant field on the `edenhttp.Handler` the
  `route.go` assembles. One concept (the request pipeline) decomposed one way, every time.
- **OpenAPI-first.** `contract/openapi.yaml` is the architecture; the typed clients are EMITTED
  from it (`clients/go/`), never hand-written to drift from the handlers.
- **sqlc over pgx.** `persistence/` is `schema/` + `migrations/` + sqlc-`generated/`; the data
  layer is typed, not string-built.
- **Reuse, never reinvent.** The libs are assembled at the composition root:
  `configuration` → `secrets` → `observability` → substrate-detect (`orchestrator.Substrate` /
  `workspaceprovider`) → `edenhttp.New` → `signal.NotifyContext` drain. The deploy surface reuses
  `deploy/servicespec`.

## Authoring is instrumented

`go/<name>/.claude/rules/` injects the CRUD-authoring rules (add-resource → 5-files-per-route →
schema/migrations → openapi/clients → test-loop) at SessionStart, so an agent extending a
generated app follows the same five-file discipline the template was built on. The template's own
`phase-gate qa` (`bash ./ctl.sh phase-gate qa`) must be green before the app is "done".

## Working on a template

Develop **inside the devcontainer** (devcontainer-first). Sibling `gophersys/libs/go/*` modules
resolve through the monorepo's `go.work` — a template's `go.mod` carries NO module-level
`replace`. Run every Go verb in-container:

```bash
docker exec -u dev -w /workspace/libs/templates/go/http-gateway base-devcontainer \
  bash -lc 'bash ./ctl.sh build'
```
