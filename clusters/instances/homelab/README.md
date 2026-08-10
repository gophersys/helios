# homelab cluster

The live HA k3s v1.35.5 cluster: 8 nodes on 3 Proxmox hosts. It carries the
self-hosted media and music platform, and it is the substrate for platform
experiments. Every node is on the Tailscale mesh. This declaration was made from
the live `kubectl` output on 2026-07-05.

This is a **Phase-0 declaration** in the migration from the homelab to the IDP
(`docs/migration-homelab-to-idp.md`). It *describes* the running cluster in IDP
form. Nothing here reconciles onto the cluster yet. `clusters/ctl.sh validate`
reads it, and future provisioning will read it. No live controller reads it.

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

## Ratified differences from the template
- **CNI = flannel + kube-router**, not Cilium. NetworkPolicy **is** enforced, by
  kube-router, and we verified that empirically. There is no Cilium reinstall.
- **policy_profile = audit-only** during the migration. Enforce per namespace at
  a later date.
- **edge TLS = letsencrypt-dns01** through cert-manager, not cloudflare-origin.
- **There are no irreplaceable nodes.** A Proxmox VM here is replaceable.
- **w-1 = apps plus labels, with no taint.** That prevents an eviction of the
  media workload that is pinned to it.

See `docs/migration-homelab-to-idp.md` for the full plan and all 9 decisions.
