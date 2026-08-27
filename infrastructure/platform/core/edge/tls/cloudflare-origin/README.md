# edge/tls/cloudflare-origin

Cloudflare-issued Origin Certificates for cluster→CF TLS. Valid up to
15 years. Used as the cert served by the cluster's ingress controller
when traffic is CF-fronted (via `cloudflare-tunnel`). The client-facing
cert on CF's edge is CF's own universal SSL — no cluster involvement.

## How it works

1. A single CF Origin CA cert is issued for `*.<zone>` and `<zone>`
   (wildcards per-zone).
2. cert-manager's external-issuer plugin for CF Origin
   (`cloudflare/origin-issuer`) provisions the cert.
3. The cert lands as a Kubernetes Secret; traefik picks it up per
   `Ingress.spec.tls[]`.
4. CF's edge trusts Origin certs intrinsically (private CA) — no
   client-facing impact.

## Trust chain

```
client ──(CF universal SSL, public-CA)──> CF edge
                                          │
                                          └─(CF Origin CA, CF-internal)──> cluster traefik
```

The Origin CA is NOT trusted by public clients — that's intentional.
Origin certs are for the CF↔origin hop only.

## Secrets

- `platform-cloudflare-origin-key` — CF API token with
  `SSL and Certificates:Edit` scope. Stored in Bitwarden.

## Limitations

- Clients cannot verify the origin cert directly (not public CA). Only
  usable when traffic is CF-fronted.
- If you go around CF (e.g., direct-to-cluster testing), the cert is
  rejected — use a `letsencrypt-dns01` ClusterIssuer for a second cert
  on the same hostname if direct hits matter.

## Status

STUB.
