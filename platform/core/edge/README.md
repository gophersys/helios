# platform/core/edge

The **edge** layer: everything between the cluster's pods and the public internet
or the tailnet. It is pluggable by design. A cluster picks a stack in the
`identity.yaml:edge` block, and an app does not know which stack it picked.

## Why the name "edge"

Ingress, TLS and DNS used to be 3 separate components: 3 install steps and 3
places to configure per cluster. In practice they are 1 decision: how does
traffic reach my apps? A single edge layer makes that decision explicit and easy
to change.

## What is in here

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

An app declares `ingress.scope` in its chart values:

| Scope     | Who can reach it                  | Typical use                              |
|-----------|-----------------------------------|------------------------------------------|
| `public`  | Anyone on the internet (with TLS) | Customer-facing APIs, marketing sites    |
| `tailnet` | Anyone on the Tailscale mesh      | Admin dashboards, internal tooling, ops  |

Each cluster declares its edge stack for **each** scope. The free-tier default
for `prod`:

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

## How to change from the free tier to a managed stack

When the cluster grows past the free tier:

```yaml
edge:
  public:
    tunnel:  cloud-loadbalancer           # AWS ELB
    dns:     route53
    tls:     acm                          # terminated at ELB
```

**Nothing in the apps changes.** The chart archetype emits the same `Ingress` and
`Service` resources. The edge configuration of the cluster decides how the
traffic flows.

## Apps do not know the edge stack

Every chart archetype emits an `Ingress` object when `ingress.enabled` is true.
The edge stack of the cluster decides:

- who accepts the request: a Cloudflare Tunnel pod, an ELB, or a kube-proxy
  NodePort;
- how DNS resolves the hostname: Cloudflare DNS, Route53, or Tailscale MagicDNS;
- where the TLS certificate comes from: a Cloudflare origin cert, Let's Encrypt,
  ACM, or Tailscale.

The app-level values (`ingress.host`, `ingress.tls.clusterIssuer`,
`ingress.rateLimit`) are hints, and the archetype maps them onto the edge stack
of the cluster. If a value is incompatible — for example an app asks for
`clusterIssuer: letsencrypt-prod` on a cluster whose `tls` is `acm` — admission
gives a warning and falls back to the cluster default.

## Install order (fixed)

The edge layer runs AFTER `cni`, `storage` and `secrets-operator`, because the
edge needs secrets for its API tokens. It runs BEFORE any `platform/services/*`:

1. `edge/tls/cert-manager` — the operator. cert-manager orchestrates issuance
   even when the issuer is not Let's Encrypt.
2. `edge/ingress-controller` — traefik, for L7 routing inside the cluster.
3. `edge/tls/<issuer>` — the ClusterIssuers for the declared TLS provider.
4. `edge/dns/<provider>` — the DNS operator: external-dns or a provider-native
   one.
5. `edge/tunnel/<provider>` — the tunnel or load balancer that accepts public
   traffic.

After the edge is up, the cluster can serve an `Ingress` object end to end, from
the declaration to a publicly resolvable URL with TLS termination.

## Status

Skeleton. This README and the sub-component READMEs are committed as the
contract. Each real install — the tunnel pods, the DNS operator, the cert-manager
manifests — lands as `prod` bootstraps through this tree.

See `CATALOG.md` for the support matrix of the providers and the combinations
that are known to work.
