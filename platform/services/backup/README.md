# platform/services/backup

Off-cluster backups of persistent volumes and cluster resources. Used for
disaster recovery, cluster migrations, and point-in-time restores.

## Default implementation

**Velero** (Helm chart: `vmware-tanzu/velero`) with the appropriate object
storage provider:
- AWS clusters → S3
- OCI clusters → OCI Object Storage (via S3-compat plugin)
- Azure clusters → Azure Blob
- Homelab → remote S3-compat bucket (Backblaze B2, Cloudflare R2)

Schedules:
- Daily full cluster backup (resource manifests + PV snapshots).
- Hourly for databases that opt in (via PV snapshot, complementing cnpg WAL).

## Fulfills
- No direct app contract — platform-level DR concern.

## Dependencies
- `platform/core/storage/` — CSI snapshot support for PV backups.
- `platform/core/secrets-operator/` — object storage credentials from
  Bitwarden.

## Status

STUB. Populate as the first stateful workload hits `prod`.

## Homelab reality today (not this service)

Velero is NOT deployed. What actually runs on homelab:
- **PV backups:** Longhorn → in-cluster MinIO (`apps/minio/`, bucket
  `longhorn-backups`) — covers the observability stack volumes.
- **Off-cluster client backups:** restic from Mateo's Mac → same MinIO
  (bucket `music-backups`, tailnet-private `s3.mateosegura.com`) for the
  music-studio workspace (client: github.com/MateoSegura/music-studio).
When this service is populated (Velero + true off-site B2/R2), the MinIO
buckets above should be included in what gets replicated off-site.
