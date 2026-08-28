# minio

The in-cluster **S3 backup target**. It has **1** consumer:

- **music-studio** — a restic repository in the bucket `music-backups`. Mateo's
  Mac pushes to it over the tailnet, through `s3.mateosegura.com`. See
  `30-ingress.yaml`. The client side lives in
  github.com/MateoSegura/music-studio.

**Longhorn was the second consumer until 2026-08-19**, when it was removed
(`platform/core/storage/README.md`). Its `BackupTarget/default` pointed at
`s3://longhorn-backups@us-east-1/`. The bucket and its objects are still on the
NVMe, orphaned. Deleting them is a deliberate step; nothing here does it.

## Why it is a hostPath, not a PVC
The storage is `hostPath /mnt/media/minio` on the NVMe of **k3s-w-1**. A backup
target must not depend on the system that it protects, so it never sat on the
replicated provisioner while one existed. `strategy: Recreate` and a pin to the
node keep the single replica bound to that disk.

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
  **The `allow-longhorn-backups` rule is dead** since the Longhorn removal on
  2026-08-19: its `namespaceSelector` matches a namespace that no longer exists,
  so it admits nothing. It is left in place on purpose — narrowing a live
  NetworkPolicy belongs with the live uninstall, not with a documentation
  change. Drop it in the follow-up that reclaims the `longhorn-backups` bucket.
- The container runs as root, because it writes to the hostPath. It drops ALL
  capabilities and applies the seccomp profile RuntimeDefault. A non-root user
  and a read-only root filesystem are deferred, because they need a chown first.

## Secrets — imperative; see docs/runtime-secrets.md
- `minio-creds` (namespace `minio`) — `MINIO_ROOT_USER` and
  `MINIO_ROOT_PASSWORD`. It comes from the vault item
  `shared/minio/longhorn-backups`. That item name is now historical: it is the
  MinIO ROOT credential and it outlived the consumer it was named for. Do not
  rename it without changing every reference here and in `docs/runtime-secrets.md`.

`longhorn-minio-backup` (namespace `longhorn-system`) was the second secret. It
went with the Longhorn removal on 2026-08-19.

The bucket `music-backups` has its own MinIO user with a narrow scope:
`music-studio`, with read and write on that bucket only. It needs no k8s secret,
because the credentials live only in the Keychain of the Mac that consumes them.
They are in the vault at `project/music-studio/minio/access-key` and
`project/music-studio/minio/secret-key`.

## Bucket bootstrap — one time, on a new cluster
`music-backups` must exist before restic can push to it. It already exists on
this cluster. After a rebuild, create it idempotently with a temporary `mc` pod.
This stays a documented command instead of an Argo Job, so that a failed image
pull cannot block the sync of the NetworkPolicy and the Deployment:
```sh
kubectl -n minio run mc --rm -it --restart=Never --image=minio/mc:latest --env=AK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d)" --env=SK="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)" -- sh -c 'mc alias set local http://minio:9000 "$AK" "$SK" && mc mb --ignore-existing local/music-backups'
```
Then recreate the scoped `music-studio` user and the `music-backups-rw` policy —
see `docs/runtime-secrets.md` → "MinIO IAM". `longhorn-backups` is NOT recreated:
the component that used it was removed on 2026-08-19.
