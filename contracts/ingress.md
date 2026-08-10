---
contract: ingress
version: 0.1.0-draft
fulfilled_by: platform/core/ingress/ + platform/core/cert-manager/
---

# ingress

## Abstract

An app exposes an HTTP route when it declares an `Ingress` (or a Traefik
`IngressRoute`) with a `scope` of `public` or `tailnet`. The edge stack of the
cluster — see `platform/core/edge/` — decides how the traffic enters:

- `public` → the cluster's `edge.public` provider (Cloudflare Tunnel, ELB or
  another), with DNS through `edge.public.dns` and TLS through
  `edge.public.tls`.
- `tailnet` → ingress on Tailscale only, at a `*.ts.net` hostname with a
  certificate that Tailscale issues.

An app does not know the provider-level choices. A change of a cluster from
Cloudflare Tunnel to AWS ELB needs no change to any app.

## Interface (TBD)

### Declaration
The chart archetype emits this automatically from `values.ingress`. The rendered
form:

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

Use the Traefik IngressRoute CRD instead for advanced routing.

### Domain allocation (recommended)

Use a subdomain per project with a prefix per app. That prevents a name collision
between projects:

- `<app>.<project>.<cluster-domain>` — for example
  `api.codectl.brain.mateosegura.com` and
  `dashboard.codectl.brain.mateosegura.com`.
- `<app>.<project>.<cluster-domain>` through wildcard DNS per project
  (`*.codectl.brain.mateosegura.com`). cert-manager issues a certificate per
  host.
- These platform hostnames are reserved: `grafana.<cluster-domain>`,
  `prometheus.<cluster-domain>`, and similar names.

An app may override `values.ingress.host` with any host that it owns, for example
`app.mateosegura.com` for a public product.

## Guarantees (TBD)

- A TLS certificate renews automatically, through cert-manager, 30 days before it
  expires.
- A wildcard DNS record per project points to the ingress LB of the cluster. A
  record per app is unnecessary while the app stays under
  `*.<project>.<cluster-domain>`.
- Routes are isolated between projects. An ingress in `codectl-prod` cannot serve
  a host assigned to `fintel-prod`, because admission validates the ownership of
  the host.

## Caveats (TBD)

- A large payload or a slow client is subject to the platform timeouts. The
  default is 60s, and you can override it per IngressRoute.
- WebSockets and gRPC work, but they need explicit annotations.
- The DNS delegation for the subdomains of a project must be set up once, at
  cluster bring-up. A new project needs an update to the DNS record.

## Example (TBD)

## Exposure classes (authoritative)

Every hostname we serve is declared in **`contracts/exposure.yaml`** with exactly
one class. `bash ctl.sh verify-exposure` resolves each host and fails when
reality differs from the declaration. It runs in CI. This document describes; the
check asserts.

| Class | Path in | TLS | Gate |
| --- | --- | --- | --- |
| `public-access` | Cloudflare tunnel → nginx :80 | cert on :443, `ssl-redirect: "false"` | Cloudflare Access + Google SSO |
| `public-open` | Cloudflare tunnel | same | none — needs a written justification |
| `tailnet` | MetalLB VIP `10.168.0.240` | cert-manager, normal redirect | the tailnet itself |
| `direct-auth` | prod cluster public IP | cert-manager | oauth2-proxy |

**Why `ssl-redirect: "false"` on a host behind the tunnel:** cloudflared connects
to nginx on **:80**. A normal HTTP-to-HTTPS redirect there loops against
cloudflared for ever. A value of false lets :80 and :443 serve at the same time,
so a host can carry a real certificate and the tunnel keeps working.

### How to choose a class

1. Does it need to be reachable without the tailnet? **No** → `tailnet`. Stop.
   An admin surface (Argo CD, Grafana, MinIO) is always `tailnet`.
2. Yes, and everyone who needs it has a Google identity → `public-access`.
3. Yes, and the intended reader has no account → `public-open`. Write the reason
   into `exposure.yaml`.
4. It must survive a Cloudflare outage → `direct-auth`. **Today this class is
   reserved for the vault cluster.** See the note about the exception in
   `exposure.yaml`.

A hostname that you add without a declaration fails the exposure check.
