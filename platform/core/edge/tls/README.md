# edge/tls

How TLS certs are minted. Every cluster installs `cert-manager/` (the
operator); the cluster's `edge.*.tls` choice selects which Issuer(s)
are configured.

| Provider              | Status  | Works with tunnel provider               | Renewal              |
|-----------------------|---------|------------------------------------------|----------------------|
| `cert-manager/`       | STUB    | (operator — always installed)            | n/a                  |
| `cloudflare-origin/`  | STUB    | `cloudflare-tunnel`                      | 15y (no renewal)     |
| `tailscale-cert/`     | STUB    | `tailscale` / `tailscale-funnel`         | TS-managed           |
| `acm/`                | STUB    | `cloud-loadbalancer` on AWS              | AWS-managed          |

Let's Encrypt issuers (both HTTP-01 and DNS-01) are configured in
`cert-manager/` via `ClusterIssuer` CRs — see `cert-manager/README.md`.

## Default for `prod`

- Public scope: `cloudflare-origin` — pairs with CF Tunnel. Cert is a
  CF-issued Origin Certificate with 15-year validity; effectively
  zero-renewal for the cluster lifetime.
- Tailnet scope: `tailscale-cert` — auto-rotated for `*.ts.net`
  hostnames.

## Why not Let's Encrypt for public on CF-fronted?

You can — set `cluster.edge.public.tls: letsencrypt-dns01`. But when
traffic is CF-fronted, the client-facing TLS is already CF's edge cert
(free, managed by CF). The cluster→CF hop cert is commonly an Origin
Cert for simplicity; LE DNS-01 is an option if you want end-to-end
public-CA chain from cluster.
