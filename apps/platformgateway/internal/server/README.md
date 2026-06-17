# internal/server — the assembled HTTP surface

> Directory README. The server package is the gateway's pure assembly point: `server.New(Config,
> Deps)` builds the edenhttp spine and mounts the probes + v1 routes behind its authentication
> Middleware. New is pure (no I/O) — the composition root (`cmd/gateway`) does the wiring.

| Sub-package | Intent |
|---|---|
| `server.go` | `New` + `Handler()` — assemble the edenhttp spine, resolve the JWT secret once, mount the route tree (public probes + authenticated `/v1`). |
| `middleware/` | Cross-cutting HTTP seams that are NOT the spine's own. Today: the `observability.Provider` → `edenhttp.Logger` adapter. A generated app adds request-id / panic-recovery / CORS wrappers here. |
| `healthcheck/` | The kubelet probes — `live.go` (process up) and `ready.go` (dependencies reachable). PUBLIC routes, mounted OUTSIDE auth. |
| `runtime/` | Deployment-substrate detection (`DetectSubstrate`), reusing `orchestrator.Substrate` — docker vs kubernetes. |
| `identity/` | Builds the request-identity verifier from the secrets seam (the dev-JWT `HMACVerifier` over the resolved signing key). HNS-1: the concept is `identity`, never `auth`. |
| `bom/` | The services Bill-of-Materials manifest (which library + contract versions a running gateway was built from). Sourcing is an OPEN fork (A/B/C — see open-decisions). |

The 5-files-per-route rule lives in `internal/api/v1/` (the resources), not here — the server only
COMPOSES the routes; it does not author them.
