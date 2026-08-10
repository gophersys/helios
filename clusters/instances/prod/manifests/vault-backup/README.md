# vault-backup — a nightly encrypted Vaultwarden backup

This closes debt-register **D14**. It was verified end to end on 2026-08-09: the
Job produced a backup, we downloaded it, decrypted it with the offline private
key, and restored it into a scratch database that matched the live database
exactly (`live_ciphers=96 users=1 folders=5 attachments=12`, no errors).

## Why it is built this way

**The cluster can encrypt, but it can never decrypt.** The encryption uses a
public key (`openssl smime`, RSA-4096 and AES-256). Only `public.pem` exists in
the cluster. An attacker who takes the whole cluster gets ciphertext only.

**There are no OCI credentials in the cluster.** The upload uses a
pre-authenticated request scoped to `AnyObjectWrite`. It can create an object,
and it cannot read, list or delete an object. A leaked PAR cannot take a single
existing backup out. That is also why the retention is a lifecycle policy on the
bucket, and not a deletion of files by the Job.

**Both halves, or nothing.** The `vaultwarden` database holds the items, and
`/data/rsa_key.pem` is the JWT signing key. A restore of the database alone
leaves every session token invalid, so the Job fails with a clear error instead
of a shipment of half the data.

## What runs

| | |
| --- | --- |
| Schedule | `0 3 * * *` (03:00 UTC), `concurrencyPolicy: Forbid` |
| Node | pinned to `agent-00`, where `/mnt/data` (the block volume) is attached |
| Destination | OCI Object Storage, bucket `eden-backups`, prefix `vault/` |
| Retention | a 30-day lifecycle policy on the bucket |
| Size | about 200 KB per run, encrypted |

The Job reads `/data` through `hostPath: /mnt/data/pv`, read-only, instead of a
mount of the PVC. The PVC is RWO and the vaultwarden pod holds it, so no other
pod can mount it at the same time. `apps/music/config-backup` uses the same
approach.

`pg_dump` connects with the `DATABASE_URL` from `vaultwarden-credentials`, which
is the same credential that vaultwarden uses. The password of the `postgres`
superuser in `postgres-shared-postgres-credentials` does **not** authenticate
over TCP. The `vaultwarden` role owns the database, so this choice is both
correct and the least privilege.

## Cluster prerequisites (not in git, because they carry secrets)

```sh
# public key — the cluster's half of the keypair
kubectl -n shared-services create configmap vault-backup-pubkey --from-file=public.pem=public.pem

# the write-only upload URL
kubectl -n shared-services create secret generic vault-backup-target --from-file=par-url=par.url
```

Create the PAR again when it expires (**2027-08-10**):

```sh
oci os preauth-request create --bucket-name eden-backups --name vault-backup-cronjob \
  --access-type AnyObjectWrite --time-expires <RFC3339>
```

## Where the private key lives

There are 2 copies, deliberately in different failure domains:

1. **Vaultwarden** — `shared/backup/vault-backup-private-key`. This is the
   convenient copy. It is of no use when the vault is the system that is down.
2. **Offline**, beside the encrypted recovery bundle (Desktop, Drive or USB).
   This is the copy that matters in a real disaster.

**Never** commit the key to this repo. Copy 2 must never be the only one inside
the vault that it exists to rescue.

## Restore

```sh
oci os object list -bn eden-backups --prefix vault/          # newest last
oci os object get -bn eden-backups --name vault/<obj>.enc --file b.enc
openssl smime -decrypt -binary -in b.enc -inform DER -inkey private.pem -out b.tar.gz
tar xzf b.tar.gz          # -> db.pgdump + data.tar.gz
```

Then follow `docs/cloud-cluster.md`, section Backups. If there is no cluster,
follow `RESTORE.md` in the offline bundle.

**Verify with a restore, not with a read.** Restore `db.pgdump` into a scratch
database and compare the counts. Note that `select count(*) from ciphers` gives a
number that is too high, because Vaultwarden soft-deletes. Compare
`count(*) filter (where deleted_at is null)` instead.

## It is not GitOps-reconciled

Argo does **not** drive the prod cluster from this repo.
`platform/services/gitops/` reconciles the homelab only. This manifest is under
version control, but you apply it deliberately:

```sh
KUBECONFIG=~/.kube/cloud.yaml kubectl apply -f cronjob.yaml
KUBECONFIG=~/.kube/cloud.yaml kubectl -n shared-services create job vault-backup-manual --from=cronjob/vault-backup
```

## Known gaps

- **It is still on a single cloud.** The backups sit in OCI Object Storage, which
  is a different service and a different durability domain from the block volume.
  They therefore survive the loss of an instance and the loss of a disk. They do
  **not** survive the loss of the Oracle account. The remaining work is a pull leg
  outside Oracle: the homelab or the workstation fetches from this bucket on a
  schedule.
- **There is no alerting.** A CronJob that fails does not look different from one
  that works. Nothing notices yet if the backups stop.
