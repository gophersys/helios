# Where things live, and why

One rule decides where a workload or a secret goes. Read this before you add
anything.

## The rule

**Put it in the cloud cluster if it must outlive your house.
Put it in the homelab if it needs your hardware.**

Everything below follows from that sentence.

## The dependency direction — never invert it

```
homelab  ──depends on──>  cloud cluster (OCI)
cloud cluster  ──depends on──>  nothing
```

The homelab reads every secret from the Vaultwarden that runs in OCI. The cloud
cluster reads nothing from the homelab.

If you move the vault home, a power cut locks you out of your own credentials.
A house fire destroys them. This direction is the reason the recovery story
works, and it is not negotiable.

## Cloud cluster (OCI Phoenix) — the root of trust

| Workload | Why it is here |
| --- | --- |
| **Vaultwarden + PostgreSQL** | every credential you own. Must survive the house. |
| **oauth2-proxy** | the gate in front of the vault |
| **CouchDB** (`notes.`) | small, wanted from anywhere |
| **Grafana / Loki / Tempo / Prometheus** | see the exception below |

Two OCI A1.Flex ARM nodes, Always Free, so it costs nothing. It does not depend
on your power, your ISP, or your Proxmox hosts.

Public entry is a **real public IP with cert-manager, deliberately not
Cloudflare**. That is the one sanctioned exception in `contracts/exposure.yaml`.
It exists so the vault stays reachable when Cloudflare is down. Do not "fix" it
onto the tunnel.

## Homelab (k3s on three Proxmox hosts) — anything that needs your hardware

| Workload | What it needs that the cloud cannot give |
| --- | --- |
| **media stack** (qBittorrent, Prowlarr, filebrowser, homepage) | 8 TB NVMe, and a residential IP for torrent egress |
| **embedded-lab** (Zephyr devboxes) | physical microcontrollers on USB, passed through to `k3s-w-4` |
| **MinIO** | bulk backup storage on local NVMe, free |
| **Argo CD** | reconciles the homelab from git |
| **eden**, **workspaces** | the platform being built; free compute |

## Deciding for something new

Ask in this order. Stop at the first yes.

1. **Does the homelab depend on it to start?** → cloud cluster. Anything the
   homelab needs at boot cannot live inside the homelab.
2. **Does it need a physical device, local disk, or your home IP?** → homelab.
3. **Must it work while your house is offline?** → cloud cluster.
4. **Is it large, cheap to lose, or bandwidth-hungry?** → homelab. OCI Always
   Free gives 200 GB total, and 150 GB is already used.
5. **Otherwise** → homelab. It has more resources and is reconciled by Argo.

## Secrets follow the same rule, with a split

| Kind | Home |
| --- | --- |
| **Secrets** | Vaultwarden only. Passwords, private keys, tokens. |
| **Facts** | this repo only. Addresses, users, access methods, topology. |
| **Link** | the repo names the vault item; the value never appears in git. |

Naming in the vault is `<scope>/<domain>/<item>`:

- `shared/` — infrastructure used by more than one thing
- `project/` — scoped to one project
- `personal/` — your own accounts

Facts stored in the vault rot silently. The vault has no diff, no review and no
CI. That is exactly how `grafana.mateosegura.com` stayed publicly exposed for
weeks while the docs claimed it was private. **If it is not secret, it goes in
git.**

## The one workload that breaks the rule

**Observability lives in the cloud cluster**, and by rule 5 it should be at home.

The homelab `obs` Helm release had been in `failed` state since 2026-06-18 and was
never managed by Argo, so nothing reconciled it and hand-applied fixes silently
reverted. It was removed on 2026-08-09 along with its namespace and PVC.

Metrics and logs do not need to outlive the house. If homelab observability comes
back, put it at home and reconcile it with Argo. Until then `obsv.mateosegura.com`
is the only Grafana, and it is fine where it is.

## Related

- `contracts/exposure.yaml` — every hostname and its exposure class
- `contracts/access.yaml` — every machine and how to reach it
- `docs/cloud-cluster.md` — the OCI cluster in detail
- `docs/machine-inventory.md` — the machine map
