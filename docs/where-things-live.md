# Where things live, and why

One rule decides where a workload or a secret goes. Read this before you add
anything.

## The rule

**Put it in the cloud cluster if it must outlive your house.
Put it in the homelab if it needs your hardware.**

Everything below follows from that rule.

## The direction of the dependency — never invert it

```
homelab  ──depends on──>  cloud cluster (OCI)
cloud cluster  ──depends on──>  nothing
```

The homelab reads every secret from the Vaultwarden that runs in OCI. The cloud
cluster reads nothing from the homelab.

If you move the vault home, a power cut locks you out of your own credentials. A
house fire destroys them. This direction is the reason the recovery procedure
works. Do not change it.

## Cloud cluster (OCI Phoenix) — the root of trust

| Workload | Why it is here |
| --- | --- |
| **Vaultwarden + PostgreSQL** | every credential you own. It must survive the house. |
| **oauth2-proxy** | the gate in front of the vault |
| **CouchDB** (`notes.`) | small, wanted from anywhere |
| **Grafana / Loki / Tempo / Prometheus** | see the exception below |

The cluster has 2 OCI A1.Flex ARM nodes on the Always Free tier, so it costs
nothing. It does not depend on your power, your ISP, or your Proxmox hosts.

Public entry is a **real public IP with cert-manager, deliberately not
Cloudflare**. That is the one approved exception in `contracts/exposure.yaml`. It
exists so the vault stays reachable when Cloudflare is down. Do not move it onto
the tunnel.

## Homelab (k3s on 3 Proxmox hosts) — anything that needs your hardware

| Workload | What it needs that the cloud cannot give |
| --- | --- |
| **media stack** (qBittorrent, Prowlarr, filebrowser, homepage) | 8 TB NVMe, and a residential IP for torrent egress |
| **embedded-lab** (Zephyr devboxes) | physical microcontrollers on USB, passed through to `k3s-w-4` |
| **MinIO** | bulk backup storage on local NVMe, free |
| **Argo CD** | reconciles the homelab from git |
| **eden**, **workspaces** | the platform being built; free compute |

## How to decide for something new

Ask these questions in order. Stop at the first yes.

1. **Does the homelab depend on it to start?** → cloud cluster. Anything the
   homelab needs at boot cannot live inside the homelab.
2. **Does it need a physical device, local disk, or your home IP?** → homelab.
3. **Must it work while your house is offline?** → cloud cluster.
4. **Is it large, inexpensive to lose, or heavy on bandwidth?** → homelab. OCI
   Always Free gives 200 GB in total, and 150 GB is already used.
5. **If none of the above applies** → homelab. It has more resources and Argo
   reconciles it.

## Secrets follow the same rule, with a split

| Kind | Home |
| --- | --- |
| **Secrets** | Vaultwarden only. Passwords, private keys, tokens. |
| **Facts** | this repo only. Addresses, users, access methods, topology. |
| **Link** | the repo names the vault item; the value never appears in git. |

The name in the vault is `<scope>/<domain>/<item>`:

- `shared/` — infrastructure used by more than one thing
- `project/` — scoped to one project
- `personal/` — your own accounts

A fact stored in the vault decays without notice. The vault has no diff, no
review and no CI. That is exactly how `grafana.mateosegura.com` stayed publicly
exposed for weeks while the documents said it was private. **If it is not secret,
it goes in git.**

## The one workload that does not follow the rule

**Observability lives in the cloud cluster.** By rule 5 it should be at home.

The homelab `obs` Helm release had been in `failed` state since 2026-06-18 and
Argo never managed it. Nothing reconciled it, and every hand-applied fix reverted
without a message. It was removed on 2026-08-09, together with its namespace and
its PVC.

Metrics and logs do not need to outlive the house. If homelab observability
returns, put it at home and let Argo reconcile it. Until then
`obsv.mateosegura.com` is the only Grafana, and its current position is
acceptable.

## Personal work — `gophersys/home`

`gophersys/home` holds everything of Mateo's that is not a platform product:
sites, documents, records, one-off tools. The same Argo reconciles it onto the
same homelab cluster, and its CI runs on the same `arc-org` pool.

It is a repo in the **org**, not on the personal account, because a self-hosted
runner registers at repository, organization or enterprise scope. There is no
user-account scope. A repo owned by a person could never use `arc-org`. The only
other options were 1 ARC scale set per repo, or GitHub-hosted runners and the
loss of the same environment for dev and CI.

The split with this repo: **content lives with the thing it belongs to; the
declaration of what is deployed stays here.** `rayne.mateosegura.com` was the
first case (taken down 2026-08-16; its page stays in `home`, undeployed). The
pattern stands for the next case: page and manifests in the owning repo, the
Argo `Application` in `platform/services/gitops/registry/`.

## Related

- `contracts/exposure.yaml` — every hostname and its exposure class
- `contracts/access.yaml` — every machine and how to reach it
- `docs/cloud-cluster.md` — the OCI cluster in detail
- `docs/machine-inventory.md` — the machine map
