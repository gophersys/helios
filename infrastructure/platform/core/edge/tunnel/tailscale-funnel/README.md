# edge/tunnel/tailscale-funnel

Expose a Tailscale-joined service to the **public internet** via
Tailscale Funnel. Free for `*.ts.net` hostnames only. Useful for
prototyping public endpoints without setting up DNS / tunnels on the
cluster side.

## When to use

- A one-off public demo that doesn't need a custom domain.
- A lab cluster without its own public DNS.
- Explicitly-public admin UIs (rare — prefer tailnet scope + SSO).

## When NOT to use

- Production customer traffic — use `cloudflare-tunnel` instead (CF has
  the WAF + DDoS + custom domain story).
- High-bandwidth or low-latency workloads — Funnel is rate-limited.
- Anything that needs a non-`ts.net` hostname.

## How it works

The Tailscale Kubernetes operator (`tailscale/tailscale-operator` Helm
chart) watches Services annotated for Funnel exposure and configures
the cluster's tailnet ingress pod to accept public traffic for the
service's `*.ts.net` hostname.

```yaml
apiVersion: v1
kind: Service
metadata:
  annotations:
    tailscale.com/expose: "true"
    tailscale.com/funnel: "true"
  name: my-demo
spec:
  type: ClusterIP
  ...
```

## Limits

- Ports: 443, 8443, 10000 only (CF Tunnel and ELB have no such limit).
- Hostnames: `<release>.<tailnet>.ts.net` only (no custom domains).
- Bandwidth + requests: Tailscale Funnel free-plan caps (current: 100 GB
  egress / month, suspended after).

## Status

STUB.
