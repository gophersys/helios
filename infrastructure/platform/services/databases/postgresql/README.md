# platform/services/databases/postgresql

Shared Postgres control plane — one logical database per tenant app.

## Default implementation

**CloudNativePG (cnpg)** operator (Helm chart: `cloudnative-pg/cloudnative-pg`).

Apps declare a `Database` CR (cnpg). The operator:
- Creates the logical DB + role.
- Generates connection credentials as a Kubernetes Secret.
- Manages HA (primary + replicas), backups, PITR.

## Fulfills
- `contracts/databases.md` (PostgreSQL variant).

## Dependencies
- `platform/core/storage/` — PV for data + WAL.
- `platform/core/secrets-operator/` — credentials out to apps via ExternalSecret.
- `platform/services/backup/` — Velero WAL-G hook for off-cluster PITR.

## Status

STUB.

## TODO (when populating)
- Pin cnpg chart version.
- Decide backup target (S3 for AWS, OCI Object Storage for Oracle, Azure
  Blob for Azure — one per cluster).
- Publish a `Database` manifest template in `charts/stateful-app/` for apps.
- Document the emitted Secret shape in `contracts/databases.md`.
