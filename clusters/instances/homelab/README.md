# homelab cluster

The live 8-node HA k3s v1.35.5 cluster on 3 Proxmox hosts — the self-hosted
media/music platform + platform experimentation substrate. All nodes on the
Tailscale mesh. Declared from live `kubectl` (2026-07-05).

This is a **Phase-0 declaration** in the homelab→IDP migration
(`docs/migration-homelab-to-idp.md`): it *describes* the running cluster in IDP
form. Nothing here reconciles onto the cluster yet — it is read by
`clusters/ctl.sh validate` and future provisioning, not by a live controller.

## Topology

| Node | k3s role | cluster_role | Host | vCPU / RAM | Notes |
|------|----------|--------------|------|-----------|-------|
| k3s-cp-0 | server | devops | pve-00 | 2 / 4Gi | control-plane + etcd |
| k3s-cp-1 | server | devops | pve-01 | 2 / 4Gi | control-plane + etcd |
| k3s-cp-2 | server | devops | pve-03 | 2 / 3Gi | control-plane + etcd |
| k3s-w-0 | agent | devops | pve-00 | 4 / 14Gi | platform/observability |
| k3s-w-1 | agent | **apps** | pve-00 | 4 / 14Gi | **media node** — NVMe `/mnt/media` + Radeon 780M |
| k3s-w-2 | agent | apps | pve-00 | 4 / 14Gi | |
| k3s-w-3 | agent | apps | pve-01 | 4 / 9Gi | |
| k3s-w-4 | agent | apps | pve-01 | 4 / 9Gi | |

## Ratified divergences from the template
- **CNI = flannel + kube-router** (not Cilium). NetworkPolicy **is** enforced
  (kube-router, empirically verified) — no Cilium reinstall.
- **policy_profile = audit-only** during migration; enforce per-namespace later.
- **edge TLS = letsencrypt-dns01** (cert-manager) not cloudflare-origin.
- **No irreplaceable nodes** — Proxmox VMs are cattle.
- **w-1 = apps + labels, no taint** — avoids evicting the pinned media workload.

See `docs/migration-homelab-to-idp.md` for the full plan + all 9 decisions.
