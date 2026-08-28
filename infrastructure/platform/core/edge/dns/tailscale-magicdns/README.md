# edge/dns/tailscale-magicdns

Tailscale MagicDNS for tailnet-scope hostnames. Every node on the
tailnet resolves `<device>.<tailnet>.ts.net` without any DNS config.

## How it works

Tailscale daemons on each node intercept DNS queries for `*.ts.net` and
answer them from the tailnet control plane. No in-cluster operator
needed.

For **cluster services** (not individual nodes), the Tailscale
Kubernetes operator (`tailscale/tailscale-operator`) creates virtual
tailnet devices representing Services, so you can `curl
<service-name>.<tailnet>.ts.net` from any tailnet device and reach the
Service.

## Usage

Apps with `ingress.scope: tailnet` get a MagicDNS hostname automatically:

```
<project>-<app>.<tailnet>.ts.net
# e.g., codectl-admin-ui.mateosegura.ts.net
```

If `ingress.host` is explicitly set, that value overrides (must still be
under the tailnet's ts.net domain).

## Status

STUB — MagicDNS itself is already working (it's Tailscale native); only
the operator install + Service-exposure wiring is missing.
