# platform/database-postgresql

Shared Postgres service with one logical database per tenant app. Default
distribution: CloudNativePG operator (cnpg) because it handles HA, backups,
and point-in-time recovery without per-cluster bespoke Terraform.

Applications do NOT provision their own Postgres — they declare a
`Database` CR (cnpg) referencing this cluster-shared control plane.

Status: stub.

TODO:
- Pin cnpg chart version.
- Decide backup target (S3 for AWS, OCI Object Storage for Oracle,
  blob storage for Azure — one backup provider per cluster, wired via
  values).
- Add a `Database` manifest template in `charts/` for applications to copy.
- Document connection-string emission: ExternalSecret from ESO pointing
  at the cnpg-generated role secret.
