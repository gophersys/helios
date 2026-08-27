# contract — the EMITTED OpenAPI contract (go-first-emit)

> Directory README. `openapi.yaml` is GENERATED, not hand-authored (ADR-0023; OD-16-openapi resolved
> **go-first-emit**, RD-17). The five-file route packages' Go `Request`/`Response` types are the
> authoring surface; this contract is EMITTED from them, and the typed clients (`clients/`) are
> emitted from the contract. A route does not exist until its types exist and it is registered.

## go-first-emit (the resolved ruling)

OD-16-openapi is ruled **go-first-emit** (RD-17): the Go route types are the single source of truth.
`tools/openapi` reflects the route `Request`/`Response` types into `openapi.yaml`, so the contract
can never silently drift from the code. The spec-first option (hand-author the YAML) and the
full-emit-of-server-types option are both rejected — the routes ARE the typed surface.

```bash
bash ./ctl.sh openapi          # EMIT openapi.yaml from the Go route types
bash ./ctl.sh verify-openapi   # re-emit and FAIL if the contract drifts (the architecture gate)
bash ./ctl.sh gen-client       # oapi-codegen the typed Go client from the contract
bash ./ctl.sh generate         # the full chain: openapi → persistence (sqlc) → gen-client
```

`DO NOT hand-edit openapi.yaml` — change a route's `Request`/`Response` Go type and re-emit. The
`phase-gate architecture` step runs `verify-openapi` (a drift is a gate failure); the
`phase-gate testing` step exercises the emitted client against the running handlers on REAL postgres
(the contract, the routes, and the data layer are proven to agree, not assumed to).
