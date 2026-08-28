# edge/dns

How an app hostname resolves. A cluster declares 1 provider for each scope,
`public` and `tailnet`. An app does not interact with DNS directly. It declares
`ingress.host`, and the DNS provider reconciles a record for it, usually through
external-dns.

| Provider               | Status | Scope    | Cost          |
|------------------------|--------|----------|---------------|
| `cloudflare/`          | STUB   | public   | Free          |
| `route53/`             | STUB   | public   | $0.50/zone/mo |
| `tailscale-magicdns/`  | STUB   | tailnet  | Free          |
| `external-dns/`        | STUB   | public   | Free operator |

## How a record is created

The default mechanism: the `external-dns` operator watches the `Ingress` objects
and the cluster-level annotations, and it reconciles the records through the API
of the provider.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: codectl-api
  namespace: codectl-prod
  annotations:
    external-dns.alpha.kubernetes.io/hostname: api.codectl.brain.mateosegura.com
```

On a cluster with a Cloudflare Tunnel, the Cloudflare tunnel operator manages the
routes directly and does not use external-dns. That is faster, because a tunnel
route is native to Cloudflare.

## Zone ownership

The cluster declares its zones in `identity.yaml:edge.public.dns.zones[]`. You
must set up the delegation outside this repo, for example with NS records that
point at the Cloudflare name servers for the zone. The platform assumes that a
zone is delegated. It does NOT create the zone.

If an app renders an Ingress with a hostname outside the declared zones of the
cluster, admission gives a warning. That protects against a typo.
