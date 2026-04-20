# platform/core/ingress

HTTP(S) ingress controller. Terminates external traffic; apps declare
`Ingress` or `IngressRoute` resources to become reachable.

## Default implementation

**Traefik** (Helm chart: `traefik/traefik`) chosen for:
- First-class CRD-based routing (IngressRoute, Middleware).
- Built-in Let's Encrypt support if we ever need it without cert-manager.
- Dashboard good enough for fleet-of-one ops.

Alternative: `ingress-nginx` if an app needs strict upstream nginx semantics.

## Fulfills
- `contracts/ingress.md` — how apps expose HTTPS routes with automatic TLS
  + DNS via the platform.

## Dependencies
- `platform/core/cni/` (pod networking)
- `platform/core/cert-manager/` (TLS issuance; this component creates the
  ingress, cert-manager issues the cert)

## Status

STUB. Only the README is here — no chart wiring yet.

## TODO (when populating)
- Pin traefik chart version.
- Parameterize default TLS resolver per cluster (DNS-01 when a DNS provider
  credential is wired, HTTP-01 otherwise).
- Wire Dashboard behind the `identity-sso` service (future).
