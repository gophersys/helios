---
contract: identity
version: 0.1.0-draft
fulfilled_by: platform/services/identity-sso/
status: future
---

# identity (SSO)

## Abstract

An app gates a route behind the SSO that the platform provides. A user
authenticates once with the cluster-wide identity provider. The app downstream
then sees authenticated requests, with the user claims in the headers or in a
forwarded OIDC token.

## Interface (TBD)

### Protect a route
An app annotates its `IngressRoute` or `Ingress` with:

```yaml
metadata:
  annotations:
    platform.gophersys/auth: sso
    platform.gophersys/auth-required-groups: "admins,operators"
```

The ingress middleware of the platform intercepts the request, sends it to SSO,
and forwards the identity of the user as:
- `X-Auth-User`: the stable user ID
- `X-Auth-Email`: the email address
- `X-Auth-Groups`: the groups, separated by commas
- `Authorization: Bearer <oidc-token>` (when forwarding is enabled)

### Tokens issued by the platform
For an app that calls another app (service to service): use the internal issuer
of the platform to mint short-lived tokens. The app downstream validates them
through the JWKS endpoint of the platform.

## Guarantees (TBD)

- The middleware verifies the user identity at the edge. An app downstream can
  trust the forwarded headers, as long as it accepts traffic only through the
  platform ingress.
- A token is short-lived (15 minutes or less), and the SSO provider refreshes it.

## Caveats (TBD)

- A service-to-service token requires network isolation (a default-deny
  NetworkPolicy). Without it an attacker can bypass the edge.
- A background job that runs for a long time needs logic to refresh the token.

## Example (TBD)

Deferred, because the implementation is future work.
