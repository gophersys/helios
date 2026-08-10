# minio

The in-cluster **S3 backup target**. It has 2 consumers:

- **Longhorn** — `BackupTarget/default` points at
  `s3://longhorn-backups@us-east-1/`. It holds the volume backups, which today
  are the observability stack.
- **music-studio** — a restic repository in the bucket `music-backups`. Mateo's
  Mac pushes to it over the tailnet, through `s3.mateosegura.com`. See
  `30-ingress.yaml`. The client side lives in
  github.com/MateoSegura/music-studio.

## Why it is here, and not on Longhorn
The storage is `hostPath /mnt/media/minio` on the NVMe of **k3s-w-1**. It is
deliberately **not** a Longhorn volume, because a backup target must not depend
on the system that it protects. `strategy: Recreate` and a pin to the node keep
the single replica bound to that disk.

## Access and isolation
- The Service is `minio.minio.svc:9000` for the S3 API, and `:9001` for the
  console.
- From outside the cluster: `https://s3.mateosegura.com`. It is a tailnet-private
  ingress, with an A record that is not proxied and points to 10.168.0.240, and a
  Let's Encrypt DNS-01 certificate. It serves the S3 API only.
- The NetworkPolicy (`25-networkpolicy.yaml`) denies ingress by default. Only
  `longhorn-system` and `ingress-nginx` may reach `:9000`, plus the admin pods in
  the same namespace. You reach the console only with
  `kubectl -n minio port-forward svc/minio 9001`.
- The container runs as root, because it writes to the hostPath. It drops ALL
  capabilities and applies the seccomp profile RuntimeDefault. A non-root user
  and a read-only root filesystem are deferred, because they need a chown first.

## Secrets — imperative; see docs/runtime-secrets.md
- `minio-creds` (namespace `minio`) — `MINIO_ROOT_USER` and
  `MINIO_ROOT_PASSWORD`.
- `longhorn-minio-backup` (namespace `longhorn-system`) — the S3 credentials that
  Longhorn uses to reach MinIO: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and
  `AWS_ENDPOINTS`.

Both come from the vault item `shared/minio/longhorn-backups`.

The bucket `music-backups` has its own MinIO user with a narrow scope:
`music-studio`, with read and write on that bucket only. It needs no k8s secret,
because the credentials live only in the Keychain of the Mac that consumes them.
They are in the vault at `project/music-studio/minio/access-key` and
`project/music-studio/minio/secret-key`.

## Bucket bootstrap — one time, on a new cluster
The bucket `longhorn-backups` must exist before Longhorn can make a backup. It
already exists on this cluster. After a rebuild, create it idempotently with a
temporary `mc` pod. This stays a documented command instead of an Argo Job, so
that a failed image pull cannot block the sync of the NetworkPolicy and the
Deployment:
```sh
kubectl -n minio run mc --rm -it --restart=Never --image=minio/mc:latest --env=AK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d)" --env=SK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)" -- sh -c 'mc alias set local http://minio:9000 "$AK" "$SK" && mc mb --ignore-existing local/longhorn-backups'
```
Then point the Longhorn `BackupTarget` at the bucket again. See
`docs/runbooks/longhorn-upgrade.md` → "Backup target".
