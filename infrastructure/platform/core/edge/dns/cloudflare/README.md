# edge/dns/cloudflare

Cloudflare DNS as the authoritative nameserver for public zones. Free,
API-rich, pairs naturally with `cloudflare-tunnel`.

## Setup

1. Zones declared in cluster identity (`edge.public.dns.zones[]`).
2. NS records at the registrar delegate the zone(s) to CF.
3. CF API token (scoped to Zone:DNS:Edit) stored in Bitwarden as
   `platform-cloudflare-dns-token`, materialized via ESO as Secret
   `platform-cloudflare-dns-token` in the `platform-dns` namespace.
4. `external-dns` operator reads the token and reconciles records.

If the cluster also uses `cloudflare-tunnel`, a single CF API token with
Zone:DNS:Edit + Zone:Cloudflare Tunnel:Edit scopes covers both. The
tunnel operator manages tunnel routes natively; external-dns manages
any A/AAAA records outside tunnels (rare).

## Record types emitted

- `CNAME <host> -> <tunnel-id>.cfargotunnel.com` for tunnel-fronted services.
- `A <host> -> <ELB IP>` when paired with `cloud-loadbalancer`.
- `TXT <host>` ownership records for external-dns state.

## Status

STUB.
