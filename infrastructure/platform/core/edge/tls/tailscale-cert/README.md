# edge/tls/tailscale-cert

Tailscale-issued TLS certs for `*.ts.net` hostnames. Auto-rotated by
Tailscale, served by the Tailscale Kubernetes operator onto the
cluster's tailnet-scope ingress.

## When to use

Every `ingress.scope: tailnet` app with an Ingress host under
`<tailnet>.ts.net` gets a tailscale-issued cert automatically. No
ClusterIssuer configuration in cert-manager needed.

## How it works

The Tailscale Kubernetes operator (already installed by
`edge/tunnel/tailscale-funnel/` or by a baseline install for all
tailnet clusters) intercepts TLS handshakes on tailnet-local IPs and
serves a TS-issued cert backed by Let's Encrypt + TS's own TLS-ALPN-01
handling.

Public-CA trusted — clients on the tailnet see a regular LE-chain
certificate.

## Limitations

- `*.ts.net` hostnames only.
- Requires MagicDNS enabled (default).
- Client must be on the tailnet to reach the cert-bearing service
  (that's the whole point).

## Status

STUB.
