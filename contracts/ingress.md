---
contract: ingress
version: 0.1.0-draft
fulfilled_by: platform/core/ingress/ + platform/core/cert-manager/
---

# ingress

## Abstract

Apps expose HTTP routes by declaring an `Ingress` (or Traefik `IngressRoute`).
The platform handles TLS (automatic via cert-manager), DNS (via cluster-wide
wildcard record), and routing to the app's Service.

## Interface (TBD)

### Declaration
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app>
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: platform
  tls:
    - hosts: [<app>.<cluster-domain>]
      secretName: <app>-tls
  rules:
    - host: <app>.<cluster-domain>
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: <app>
                port:
                  number: 80
```

Or the Traefik IngressRoute CRD for advanced routing.

### Domain allocation
- `<app>.<cluster-domain>` — standard app route.
- `<app>.api.<cluster-domain>` — API-only variant (e.g., gRPC reserved).
- Platform-level hostnames (`grafana.<cluster-domain>`, etc.) are reserved.

## Guarantees (TBD)

- TLS certs renew automatically (cert-manager, 30 days before expiry).
- Wildcard DNS record points to the cluster's ingress LB; per-app records
  unnecessary.

## Caveats (TBD)

- Large payloads/slow clients are subject to platform-level timeouts
  (default 60s; overridable per IngressRoute).
- WebSockets and gRPC work but require explicit annotations.

## Example (TBD)
