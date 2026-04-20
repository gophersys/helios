# edge/tunnel/cloudflare-tunnel

**Default public-traffic entry for free-tier clusters.** No public IP on
the cluster; Cloudflare's edge accepts traffic, a `cloudflared` DaemonSet
pod keeps outbound persistent connections to CF, and public requests are
tunneled through to the in-cluster ingress controller (`traefik`).

## Why this is the default

- **Zero public IP.** OCI + AWS free-tier instances often don't have
  stable public IPs or adequate bandwidth — tunnels sidestep that.
- **Free.** Unlimited tunnels, unlimited bandwidth through CF's edge.
- **DDoS + WAF.** CF's edge soaks attack traffic before it reaches the
  cluster. Zero config.
- **Works behind NAT.** Homelab-friendly for future lab clusters.

## How it works

1. A `cloudflared` DaemonSet runs on every cluster node (or as a
   Deployment — DaemonSet chosen for outbound-connection redundancy).
2. Each pod opens 4 outbound TLS connections to CF's edge (no inbound
   firewall holes needed).
3. CF routes public requests matching the tunnel's configured hostnames
   through the persistent connection to a cluster-local Service (the
   cluster's `traefik` ingress controller, at `platform-ingress` namespace).
4. Traefik routes to the app's Service based on `Ingress` rules.

## Configuration

One `cloudflared` tunnel per cluster. The tunnel has a Route table
managed by the `cloudflare-operator` (Helm chart: `strrl.dev/cloudflare-tunnel-ingress-controller`) which watches `Ingress` objects and
creates CF tunnel routes automatically.

Secrets (from Bitwarden via ESO):
- `cloudflare-tunnel-token` — the tunnel's credentials (issued by CF).
- `cloudflare-api-token` — for the operator to create tunnel routes
  via CF API (scoped to zone + tunnel edit permissions).

## Compatibility

| DNS provider           | OK?  | Notes                                    |
|------------------------|------|------------------------------------------|
| `cloudflare`           | Yes  | Natural pairing (same account)           |
| `route53`              | No   | CF Tunnel routes require CF DNS          |
| `tailscale-magicdns`   | N/A  | MagicDNS is internal only                |
| `external-dns`         | Yes  | Via CF provider in external-dns          |

| TLS provider           | OK?  | Notes                                    |
|------------------------|------|------------------------------------------|
| `cloudflare-origin`    | Yes  | Natural pairing                          |
| `letsencrypt-dns01`    | Yes  | via CF DNS API; cluster-issued certs     |
| `letsencrypt-http01`   | No   | HTTP-01 needs port 80 on public IP       |
| `acm`                  | No   | ACM terminates at AWS ELB, not cluster   |

## Limits (as of 2026-04)

- Free plan: 100 public hostnames per tunnel, 1,000 tunnels per account.
- Bandwidth: unlimited on CF free plan; requests are rate-limited by CF
  WAF defaults (configurable).
- Latency: +10–30ms vs direct public ingress, depending on edge PoP
  proximity.

## Status

STUB. Cloudflared install + operator wiring lands when `prod` cluster
bootstraps its public edge.
