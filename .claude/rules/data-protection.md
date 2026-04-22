---
paths:
  - "deploy/production/helm/**/*"
  - "infrastructure/**/*"
---

# Data Protection & Backup Rules

Concord's data lives in PostgreSQL (application state) and MinIO (firmware artifacts). Both run as in-cluster pods with PersistentVolumeClaims on local-path storage.

## Protection Layers

### 1. PVC Delete Protection

All PVCs have `helm.sh/resource-policy: keep` — Helm will **never** delete them, even on `helm uninstall`. This means:

- `nx stop platform -c staging` → pods removed, PVCs survive, data safe
- `helm uninstall concord -n production` → same, PVCs survive
- Manual `kubectl delete pvc` → **still dangerous** (requires explicit action)

### 2. PV Retain Policy

All PVs are patched to `Retain` reclaim policy. Even if a PVC is somehow deleted, the underlying PV and its data stay on disk. Recovery requires manual PV re-binding.

New PVs created by the `local-path` provisioner default to `Delete` — run this after any new PVC is created:

```bash
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

### 3. Production Stop Safety

`nx stop platform -c production` requires `--confirm-delete` flag. Without it, the command refuses to execute.

### 4. Automated Backups

| Backup | Schedule | Retention | Storage |
|--------|----------|-----------|---------|
| PostgreSQL (staging) | Daily 2 AM UTC | 7 days | MinIO `backups/postgres/staging/` |
| PostgreSQL (production) | Daily 2 AM UTC | 30 days | MinIO `backups/postgres/production/` |
| PostgreSQL (pre-upgrade) | Before every `helm upgrade` | Kept with daily rotation | MinIO `backups/postgres/<env>/` |
| MinIO mirror (staging) | Weekly Sunday 3 AM | Latest mirror | hostPath `/var/lib/concord/backups/minio/` |
| MinIO mirror (production) | Weekly Sunday 3 AM | Latest mirror | hostPath `/var/lib/concord/backups/minio/` |

## Backup Storage Layout

```
MinIO: backups/
├── postgres/
│   ├── staging/
│   │   ├── concord-2026-04-07T02-00-00Z.sql.gz
│   │   ├── pre-upgrade-2026-04-07T15-30-00Z.sql.gz
│   │   └── ...
│   └── production/
│       ├── concord-2026-04-07T02-00-00Z.sql.gz
│       └── ...

hostPath: /var/lib/concord/backups/minio/
├── staging/
│   └── (mirror of all MinIO buckets)
└── production/
    └── (mirror of all MinIO buckets)
```

## Manual Backup

```bash
# Trigger a one-off postgres backup
kubectl create job --from=cronjob/concord-backup-postgres manual-backup -n production

# Check backup status
kubectl logs job/manual-backup -n production

# List all backups in MinIO (from any pod with mc)
mc ls concord/backups/postgres/production/
```

## Restore Procedures

### PostgreSQL Restore

```bash
# 1. Download the backup from MinIO
kubectl exec -n production deploy/concord-postgres -- bash -c \
  'apt-get update && apt-get install -y curl && \
   curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && \
   chmod +x /usr/local/bin/mc && \
   mc alias set concord http://concord-minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD && \
   mc cp concord/backups/postgres/production/<filename>.sql.gz /tmp/restore.sql.gz'

# 2. Restore (drops + recreates all tables)
kubectl exec -n production deploy/concord-postgres -- bash -c \
  'gunzip -c /tmp/restore.sql.gz | psql -U concord -d concord'
```

### PV Recovery (after accidental PVC delete)

If a PVC is deleted but the PV has `Retain` policy:

1. The PV enters `Released` state (data still on disk)
2. Remove the stale claimRef: `kubectl patch pv <pv-name> -p '{"spec":{"claimRef":null}}'`
3. Re-create the PVC with the same name — it will bind to the existing PV

## Configuration

Backup settings in Helm values:

```yaml
backups:
  postgres:
    enabled: true
    schedule: "0 2 * * *"       # Cron schedule
    retain: 30                   # Keep last N backups
    preUpgrade: true             # Auto-backup before helm upgrade
  minio:
    enabled: true
    schedule: "0 3 * * 0"       # Weekly
    hostPath: "/var/lib/concord/backups/minio"
```

## What NOT To Do

- **NEVER** `kubectl delete pvc` in production without a verified backup
- **NEVER** delete a node that hosts a PV without migrating the data first
- **NEVER** disable pre-upgrade backups in production
- **NEVER** reduce retention below 7 days in production
