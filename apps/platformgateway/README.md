# platformgateway

> Directory README · Eden's **platform HTTP API** — the SaaS-side gateway (users, identity, login)
> the frontend talks to via the `/platform` vite proxy. Generated from the `http-gateway`
> application template (ADR-0023/0026, spec `docs/architecture/16-application-template-system.md`)
> and then specialized; it keeps the template's engineering bar (5-files-per-route, sqlc/pgx,
> OpenAPI-first, phase-gate) — "Eden builds Eden".

## What it serves

Behind the edenhttp 6-stage pipeline and the dev-JWT identity gate (behind auth even locally):

- `GET /ping` — the template's worked reference route (kept as the living example).
- `GET /users` + `GET /users/{id}` — the users read-slice (list paginated, get by id).
- `GET /me` — the caller's own identity, resolved from the verified JWT.

Public (pre-identity, mounted by the server composition, not the v1 mux):

- `POST /auth/login` — password login against the seeded users → a signed dev-JWT.
- `GET /bootstrap/default-user` — the login screen's bootstrap (the seeded default identity).
- `GET /healthz/live` + `GET /healthz/ready` — probes.

## The data layer

`persistence/` is sqlc-over-pgx with three migrations (`0001_create_users`, `0002_create_rbac`,
`0003_create_accounts`) run by an IOTEA-style embedded migrate-then-seed at startup. The
integration lane drives the running handlers through the emitted OpenAPI client against a REAL
postgres (never a mock — ADR-0016 §2).

## Running it

- Local dev: via eden's `deploy/ctl.sh` platformgateway-live path — Vault seeds
  `platformgateway-jwt-signing-key` / `platformgateway-database-dsn`, the frontend proxies
  `/platform` → the gateway.
- Image: `docker build -f apps/platformgateway/deploy/Dockerfile -t platformgateway:local .` from
  the MONOREPO ROOT (the build stage regenerates the gitignored go.work via
  `scripts/gen-go-work.sh`).
- Gates: `bash ./ctl.sh phase-gate all` in the devcontainer — the same four-phase ADR-0020
  sequence as every lib.

## Layout

The template shape, kept: `cmd/gateway/` (pure composition root), `internal/api/v1/<resource>/`
(five files per route + declarative `Required` grants, registered in `internal/api/v1/mount.go`),
`internal/server/` (spine + middleware + healthcheck + identity verifier), `persistence/` (schema,
migrations, queries, generated Querier), `contract/openapi.yaml` (EMITTED from the route types —
never hand-edited), `clients/go/` (the emitted typed client the integration lane drives), and
`.claude/` (the CRUD-authoring rules injected at SessionStart).
