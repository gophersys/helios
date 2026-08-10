# vault-backup — nightly encrypted Vaultwarden backup

Closes debt-register **D14**. Verified end-to-end 2026-08-09: the Job produced a
backup, it was downloaded, decrypted with the offline private key, and restored
into a scratch database matching live exactly (`live_ciphers=96 users=1 folders=5
attachments=12`, zero errors).

## Why it is built this way

**The cluster can encrypt but never decrypt.** Encryption is public-key
(`openssl smime`, RSA-4096 + AES-256). Only `public.pem` exists in the cluster.
Compromising the entire cluster yields ciphertext.

**No OCI credentials in the cluster.** Upload uses a pre-authenticated request
scoped to `AnyObjectWrite` — it can create objects, and cannot read, list or
delete them. A leaked PAR cannot exfiltrate a single existing backup, which is
also why retention is a bucket lifecycle policy rather than the Job deleting
files.

**Both halves or nothing.** The `vaultwarden` database holds the items;
`/data/rsa_key.pem` is the JWT signing key. A database-only restore leaves every
session token invalid, so the Job fails loudly rather than shipping half.

## What runs

| | |
| --- | --- |
| Schedule | `0 3 * * *` (03:00 UTC), `concurrencyPolicy: Forbid` |
| Node | pinned to `agent-00` — where `/mnt/data` (the block volume) is attached |
| Destination | OCI Object Storage, bucket `eden-backups`, prefix `vault/` |
| Retention | 30-day bucket lifecycle policy |
| Size | ~200 KB per run encrypted |

`/data` is read via `hostPath: /mnt/data/pv` read-only rather than by mounting the
PVC: it is RWO and the vaultwarden pod holds it, so it cannot be co-mounted. Same
approach as `apps/music/config-backup`.

`pg_dump` connects with `DATABASE_URL` from `vaultwarden-credentials` — the same
credential vaultwarden uses. The `postgres` superuser password in
`postgres-shared-postgres-credentials` does **not** authenticate over TCP; the
`vaultwarden` role owns the database, so this is both correct and least-privilege.

## Cluster prerequisites (not in git — they carry secrets)

```sh
# public key — the cluster's half of the keypair
kubectl -n shared-services create configmap vault-backup-pubkey --from-file=public.pem=public.pem

# the write-only upload URL
kubectl -n shared-services create secret generic vault-backup-target --from-file=par-url=par.url
```

Recreate the PAR when it expires (**2027-08-10**):

```sh
oci os preauth-request create --bucket-name eden-backups --name vault-backup-cronjob \
  --access-type AnyObjectWrite --time-expires <RFC3339>
```

## Where the private key lives

Two copies, deliberately in different failure domains:

1. **Vaultwarden** — `shared/backup/vault-backup-private-key`. The convenient copy.
   Useless when the vault is the thing that is down.
2. **Offline**, alongside the encrypted recovery bundle (Desktop / Drive / USB).
   This is the copy that matters in a real disaster.

The key is **never** committed to this repo, and copy 2 must never be the only one
inside the vault it exists to rescue.

## Restore

```sh
oci os object list -bn eden-backups --prefix vault/          # newest last
oci os object get -bn eden-backups --name vault/<obj>.enc --file b.enc
openssl smime -decrypt -binary -in b.enc -inform DER -inkey private.pem -out b.tar.gz
tar xzf b.tar.gz          # -> db.pgdump + data.tar.gz
```

Then follow `docs/cloud-cluster.md` §Backups, or `RESTORE.md` in the offline
bundle for the no-cluster path.

**Verify by restoring, not by reading.** Restore `db.pgdump` into a scratch
database and compare counts. Note `select count(*) from ciphers` overcounts —
Vaultwarden soft-deletes, so compare `count(*) filter (where deleted_at is null)`.

## Not GitOps-reconciled

The prod cluster is **not** driven by Argo from this repo — `platform/services/gitops/`
reconciles the homelab only. This manifest is version-controlled but applied
deliberately:

```sh
KUBECONFIG=~/.kube/cloud.yaml kubectl apply -f cronjob.yaml
KUBECONFIG=~/.kube/cloud.yaml kubectl -n shared-services create job vault-backup-manual --from=cronjob/vault-backup
```

## Known gaps

- **Still single-cloud.** Backups sit in OCI Object Storage — a different service
  and durability domain from the block volume, so it survives instance and disk
  loss. It does **not** survive losing the Oracle account. An off-Oracle pull leg
  (homelab or workstation fetching from this bucket on a schedule) is the
  remaining work.
- **No alerting.** A silently failing CronJob looks identical to a working one.
  Nothing notices yet if backups stop.
