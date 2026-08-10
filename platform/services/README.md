# platform/services

The opt-in shared services, with a pinned version. Each cluster declares the
services that it consumes in its `identity.yaml`. The overrides for that cluster
live under `clusters/instances/<c>/overlays/services/<path>/values.yaml`.

| Service              | Provides                                   |
|----------------------|--------------------------------------------|
| `observability/`     | Grafana + Prometheus + Loki + Tempo        |
| `networking/`        | Tailscale operator (per-Service tailnet exposure) |
| `databases/`         | PostgreSQL (cnpg), Redis                   |
| `messaging/`         | NATS JetStream                             |
| `registry/`          | Internal OCI registry (optional)           |
| `admin-dashboard/`   | One view of every machine and cluster      |
| `identity-sso/`      | Dex/Keycloak SSO (future)                  |
| `backup/`            | Velero                                     |
| `cost/`              | OpenCost                                   |

## The link to the contracts

An app never consumes a service directly. It goes through `contracts/`:
- `contracts/observability.md` → fulfilled by `services/observability/`
- `contracts/secrets.md` → fulfilled by `core/secrets-operator/`
- `contracts/databases.md` → fulfilled by `services/databases/*`
- `contracts/ingress.md` → fulfilled by `core/ingress/` + `core/cert-manager/`
- `contracts/identity.md` → fulfilled by `services/identity-sso/`
- `contracts/messaging.md` → fulfilled by `services/messaging/*`

A change of implementation, for example from Postgres to Neon, or from NATS to
Redis Streams, is invisible to an app while the contract stays the same.

## Status

Every service is a stub.
