# edge/dns/external-dns

[external-dns](https://github.com/kubernetes-sigs/external-dns) — the
generic DNS operator. Reconciles DNS records from Kubernetes `Ingress`
and `Service` resources.

## When to use

- When the cluster uses a DNS provider that needs record reconciliation
  (i.e., every provider except `tailscale-magicdns`).
- As a **single operator** that handles both `cloudflare` and `route53`
  providers simultaneously (for clusters that span, e.g., CF-fronted
  public + AWS-hosted API subdomain).

## Provider configs

external-dns is installed ONCE per cluster, configured with the
providers declared in `cluster.edge.public.dns`. Multiple provider
stanzas supported.

## Status

STUB. Often bundled with the provider-specific component
(`edge/dns/cloudflare/`, `edge/dns/route53/`) — they share the same
operator install.
