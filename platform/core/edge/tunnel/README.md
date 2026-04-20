# edge/tunnel

How public traffic enters the cluster. A cluster picks exactly ONE tunnel
provider for its `edge.public` scope. Tailnet scope is always served by
Tailscale directly (see `../../edge/ingress-controller/` binding to
tailnet-local IPs).

| Provider             | Status  | Free-tier?    | Best for                                      |
|----------------------|---------|---------------|-----------------------------------------------|
| `cloudflare-tunnel/` | STUB    | Yes           | **Default.** Zero public IP needed; CF edge |
| `tailscale-funnel/`  | STUB    | Yes (limited) | Exposing `*.ts.net` services without CF      |
| `cloud-loadbalancer/`| STUB    | No (~$16/mo)  | Cloud-managed apps outgrowing free-tier       |

See `../CATALOG.md` for the compatibility matrix against DNS + TLS.
