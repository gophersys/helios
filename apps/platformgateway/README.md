# http-gateway (application template)

> Directory README · the first Eden application template (ADR-0023, spec
> `docs/architecture/16-application-template-system.md`). An OpenAPI-first, sqlc/pgx HTTP service
> that ASSEMBLES the Eden Go libraries the IOTEA way.

## What you get

A production-shaped HTTP service, compiling and ready to extend:

- A **pure composition root** (`cmd/gateway`) that wires the libraries in order: `configuration`
  → `secrets` (Vault) → `observability` → substrate-detect → `server.New` → `signal.NotifyContext`
  drain. The libraries own all behavior; this owns only the wiring.
- The **edenhttp 6-stage handler pipeline** behind a dev-JWT identity gate (behind auth even
  locally), with the health probes mounted public.
- The **5-files-per-route rule** (`internal/api/v1/`): every route is
  `route.go`/`parse.go`/`validate.go`/`execute.go`/`effect.go`, authorization a declarative
  `Required` Grant — the worked `ping` resource is the reference.
- A **sqlc/pgx data layer** (`persistence/`) and an **OpenAPI contract** (`contract/openapi.yaml`)
  that emits the typed test client (`clients/go/`) — the two codegen axes.
- A **two-axis deploy surface** (`deploy/`) rendered from eden's `deploy/servicespec`.

## Layout

```
http-gateway/
├── ctl.sh                  # thin dispatcher → ../../_ctl/template.sh
├── project.json            # Nx app wiring
├── go.mod / go.sum         # requires gophersys/libs/go/* (resolved via the workspace go.work)
├── cmd/gateway/            # the composition root (main.go + environment.go)
├── internal/
│   ├── server/             # server.New + Handler(); middleware/, healthcheck/, runtime/, identity/, bom/
│   └── api/v1/             # the versioned resources — the 5-files-per-route rule (ping/ is the example)
├── contract/openapi.yaml   # OpenAPI-first — the API's source of truth
├── persistence/            # sqlc/pgx data layer (Nx codegen sub-project)
├── clients/go/             # the emitted Go test client (Nx codegen sub-project, own module)
├── deploy/                 # Dockerfile + the typed ServiceSpec (reuses deploy/servicespec)
└── .claude/                # the CRUD-authoring rules injected at SessionStart
```

## Build, test, gate (devcontainer-first)

```bash
docker exec -u dev -w /workspace/libs/templates/go/http-gateway base-devcontainer \
  bash -lc 'bash ./ctl.sh build'              # compile (go build ./...)
# ... test | lint | generate | integration | phase-gate <architecture|implementation|testing|qa|all>
```

The sibling `gophersys/libs/go/*` modules resolve through the monorepo's `go.work`; this module's
`go.mod` carries NO module-level `replace`. A library is "done" only past `phase-gate qa`.
