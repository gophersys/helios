---
contract: ingress
version: 0.1.0-draft
fulfilled_by: platform/core/ingress/ + platform/core/cert-manager/
---

# ingress

## Abstract

Apps expose HTTP routes by declaring an `Ingress` (or Traefik `IngressRoute`).
The platform handles TLS (automatic via cert-manager), DNS (via cluster-wide
wildcard records), and routing to the app's Service.

## Interface (TBD)

### Declaration
Auto-emitted by the chart archetype from `values.ingress`. Rendered form:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <project>-<app>                    # e.g., codectl-api
  namespace: <project>-<env>               # e.g., codectl-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: platform
  tls:
    - hosts: [<hostname>]                  # from values.ingress.host
      secretName: <project>-<app>-tls      # e.g., codectl-api-tls
  rules:
    - host: <hostname>
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: <project>-<app>
                port:
                  number: 80
```

Or the Traefik IngressRoute CRD for advanced routing.

### Domain allocation (recommended)

Per-project subdomain with per-app prefix — avoids name collisions
across projects:

- `<app>.<project>.<cluster-domain>` — e.g.,
  `api.codectl.brain.mateosegura.com`, `dashboard.codectl.brain.mateosegura.com`.
- `<app>.<project>.<cluster-domain>` via wildcard DNS
  (`*.codectl.brain.mateosegura.com`) per project; certs issued
  per-host by cert-manager.
- Platform hostnames reserved: `grafana.<cluster-domain>`,
  `prometheus.<cluster-domain>`, etc.

Apps are free to override `values.ingress.host` with any host they own
(e.g., `app.mateosegura.com` for a public-facing product).

## Guarantees (TBD)

- TLS certs renew automatically (cert-manager, 30 days before expiry).
- Wildcard DNS record per project points to the cluster's ingress LB;
  per-app records unnecessary as long as they're under `*.<project>.<cluster-domain>`.
- Cross-project route isolation — an ingress in `codectl-prod` cannot
  serve a host assigned to `fintel-prod` (admission validates host
  ownership).

## Caveats (TBD)

- Large payloads/slow clients are subject to platform-level timeouts
  (default 60s; overridable per IngressRoute).
- WebSockets and gRPC work but require explicit annotations.
- DNS delegation for the per-project subdomains must be set up once at
  cluster bring-up; adding a new project requires a DNS record update.

## Example (TBD)
