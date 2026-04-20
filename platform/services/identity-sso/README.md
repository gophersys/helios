# platform/services/identity-sso

Single sign-on for cluster-served UIs and APIs. Apps gate routes behind an
SSO middleware; users authenticate once and gain access everywhere.

## Default implementation

Candidates (TBD):
- **Dex** — lightweight OIDC shim, federates to GitHub / Google / Microsoft.
  Lowest operational cost for fleet-of-one.
- **Keycloak** — full-featured but heavy. Adopt only if complex RBAC /
  federated identity / user self-service matters.

Default: **Dex** federated to GitHub (org `gophersys` + MateoSegura) for the
initial operator-only phase.

## Fulfills
- `contracts/identity.md` — how apps gate a route with platform-managed SSO.

## Dependencies
- `platform/core/ingress/` + `cert-manager/`.
- `platform/core/secrets-operator/` — OIDC client secret from Bitwarden.

## Status

STUB — future. Apps today gate with per-app basic auth or token auth.
Populate once the second human needs access to a cluster-served UI.
