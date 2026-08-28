# deploy — the two-axis deploy surface

> Directory README. The gateway deploys as ONE typed `ServiceSpec` rendered to BOTH a
> docker-compose service (local) and a Helm chart template (production), REUSING eden's
> `deploy/servicespec` renderer (ADR-0023: reuse, never reinvent). One Dockerfile;
> image-tag-as-environment-contract.

| File | Intent |
|---|---|
| `servicespec.go` | `Spec()` — the gateway's typed `ServiceSpec` (port, env NAMES + Secret references, probes). `RenderCompose` / `RenderHelm` delegate to the reused eden renderer. Its OWN module (a build-time renderer, out of go.work; `replace` resolves servicespec from the superproject). |
| `Dockerfile` | The single build, distroless non-root runtime. Built from the monorepo root with the go.work in context. |

## Secrets never inline

The env carries NAMES and Vault/Secret REFERENCES only — never a value. The JWT signing key is
`EDEN_GATEWAY_JWT_SECRET_REF` (a `vault://…` reference); the composition root resolves it through the
Vault sidecar at startup (the secrets no-leak contract). The rendered compose/Helm manifests are
value-free by construction.

## The chart-granularity fork (OPEN)

Whether each application template ships its OWN chart or shares one umbrella chart across templates
is an OPEN fork (recorded in `docs/architecture/open-decisions.md`). Today the gateway renders a
standalone service via the shared renderer; either resolution is a render-target change, not a
rewrite.
