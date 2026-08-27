# edge/tunnel

How public traffic enters the cluster. A cluster picks exactly ONE tunnel
provider for its `edge.public` scope. Tailscale always serves the tailnet scope
directly. See `../../edge/ingress-controller/`, which binds to the IPs that are
local to the tailnet.

| Provider             | Status  | Free-tier?    | Best for                                      |
|----------------------|---------|---------------|-----------------------------------------------|
| `cloudflare-tunnel/` | STUB    | Yes           | **Default.** Zero public IP needed; CF edge |
| `tailscale-funnel/`  | STUB    | Yes (limited) | Exposing `*.ts.net` services without CF      |
| `cloud-loadbalancer/`| STUB    | No (~$16/mo)  | Cloud-managed apps outgrowing free-tier       |

See `../CATALOG.md` for the compatibility matrix against DNS + TLS.
