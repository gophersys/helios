# platform/services

Opt-in, version-pinned shared services. Each cluster declares in its
`identity.yaml` which services it consumes; cluster-specific overrides live
under `clusters/instances/<c>/overlays/services/<path>/values.yaml`.

| Service              | Provides                                   |
|----------------------|--------------------------------------------|
| `observability/`     | Grafana + Prometheus + Loki + Tempo        |
| `databases/`         | PostgreSQL (cnpg), Redis                   |
| `messaging/`         | NATS JetStream                             |
| `registry/`          | Internal OCI registry (optional)           |
| `admin-dashboard/`   | Single pane of glass for the fleet         |
| `identity-sso/`      | Dex/Keycloak SSO (future)                  |
| `backup/`            | Velero                                     |
| `cost/`              | OpenCost                                   |

## Contract linkage

Apps never consume services directly — they go through `contracts/`:
- `contracts/observability.md` → fulfilled by `services/observability/`
- `contracts/secrets.md` → fulfilled by `core/secrets-operator/`
- `contracts/databases.md` → fulfilled by `services/databases/*`
- `contracts/ingress.md` → fulfilled by `core/ingress/` + `core/cert-manager/`
- `contracts/identity.md` → fulfilled by `services/identity-sso/`
- `contracts/messaging.md` → fulfilled by `services/messaging/*`

Swapping implementations (e.g. Postgres → Neon, NATS → Redis Streams) is
transparent to apps as long as the contract is preserved.

## Status

Every service is a stub.
