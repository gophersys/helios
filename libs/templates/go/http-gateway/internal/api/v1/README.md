# internal/api/v1 — the versioned API resources (the 5-files-per-route rule)

> Directory README. This is the home of the gateway's RESOURCES. Every route is authored as exactly
> five files; authorization is a declarative field, never a sixth file (ADR-0023).

## The 5-files-per-route rule

A route is one `edenhttp.Handler[Request, Response]` and exactly five files, each owning one pipeline
stage:

| File | Stage | Owns |
|---|---|---|
| `route.go` | (assembly) | Wire the handler from the four stage funcs, DECLARE the `Required` Grant, register the route on the mux. Authorization is THIS field — `Required: NewGrant("ns","action")` — not a file. |
| `parse.go` | PARSE | Decode the request into the typed `Request` (body / path / query). No validation, no logic. |
| `validate.go` | VALIDATE | Check the parsed input is well-formed. Pure — touches no port. A bare error → 400. |
| `execute.go` | EXECUTE | The business step → the typed `Response`. The ONLY stage that may touch a port (persistence, upstream). Runs after authn + authz. |
| `effect.go` | ACTION | After-respond side effect (audit, metric, domain event). Its error is logged, never surfaced. |

## The worked example

`ping/` is the complete, compiling reference: `GET /v1/ping`, requiring `ping:read`, echoing the
caller's subject + a server timestamp. It is the five files end to end — copy its shape to add a
resource. `mount.go` is the single place the resource set is composed (one auditable read of the
route table).

## Authoring a new resource

Follow `.claude/rules/00-add-resource.md` → `10-five-files-per-route.md`: scaffold the five files,
declare the Grant, add the schema + migration (`20-schema-and-migrations.md`), update
`contract/openapi.yaml` and regenerate the clients (`30-openapi-and-clients.md`), then the test loop
(`40-test-loop.md`). The `phase-gate` enforces it.
