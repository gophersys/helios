# clients — the emitted API clients (codegen axis #2)

> Directory README. The typed clients are EMITTED from `contract/openapi.yaml` (ADR-0023:
> OpenAPI-first → test-client codegen), never hand-written to drift from the handlers.

## go/ — the Go test/integration client

`go/` is its own Nx codegen sub-project (`http-gateway-template-client-go`) and its own Go module.
`bash go/ctl.sh generate` runs `oapi-codegen` over `../../contract/openapi.yaml` and emits a typed
client (request/response models + a `Client` with one method per `operationId`) into
`go/generated/`. The integration lane drives the running handlers through this client, so the
contract and the implementation are proven to AGREE — not assumed to.

Why a separate module: the regenerated client never breaks the gateway module's `go build ./...`,
and oapi-codegen's runtime deps stay out of the gateway's dependency graph.

## Adding more clients

Other language clients (a TypeScript client for a Svelte frontend, …) are added as sibling
sub-projects under `clients/<lang>/`, each emitting from the same `contract/openapi.yaml` — one
contract, N emitted clients.
