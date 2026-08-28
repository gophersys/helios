# edge — provider catalog

The support matrix of the edge providers, and the combinations that are known to
work.

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

**Default on `prod`:** `cloudflare` for the public zones, and
`tailscale-magicdns` for the internal `*.ts.net` hosts.

## TLS providers (how certs are minted + terminated)

| Provider              | Where TLS terminates            | Compatible tunnel     | Renewal            |
|-----------------------|----------------------------------|-----------------------|--------------------|
| `cloudflare-origin`   | Cluster (tunnel-fronted) + CF edge | `cloudflare-tunnel`   | 15-year cert, no renewal |
| `letsencrypt-dns01`   | Cluster                         | Any (works w/o public IP) | 90-day cert, cert-manager auto-renew |
| `letsencrypt-http01`  | Cluster                         | Any with public IP    | 90-day, auto-renew |
| `tailscale-cert`      | Cluster (tailnet)               | `tailscale` /  `tailscale-funnel` | TS-managed |
| `acm`                 | AWS ELB (terminated there)      | `cloud-loadbalancer` on AWS | AWS-managed |

**Default on `prod`:**
- Public: `cloudflare-origin`, used with the Cloudflare Tunnel. There is no
  renewal work.
- Tailnet: `tailscale-cert`. Tailscale rotates it automatically for `*.ts.net`.

## The combinations that are known to work

### The free-tier stack (today's `prod`)
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

### The cloud-managed stack (future, when the traffic justifies the cost)
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
Use this stack when the cluster must serve Let's Encrypt certificates instead of
the Cloudflare origin certificate. An example reason is strict control of the
certificate chain, end to end.

## Forbidden combinations

| Combo                                                    | Why                                                    |
|----------------------------------------------------------|--------------------------------------------------------|
| `cloudflare-tunnel` + `acm`                              | ACM terminates at ELB, not at cluster; no tunnel path  |
| `cloud-loadbalancer` + `cloudflare-origin`               | CF Origin cert requires CF-fronted traffic             |
| `tailscale-funnel` + `cloudflare` DNS for `*.ts.net`     | `*.ts.net` is Tailscale's zone; CF can't answer for it |

At validate time, CI checks the `identity.yaml:edge` combination of a cluster
against this matrix.

## Migration paths

### From free tier to cloud-managed
1. Create the ELB, Route53 and ACM resources with Terraform, through
   `providers/aws/modules/*`.
2. Change the cluster's `identity.yaml:edge.public` to the managed stack.
3. Apply `platform/core/edge/*`. The new operators install, and the old tunnel
   pods stop.
4. Change the Cloudflare DNS records to point at the ELB, or disable the
   Cloudflare Tunnel. Keep the TTL low, 300s, during the cutover.
5. Decommission the Cloudflare Tunnel route.

No app is deployed again. The `Ingress` resources do not change. Only the edge of
the cluster is different.

### Add the domain of a new project, in the same cluster
1. In Cloudflare, add the domain as a Zone.
2. Add the zone to `cluster.edge.public.dns.zones[]` in identity.yaml.
3. Apply `platform/core/edge/dns/cloudflare/`.
4. The external-dns operator starts to manage the new zone. The Ingress objects
   in the namespace of the project get their DNS records automatically.

## Status

Skeleton. This catalog is authoritative. The edge validator rejects a combination
that this catalog does not list.
