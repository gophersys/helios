---
contract: identity
version: 0.1.0-draft
fulfilled_by: platform/services/identity-sso/
status: future
---

# identity (SSO)

## Abstract

Apps gate routes behind platform-provided SSO. Users authenticate once via
the cluster-wide identity provider; downstream apps see authenticated
requests with user claims in headers (or via forwarded OIDC tokens).

## Interface (TBD)

### Protecting a route
Apps annotate their `IngressRoute` or `Ingress` with:

```yaml
metadata:
  annotations:
    platform.gophersys/auth: sso
    platform.gophersys/auth-required-groups: "admins,operators"
```

The platform's ingress middleware intercepts, bounces to SSO, and forwards
the user's identity as:
- `X-Auth-User`: stable user ID
- `X-Auth-Email`: email
- `X-Auth-Groups`: comma-separated groups
- `Authorization: Bearer <oidc-token>` (when forwarding is enabled)

### Platform-issued tokens
Apps calling other apps (service-to-service): use the platform's internal
issuer to mint short-lived tokens; downstream apps validate via the
platform's JWKS endpoint.

## Guarantees (TBD)

- User identity is verified at the edge (middleware); downstream apps trust
  the forwarded headers as long as they only accept traffic via the
  platform ingress.
- Tokens are short-lived (≤15 min) with refresh via SSO provider.

## Caveats (TBD)

- Service-to-service tokens require network isolation (default-deny
  NetworkPolicy) — otherwise an attacker bypasses the edge.
- Long-running background jobs need token refresh logic.

## Example (TBD)

Deferred — implementation is future work.
