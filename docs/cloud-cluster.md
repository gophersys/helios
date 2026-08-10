# Cloud cluster (OCI Phoenix)

What actually runs on the Oracle Cloud k3s cluster, and why it matters more than
its size suggests: **this is where Vaultwarden lives**, so it is the root of trust
for every credential in the ecosystem. The homelab depends on it. It depends on
nothing.

Verified against the live cluster 2026-08-09.

> **Direction of dependency: `homelab` → cloud. Never the reverse.**
> The homelab's External Secrets Operator resolves secrets from the Vaultwarden
> that runs here. The homelab can burn down without threatening a credential.
> This cluster going down locks every secret in the ecosystem.

## Nodes

| k8s node | OCI instance | Shape | Role |
| --- | --- | --- | --- |
| `code-kit-server` | `server-00` | VM.Standard.A1.Flex (ARM 2/12) | control-plane, **etcd** |
| `agent-00` | `agent-00` | VM.Standard.A1.Flex (ARM 2/12) | worker, holds all storage |

k3s `v1.34.5+k3s1`, Ubuntu 22.04.5, flannel CNI (not Cilium). Both nodes are on
the Tailscale mesh and both sit in `FEQI:PHX-AD-1`, inside VCN `prod-vcn` /
subnet `prod-public-subnet`.

Public entry is a **real public IP on the cluster — `144.24.23.2`** — not a
Cloudflare tunnel. `*.mateosegura.com` wildcard DNS points here, `ingress-nginx`
terminates, and cert-manager issues Let's Encrypt certs (`letsencrypt-prod`).
This is the opposite of the homelab model and the difference is deliberate: the
vault must stay reachable when Cloudflare is not.

> **`code-kit-server` is a legacy name.** The OCI instance, its boot volume and
> the OS hostname are all `server-00`; only the k3s node registration still says
> `code-kit-server`. It is **not** safe to rename in place: k3s derives its etcd
> member identity from the node name, and on a single-member cluster a rename can
> leave etcd refusing to start against a member list it no longer recognises. The
> safe path is to add a second server node, let etcd form a real quorum, then roll
> the original — worth doing for HA, not for cosmetics. `agent-00` was renamed
> from `code-kit-agent-1` on 2026-08-09 precisely because it carried no such
> coupling.

## Workloads

### `shared-services`
- **vaultwarden** (`1.35.4`) at `secrets.mateosegura.com` — see the split-ingress
  note below. Backed by **PostgreSQL**, not SQLite: `DATABASE_URL` is injected from
  a Secret, so an env dump reads empty and `/data` holds no `.sqlite3` file. The
  item data lives in the `vaultwarden` database on `postgres-shared`; `/data`
  holds `rsa_key.pem` (the JWT signing key, **not** encrypted the way items are),
  attachments and sends.
- **oauth2-proxy** — Google SSO in front of the vault's web UI.
- **postgres-shared**, **couchdb-shared** (`notes.mateosegura.com`),
  **prometheus-server**, **grafana** (`obsv.mateosegura.com`), **otel-collector**.

### `observability`
Loki, Tempo, Alloy (gateway + logs DaemonSet). All telemetry data is disposable
and was reset on 2026-08-09.

### Platform
`cert-manager` (three working ClusterIssuers), `ingress-nginx`, `sealed-secrets`,
`tailscale` subnet-router.

## The vault's two doors

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

**Web UI** takes Google SSO *then* the master password. **The API path does not** —
it is master-password only. That is deliberate: it is what makes recovery work when
Google, Cloudflare, Tailscale and the homelab are all unavailable. It is also the
thinnest part of the perimeter, which is why TOTP on the vault account matters.

Hardening in place: `SIGNUPS_ALLOWED=false`, `INVITATIONS_ALLOWED=false`,
`ORG_CREATION_USERS=none`, and `EMERGENCY_ACCESS_ALLOWED=false` — the last means
no trusted contact can ever recover this vault. Only the account owner can.

## Storage — `block-local`, not `local-path`

Every PVC is on StorageClass **`block-local`**: hand-written `local` PVs on a
**50 GB OCI Block Volume** attached to `agent-00`, formatted ext4 and mounted at
`/mnt/data` via `/etc/fstab` (`nofail`). PV directories live under `/mnt/data/pv/<pvc>`.

| PVC | Namespace | Holds |
| --- | --- | --- |
| `data-postgres-shared-postgres-0` | shared-services | **the vault database** |
| `vaultwarden-data` | shared-services | `rsa_key.pem`, attachments, sends |
| `data-couchdb-shared-couchdb-0` | shared-services | notes |
| `prometheus-server`, `storage-loki-0`, `storage-tempo-0` | — | disposable telemetry |

**Nothing is on `local-path` any more.** That matters: `local-path` stamped each PV
with `nodeAffinity` bound to a node-name *string* it also owned, so a node rename
orphaned the volume permanently and a node loss destroyed the data outright. The
volumes are now on a block device that detaches from a dead instance and reattaches
elsewhere, and because the PVs are hand-written, `nodeAffinity` is a field we can
edit rather than one a provisioner owns.

`reclaimPolicy` is `Retain` on every PV — deleting a PVC no longer deletes data.

**Renaming a node still requires recreating the PV objects** (`nodeAffinity` is
immutable). Delete the PVC and PV, recreate both pointing at the new node name; the
data under `/mnt/data/pv/` is untouched throughout. Expect one gotcha: a renamed
node gets a **new pod CIDR**, and any DaemonSet pod that survives the rename keeps
an address from the old range and silently fails its probes. Delete those pods and
clear the stale `/var/lib/cni/networks/cbr0/<old-ip>` entries.

## Backups

`pg_dump` of the `vaultwarden` database plus a tar of `/data`. Both are required —
the database without `rsa_key.pem` leaves you re-issuing every session token.

```sh
export KUBECONFIG=~/.kube/cloud.yaml
kubectl -n shared-services exec postgres-shared-postgres-0 -- \
  pg_dump -U postgres -d vaultwarden --format=custom --no-owner --no-privileges > vault.pgdump
kubectl -n shared-services exec deploy/vaultwarden -- tar czf - -C / data > vault-data.tar.gz
```

Verify a dump by restoring it into a scratch database and comparing counts — an
untested backup is a belief, not a backup:

```sh
kubectl -n shared-services exec -i postgres-shared-postgres-0 -- sh -c '
  cat > /tmp/v.pgdump
  psql -U postgres -tAc "create database vw_restoretest;"
  pg_restore -U postgres -d vw_restoretest --no-owner --no-privileges /tmp/v.pgdump
  psql -U postgres -d vw_restoretest -tAc "select count(*) from ciphers;"
  psql -U postgres -tAc "drop database vw_restoretest;"' < vault.pgdump
```

Counting `ciphers` overstates the item count: Vaultwarden **soft-deletes**, so the
table includes trashed rows. Compare `count(*) filter (where deleted_at is null)`
against what `bw list items` returns.

**Open gap:** this is manual. There is no CronJob and no off-cluster copy on a
schedule. See debt-register D14.

## Access

```
~/.kube/cloud.yaml           direct, via the public IP — works without the tailnet
~/.kube/cloud-tailnet.yaml   over Tailscale
```

Tailscale SSH is enabled — `ssh ubuntu@<tailnet-ip>` needs no key. The vault item
`shared/ssh/bastion-private-key` is stored as `SSH_PRIVATE_KEY_B64=<base64>`, an
env-var line rather than a bare PEM, so it will not parse if fed straight to `ssh -i`.

True break-glass is the **OCI console** (Compute → Instances → Console Connection):
serial access needing neither SSH nor the network. That credential must never live
in the vault it is meant to rescue.

## Always Free budget

Four instances at ~50 GB boot each consumed the entire 200 GB storage allowance,
leaving no room for block storage — OCI's minimum block volume is 50 GB and boot
volumes cannot be shrunk, only expanded. Deleting the two idle `sentinel-*`
bastions (which ran nothing but `tailscaled`, and were redundant once Tailscale SSH
reached every node directly) freed 94 GB and made the data volume possible.

```
server-00 boot    50 GB
agent-00 boot     50 GB
prod-data-01      50 GB   ← the block volume
─────────────────────────
                 150 GB of 200 GB
```

Adding an instance or a second block volume exceeds the allowance and starts
billing. Budget before provisioning.
