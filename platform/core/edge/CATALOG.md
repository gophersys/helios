# edge — provider catalog

Support matrix of edge providers + known-good combinations.

## Tunnel providers (how public traffic enters the cluster)

| Provider             | Cost                     | Pros                                                 | Cons                                                |
|----------------------|--------------------------|------------------------------------------------------|-----------------------------------------------------|
| `cloudflare-tunnel`  | Free (unlimited tunnels) | No public IP needed; CF WAF + DDoS free; works behind NAT | CF vendor lock-in for the tunnel; ingress count cap |
| `tailscale-funnel`   | Free (ts.net hosts only) | Trivially easy for ts.net-hostname services          | Only `*.ts.net` hostnames; bandwidth capped         |
| `cloud-loadbalancer` | $16–$30/mo per LB        | Managed, fast, familiar, integrates with cloud WAF   | Costs scale with LBs; cloud-specific                |
| `metallb` (future)   | Free (bare-metal)        | Works on homelab / on-prem                           | Layer 2 / BGP complexity                            |

**Default on `prod`:** `cloudflare-tunnel` (free, no public IP footprint).

## DNS providers (how app hostnames resolve)

| Provider             | Cost                 | Works with tunnel provider                     | API complexity |
|----------------------|----------------------|------------------------------------------------|----------------|
| `cloudflare`         | Free                 | Any (especially CF Tunnel — same account)      | Low            |
| `route53`            | $0.50/mo/zone        | Any (especially cloud-loadbalancer on AWS)     | Medium         |
| `tailscale-magicdns` | Free (ts.net only)   | `tailscale-funnel` / `tailscale` tunnel        | Zero           |
| `external-dns`       | Free operator        | Any — supports all providers above via plugins | Medium         |

**Default on `prod`:** `cloudflare` for public zones,
`tailscale-magicdns` for internal `*.ts.net` hosts.

## TLS providers (how certs are minted + terminated)

| Provider              | Where TLS terminates            | Compatible tunnel     | Renewal            |
|-----------------------|----------------------------------|-----------------------|--------------------|
| `cloudflare-origin`   | Cluster (tunnel-fronted) + CF edge | `cloudflare-tunnel`   | 15-year cert, no renewal |
| `letsencrypt-dns01`   | Cluster                         | Any (works w/o public IP) | 90-day cert, cert-manager auto-renew |
| `letsencrypt-http01`  | Cluster                         | Any with public IP    | 90-day, auto-renew |
| `tailscale-cert`      | Cluster (tailnet)               | `tailscale` /  `tailscale-funnel` | TS-managed |
| `acm`                 | AWS ELB (terminated there)      | `cloud-loadbalancer` on AWS | AWS-managed |

**Default on `prod`:**
- Public: `cloudflare-origin` (paired with CF Tunnel — zero renewal ops).
- Tailnet: `tailscale-cert` (auto-rotated by Tailscale for `*.ts.net`).

## Known-good combinations

### Free-tier stack (today's `prod`)
```yaml
edge:
  public:
    tunnel: cloudflare-tunnel
    dns: cloudflare
    tls: cloudflare-origin
  tailnet:
    tunnel: tailscale
    dns: tailscale-magicdns
    tls: tailscale-cert
```
Total edge cost: **$0/mo**.

### Cloud-managed stack (future, when traffic justifies)
```yaml
edge:
  public:
    tunnel: cloud-loadbalancer      # AWS ELB
    dns: route53
    tls: acm
  tailnet:
    tunnel: tailscale
    dns: tailscale-magicdns
    tls: tailscale-cert
```
Edge cost: ~$16/mo/ELB + $0.50/zone/mo + cert pricing.

### Hybrid (CF edge, internal LE)
```yaml
edge:
  public:
    tunnel: cloudflare-tunnel
    dns: cloudflare
    tls: letsencrypt-dns01          # via CF DNS API — works inside tunnel too
  tailnet:
    tunnel: tailscale
    dns: tailscale-magicdns
    tls: tailscale-cert
```
Use when you want Let's Encrypt certs served from the cluster (not CF's
origin cert) — e.g., for strict end-to-end cert-chain control.

## Forbidden combinations

| Combo                                                    | Why                                                    |
|----------------------------------------------------------|--------------------------------------------------------|
| `cloudflare-tunnel` + `acm`                              | ACM terminates at ELB, not at cluster; no tunnel path  |
| `cloud-loadbalancer` + `cloudflare-origin`               | CF Origin cert requires CF-fronted traffic             |
| `tailscale-funnel` + `cloudflare` DNS for `*.ts.net`     | `*.ts.net` is Tailscale's zone; CF can't answer for it |

CI validates cluster `identity.yaml:edge` combinations against this
matrix at validate time.

## Migration paths

### Free → Cloud-managed
1. Stand up ELB + Route53 + ACM via `providers/aws/modules/*` (Terraform).
2. Update cluster `identity.yaml:edge.public` to the managed stack.
3. Apply `platform/core/edge/*` — new operators install, old tunnel
   pods drain out.
4. Update CF DNS records to point to ELB (or disable CF Tunnel). TTL
   low (300s) during cutover.
5. Decommission CF Tunnel route.

Apps don't redeploy. `Ingress` resources are unchanged; only the cluster
edge is different.

### Add a new project's domain (within same cluster)
1. Cloudflare → add the domain as a Zone.
2. Add the zone to `cluster.edge.public.dns.zones[]` in identity.yaml.
3. Apply `platform/core/edge/dns/cloudflare/`.
4. external-dns operator starts managing the new zone; Ingress objects
   in the project namespace automatically get DNS records.

## Status

Skeleton. This catalog is authoritative — combinations not listed here
are rejected by the edge validator.
