# edge/tls

How a TLS certificate is issued. Every cluster installs the `cert-manager/`
operator. The `edge.*.tls` choice of the cluster selects which Issuers are
configured.

| Provider              | Status  | Works with tunnel provider               | Renewal              |
|-----------------------|---------|------------------------------------------|----------------------|
| `cert-manager/`       | STUB    | (operator — always installed)            | n/a                  |
| `cloudflare-origin/`  | STUB    | `cloudflare-tunnel`                      | 15y (no renewal)     |
| `tailscale-cert/`     | STUB    | `tailscale` / `tailscale-funnel`         | TS-managed           |
| `acm/`                | STUB    | `cloud-loadbalancer` on AWS              | AWS-managed          |

The Let's Encrypt issuers, both HTTP-01 and DNS-01, are configured in
`cert-manager/` through `ClusterIssuer` CRs. See `cert-manager/README.md`.

## The default for `prod`

- Public scope: `cloudflare-origin`. It works with the Cloudflare Tunnel. The
  certificate is a Cloudflare Origin Certificate with 15 years of validity, so
  the cluster does not renew it during its lifetime.
- Tailnet scope: `tailscale-cert`. Tailscale rotates it automatically for a
  `*.ts.net` hostname.

## Let's Encrypt for a public host behind Cloudflare

You can use Let's Encrypt for such a host: set
`cluster.edge.public.tls: letsencrypt-dns01`. When Cloudflare fronts the traffic,
the TLS that the client sees is already the Cloudflare edge certificate, which is
free and which Cloudflare manages. The certificate for the hop from the cluster
to Cloudflare is usually an Origin Certificate, because that is simpler. Use LE
DNS-01 instead when you want a chain to a public CA, end to end, from the
cluster.
