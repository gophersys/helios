# Cloud cluster (OCI Phoenix)

What runs on the Oracle Cloud k3s cluster, and why it matters more than its size
suggests. **Vaultwarden runs here**, so this cluster is the root of trust for
every credential in the ecosystem. The homelab depends on it. It depends on
nothing.

Verified against the live cluster 2026-08-09.

> **Direction of the dependency: `homelab` → cloud. Never the reverse.**
> The External Secrets Operator of the homelab resolves its secrets from the
> Vaultwarden that runs here. The homelab can burn down without a threat to a
> credential. If this cluster goes down, every secret in the ecosystem is locked.

## Nodes

| k8s node | OCI instance | Shape | Role |
| --- | --- | --- | --- |
| `code-kit-server` | `server-00` | VM.Standard.A1.Flex (ARM 2/12) | control-plane, **etcd** |
| `agent-00` | `agent-00` | VM.Standard.A1.Flex (ARM 2/12) | worker, holds all storage |

k3s `v1.34.5+k3s1`, Ubuntu 22.04.5, flannel CNI (not Cilium). Both nodes are on
the Tailscale mesh. Both sit in `FEQI:PHX-AD-1`, inside VCN `prod-vcn` and subnet
`prod-public-subnet`.

Public entry is a **real public IP on the cluster — `144.24.23.2`** — not a
Cloudflare tunnel. The wildcard DNS record `*.mateosegura.com` points here,
`ingress-nginx` terminates, and cert-manager issues Let's Encrypt certificates
(`letsencrypt-prod`). This is the opposite of the homelab model, and the
difference is deliberate: the vault must stay reachable when Cloudflare is not.

> **`code-kit-server` is a legacy name.** The OCI instance, its boot volume and
> the OS hostname are all `server-00`. Only the k3s node registration still says
> `code-kit-server`. It is **not** safe to rename in place: k3s derives its etcd
> member identity from the node name, and on a single-member cluster a rename can
> leave etcd unable to start against a member list it no longer recognises. The
> safe procedure is to add a second server node, let etcd form a real quorum,
> then replace the original. Do that for HA, not for appearance. `agent-00` was
> renamed from `code-kit-agent-1` on 2026-08-09 because it had no such coupling.

## Workloads

### `shared-services`
- **vaultwarden** (`1.35.4`) at `secrets.mateosegura.com` — see the note on the
  split ingress below. It is backed by **PostgreSQL**, not SQLite: a Secret
  injects `DATABASE_URL`, so a dump of the environment reads empty and `/data`
  holds no `.sqlite3` file. The item data lives in the `vaultwarden` database on
  `postgres-shared`. `/data` holds `rsa_key.pem` (the JWT signing key, which is
  **not** encrypted the way the items are), the attachments and the sends.
- **oauth2-proxy** — Google SSO in front of the web UI of the vault.
- **postgres-shared**, **couchdb-shared** (`notes.mateosegura.com`),
  **prometheus-server**, **grafana** (`obsv.mateosegura.com`), **otel-collector**.

### `observability`
Loki, Tempo and Alloy (gateway plus the logs DaemonSet). All telemetry data can
be discarded, and it was reset on 2026-08-09.

### Platform
`cert-manager` (3 working ClusterIssuers), `ingress-nginx`, `sealed-secrets` and
the `tailscale` subnet router.

## The 2 doors of the vault

```
                    ingress-nginx
                          │
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
  secrets-manager-web              secrets-manager-noauth
  path: /                          /oauth2 /api /identity
        │                          /notifications /icons
        ▼                                    │
  oauth2-proxy (Google)                      │ no proxy
        └──────────► vaultwarden ◄───────────┘
                (master password on BOTH)
```

The **web UI** takes Google SSO *and then* the master password. **The API path
does not.** It takes the master password only. That is deliberate: it is what
makes recovery work when Google, Cloudflare, Tailscale and the homelab are all
unavailable. It is also the weakest part of the perimeter, which is why TOTP on
the vault account matters.

Hardening in place: `SIGNUPS_ALLOWED=false`, `INVITATIONS_ALLOWED=false`,
`ORG_CREATION_USERS=none` and `EMERGENCY_ACCESS_ALLOWED=false`. The last setting
means that no trusted contact can ever recover this vault. Only the account owner
can.

## Storage — `block-local`, not `local-path`

Every PVC is on the StorageClass **`block-local`**. These are hand-written
`local` PVs on a **50 GB OCI Block Volume** attached to `agent-00`, formatted
ext4 and mounted at `/mnt/data` through `/etc/fstab` (`nofail`). The PV
directories are under `/mnt/data/pv/<pvc>`.

| PVC | Namespace | Holds |
| --- | --- | --- |
| `data-postgres-shared-postgres-0` | shared-services | **the vault database** |
| `vaultwarden-data` | shared-services | `rsa_key.pem`, attachments, sends |
| `data-couchdb-shared-couchdb-0` | shared-services | notes |
| `prometheus-server`, `storage-loki-0`, `storage-tempo-0` | — | telemetry that can be discarded |

**Nothing is on `local-path` any more.** That matters: `local-path` stamped each
PV with a `nodeAffinity` bound to a node-name *string* that it also owned. A node
rename therefore orphaned the volume permanently, and a node loss destroyed the
data. The volumes are now on a block device that detaches from a dead instance
and attaches elsewhere. The PVs are hand-written, so `nodeAffinity` is a field we
can edit, not a field a provisioner owns.

`reclaimPolicy` is `Retain` on every PV, so deletion of a PVC no longer deletes
the data.

**A rename of a node still requires that you recreate the PV objects**, because
`nodeAffinity` is immutable. Delete the PVC and the PV, then create both again
pointing at the new node name. The data under `/mnt/data/pv/` is not touched at
any point. Expect one problem: a renamed node gets a **new pod CIDR**, and any
DaemonSet pod that survives the rename keeps an address from the old range and
fails its probes with no message. Delete those pods and clear the stale
`/var/lib/cni/networks/cbr0/<old-ip>` entries.

## Backups

A backup is a `pg_dump` of the `vaultwarden` database plus a tar of `/data`. Both
are required: the database without `rsa_key.pem` makes you issue every session
token again.

```sh
export KUBECONFIG=~/.kube/cloud.yaml
kubectl -n shared-services exec postgres-shared-postgres-0 -- \
  pg_dump -U postgres -d vaultwarden --format=custom --no-owner --no-privileges > vault.pgdump
kubectl -n shared-services exec deploy/vaultwarden -- tar czf - -C / data > vault-data.tar.gz
```

Verify a dump: restore it into a scratch database and compare the counts. A
backup that nobody tested is a belief, not a backup.

```sh
kubectl -n shared-services exec -i postgres-shared-postgres-0 -- sh -c '
  cat > /tmp/v.pgdump
  psql -U postgres -tAc "create database vw_restoretest;"
  pg_restore -U postgres -d vw_restoretest --no-owner --no-privileges /tmp/v.pgdump
  psql -U postgres -d vw_restoretest -tAc "select count(*) from ciphers;"
  psql -U postgres -tAc "drop database vw_restoretest;"' < vault.pgdump
```

A count of `ciphers` gives a number that is too high. Vaultwarden
**soft-deletes**, so the table includes the rows in the trash. Compare
`count(*) filter (where deleted_at is null)` against the result of
`bw list items`.

**Open gap:** this procedure is manual. There is no CronJob and no copy off the
cluster on a schedule. See debt-register D14.

## Access

```
~/.kube/cloud.yaml           direct, via the public IP — works without the tailnet
~/.kube/cloud-tailnet.yaml   over Tailscale
```

Tailscale SSH is enabled, so `ssh ubuntu@<tailnet-ip>` needs no key. The vault
item `shared/ssh/bastion-private-key` is stored as `SSH_PRIVATE_KEY_B64=<base64>`.
That is an env-var line, not a bare PEM, so it does not parse if you feed it
straight to `ssh -i`.

The true break-glass path is the **OCI console** (Compute → Instances → Console
Connection). It gives serial access and needs neither SSH nor the network. That
credential must never live in the vault it is meant to rescue.

## Always Free budget

4 instances with a boot volume of about 50 GB each used the whole 200 GB storage
allowance and left no room for block storage. The minimum OCI block volume is
50 GB, and you can only expand a boot volume, never shrink it. Deleting the 2
idle `sentinel-*` bastions freed 94 GB and made the data volume possible. Those
bastions ran nothing but `tailscaled`, and they became unnecessary once Tailscale
SSH reached every node directly.

```
server-00 boot    50 GB
agent-00 boot     50 GB
prod-data-01      50 GB   ← the block volume
─────────────────────────
                 150 GB of 200 GB
```

An extra instance or a second block volume exceeds the allowance and starts
billing. Calculate the budget before you provision.
