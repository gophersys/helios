# Rule — OpenAPI go-first-emit & client codegen

> Injected at SessionStart (ADR-0023). OD-16-openapi is resolved **go-first-emit** (RD-17): the Go
> route types are the source of truth; `contract/openapi.yaml` is EMITTED from them, and the clients
> are emitted from the contract.

## The routes are the source of truth, not the YAML

- A route does not exist until its five files exist and it is registered. `contract/openapi.yaml` is
  GENERATED from the route `Request`/`Response` types by `tools/openapi` — **never hand-edit it**.
- After authoring/changing a route, run `bash ./ctl.sh openapi` to re-emit the contract, then
  `bash ./ctl.sh gen-client` to refresh the client (or `bash ./ctl.sh generate` for the full chain).
- `bash ./ctl.sh verify-openapi` fails the architecture gate when the committed contract drifts from
  the route types — so a changed route with a stale contract is caught mechanically.
- The success response wraps the payload in the uniform `edenhttp` Envelope (`{ "data": … }`); the
  emitter renders it as `Envelope_<Payload>`. `security: [{ bearerAuth: [] }]` — every `/v1` route is
  behind the JWT gate; the health probes are NOT in this contract (they are public, pre-identity).

## Emit the clients

- `bash ./ctl.sh gen-client` runs oapi-codegen over the EMITTED contract and writes the typed Go
  client into `clients/go/generated/`. The integration lane drives the running handlers THROUGH this
  client, so the contract and the implementation are proven to AGREE — a documented-but-unimplemented
  route fails, and an implemented-but-undocumented route is never exercised.
- **Never hand-write or hand-edit** anything under `clients/*/generated/` or `contract/openapi.yaml`
  — change the route's Go types and regenerate.

## Why go-first-emit (the rejected forks)

Spec-first (hand-author the YAML) lets the contract drift from the code it documents; emitting the
SERVER types from a YAML that is itself a projection of those types is circular. The route types are
the one typed surface — the YAML and the client are its projections.
