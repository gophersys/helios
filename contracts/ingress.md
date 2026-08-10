---
contract: ingress
version: 0.1.0-draft
fulfilled_by: platform/core/ingress/ + platform/core/cert-manager/
---

# ingress

## Abstract

Apps expose HTTP routes by declaring an `Ingress` (or Traefik `IngressRoute`)
with a `scope` (`public` | `tailnet`). The cluster's edge stack — see
`platform/core/edge/` — decides how traffic actually enters:

- `public` → cluster's `edge.public` provider (Cloudflare Tunnel /
  ELB / etc.), DNS via `edge.public.dns`, TLS via `edge.public.tls`.
- `tailnet` → Tailscale-only ingress at a `*.ts.net` hostname with
  TS-issued cert.

Apps are unaware of provider-level choices; swapping a cluster from
Cloudflare Tunnel to AWS ELB requires no app changes.

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

## Exposure classes (authoritative)

Every hostname we serve is declared in **`contracts/exposure.yaml`** with exactly
one class. `bash ctl.sh verify-exposure` resolves each host and fails when reality
diverges — run in CI. Documentation describes; that check asserts.

| Class | Path in | TLS | Gate |
| --- | --- | --- | --- |
| `public-access` | Cloudflare tunnel → nginx :80 | cert on :443, `ssl-redirect: "false"` | Cloudflare Access + Google SSO |
| `public-open` | Cloudflare tunnel | same | none — needs a written justification |
| `tailnet` | MetalLB VIP `10.168.0.240` | cert-manager, normal redirect | the tailnet itself |
| `direct-auth` | prod cluster public IP | cert-manager | oauth2-proxy |

**Why `ssl-redirect: "false"` on tunnel-backed hosts:** cloudflared connects to
nginx on **:80**. A normal HTTP→HTTPS redirect there loops against cloudflared
forever. Setting it false lets :80 and :443 serve simultaneously, so a host can
carry a real certificate without breaking the tunnel.

### Choosing a class

1. Does it need to be reachable without the tailnet? **No** → `tailnet`. Stop.
   Admin surfaces (Argo CD, Grafana, MinIO) are always `tailnet`.
2. Yes, and everyone who needs it has a Google identity → `public-access`.
3. Yes, and the intended reader has no account → `public-open`, with the reason
   written into `exposure.yaml`.
4. It must survive a Cloudflare outage → `direct-auth`. **Today this is reserved
   for the vault cluster.** See the exception note in `exposure.yaml`.

Adding a hostname without declaring it fails the exposure check.
