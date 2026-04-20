# platform/core/edge

The **edge** layer: everything between the public internet (and the
tailnet) and the cluster's pods. Pluggable by design — a cluster picks a
stack in its `identity.yaml:edge` block, and apps are unaware of the
choice.

## Why "edge"

Ingress, TLS, and DNS used to be three separate components (three install
steps, three places to configure per cluster). In practice they're one
decision: "how does traffic get to my apps?" Bundling them into an edge
layer makes that decision explicit and swappable.

## What's in here

```
edge/
├── tunnel/                  # how traffic enters the cluster
│   ├── cloudflare-tunnel/       (default / free — cloudflared DaemonSet)
│   ├── tailscale-funnel/        (free for ts.net hosts; limited)
│   └── cloud-loadbalancer/      (AWS ELB, OCI LB, Azure LB — expensive, managed)
├── ingress-controller/      # in-cluster L7 routing (always installed)
│   (currently: traefik; alt: nginx)
├── dns/                     # how app hostnames resolve
│   ├── cloudflare/              (default / free — Cloudflare DNS API)
│   ├── route53/                 (AWS)
│   ├── tailscale-magicdns/      (internal-only, ts.net hostnames)
│   └── external-dns/            (generic ExternalDNS operator — can target any)
└── tls/                     # how certs are minted
    ├── cert-manager/            (the operator; always installed)
    ├── cloudflare-origin/       (CF-issued origin cert — tunnel-fronted traffic)
    ├── tailscale-cert/          (TS-issued cert for ts.net hostnames)
    └── acm/                     (AWS Certificate Manager — terminated at ELB)
```

## Traffic scopes

Apps declare `ingress.scope` in their chart values:

| Scope     | Who can reach it                  | Typical use                              |
|-----------|-----------------------------------|------------------------------------------|
| `public`  | Anyone on the internet (with TLS) | Customer-facing APIs, marketing sites    |
| `tailnet` | Anyone on the Tailscale mesh      | Admin dashboards, internal tooling, ops  |

Each cluster declares its edge stack for **each** scope. The free-tier
default for `prod`:

```yaml
edge:
  public:
    tunnel:  cloudflare-tunnel           # no public IP on the cluster; CF is the edge
    dns:     cloudflare                   # CF DNS authoritative for public zones
    tls:     cloudflare-origin            # cluster→CF TLS via origin cert; CF→client TLS via CF edge
  tailnet:
    tunnel:  tailscale                    # nodes are on the mesh; Service LB = tailnet IP
    dns:     tailscale-magicdns           # <host>.<tailnet>.ts.net
    tls:     tailscale-cert               # auto-issued, auto-rotated for ts.net hostnames
```

## The swap path (free-tier → managed)

As the cluster grows out of free-tier:

```yaml
edge:
  public:
    tunnel:  cloud-loadbalancer           # AWS ELB
    dns:     route53
    tls:     acm                          # terminated at ELB
```

**Nothing in the apps changes.** The chart archetype emits the same
`Ingress` + `Service` resources. The cluster-level edge configuration
decides how traffic actually flows.

## Apps are unaware

Every chart archetype emits an `Ingress` object (when `ingress.enabled`).
The cluster's edge stack decides:

- Who accepts the request (CF Tunnel pod? ELB? kube-proxy NodePort?).
- How DNS resolves the hostname (CF DNS? Route53? tailscale MagicDNS?).
- Where the TLS cert came from (CF Origin? Let's Encrypt? ACM? TS?).

App-level values (`ingress.host`, `ingress.tls.clusterIssuer`,
`ingress.rateLimit`) are hints the archetype maps onto the cluster's
edge stack. When incompatible (e.g., an app asks for `clusterIssuer:
letsencrypt-prod` on a cluster whose `tls: acm`), admission warns +
falls back to the cluster default.

## Install order (fixed)

Runs AFTER `cni` + `storage` + `secrets-operator` (because edge needs
secrets for API tokens), BEFORE any `platform/services/*`:

1. `edge/tls/cert-manager` — operator (even if using non-LE issuers,
   cert-manager orchestrates)
2. `edge/ingress-controller` — traefik (for in-cluster L7 routing)
3. `edge/tls/<issuer>` — ClusterIssuers for the declared TLS provider
4. `edge/dns/<provider>` — DNS operator (external-dns or provider-native)
5. `edge/tunnel/<provider>` — tunnel/LB that accepts public traffic

After edge is up, the cluster can serve `Ingress` objects end-to-end
from declaration to publicly-resolvable TLS-terminated URL.

## Status

Skeleton. README + sub-component READMEs committed as the contract.
Every actual install (tunnel pods, DNS operator, cert-manager manifests)
lands as `prod` bootstraps through this tree.

See `CATALOG.md` for the provider support matrix + known-good combos.
