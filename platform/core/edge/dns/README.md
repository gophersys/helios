# edge/dns

How app hostnames resolve. A cluster declares one provider per scope
(`public` / `tailnet`). Apps don't interact with DNS directly — they
declare `ingress.host` and the DNS provider (usually via external-dns)
reconciles a record for them.

| Provider               | Status | Scope    | Cost          |
|------------------------|--------|----------|---------------|
| `cloudflare/`          | STUB   | public   | Free          |
| `route53/`             | STUB   | public   | $0.50/zone/mo |
| `tailscale-magicdns/`  | STUB   | tailnet  | Free          |
| `external-dns/`        | STUB   | public   | Free operator |

## How records get created

Default mechanism: `external-dns` operator watches `Ingress` objects +
cluster-level annotations, and reconciles records via the provider's API.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: codectl-api
  namespace: codectl-prod
  annotations:
    external-dns.alpha.kubernetes.io/hostname: api.codectl.brain.mateosegura.com
```

For CF Tunnel clusters, the CF tunnel operator manages routes directly
(bypassing external-dns) — faster because tunnel routes are CF-native.

## Zone ownership

Zones declared in cluster `identity.yaml:edge.public.dns.zones[]`.
Delegation must be set up out-of-band (e.g., NS records pointing to CF's
NS for the zone). The platform assumes zones are delegated; it does NOT
create the zone itself.

Apps rendering an Ingress with a hostname outside the cluster's declared
zones → admission warns (typo protection).
