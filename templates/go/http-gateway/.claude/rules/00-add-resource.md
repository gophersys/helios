# Rule — Adding a resource (the CRUD authoring loop)

> Injected at SessionStart for the http-gateway template (ADR-0023). This is the ordered loop for
> adding or extending a resource. Each step has its own rule; do them IN ORDER. The `phase-gate`
> enforces the result — this rule keeps you on the rails while you author.

A "resource" is a noun the API exposes (e.g. `widget`, `order`). Adding one is always the same five
steps, in order (go-first-emit, RD-17 — the routes are the source of truth, the contract is emitted):

1. **The five route files.** Author each route as exactly five files under
   `internal/api/v1/<resource>/<verb>/`: `route.go` / `parse.go` / `validate.go` / `execute.go` /
   `effect.go`, and declare the `Required` Grant + `Request`/`Response` types in `route.go`. See
   `10-five-files-per-route.md`. Register it in `internal/api/v1/mount.go`. The Go types ARE the
   contract's source of truth.
2. **Schema + migration.** If the resource is persisted, add the DDL to
   `persistence/schema/schema.sql`, a NEW numbered migration to `persistence/migrations/`, and the
   queries to `persistence/schema/queries/`. See `20-schema-and-migrations.md`.
3. **Emit the contract + clients.** `bash ./ctl.sh generate` — emit `contract/openapi.yaml` FROM the
   route types, refresh the sqlc Querier, and emit the OpenAPI client. See `30-openapi-and-clients.md`.
4. **Register the operation** in `tools/openapi/operations.go` (method + path + operationId + grant)
   so the emitted contract documents the new route — the one place the route table is projected.
5. **Test loop.** Unit-test each stage, then the integration lane against the REAL substrate. See
   `40-test-loop.md`. The resource is done only when `bash ./ctl.sh phase-gate qa` is green.

## Hard rules

- **Never hand-edit the contract.** `contract/openapi.yaml` is EMITTED from the route types; a route
  whose types changed but whose contract was not re-emitted is drift — `verify-openapi` fails the
  architecture gate, and the test loop drives the running handler through the EMITTED client (an
  undocumented route is not exercised, a documented-but-unimplemented one fails).
- **Never collapse the five files** into one, and **never add a sixth for authz** — authorization is
  the `Required` field on the `edenhttp.Handler` (rule 10).
- **Never hand-edit a generated file** (`persistence/generated/`, `clients/go/generated/`) — change
  the source (schema/queries/contract) and regenerate.
- **Full HNS-1 names** — `identity` not `auth`, `persistence` not `db`/`repo`/`store`,
  `configuration` not `config`; `util`/`common`/`core` are banned (the shared `11-naming` rule).
