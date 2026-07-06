# Homelab → IDP migration (historical)

> **Status: COMPLETE.** This document is referenced from several READMEs and
> `clusters/instances/homelab/identity.yaml`. The migration it describes — moving
> the ad-hoc homelab manifests into the 7-layer IDP structure — finished in
> 2026-07; the cluster now lives entirely under `clusters/`, `platform/`, and
> `apps/`. For the current state see `docs/cluster-topology.md`. This file is
> kept as the record of the ratified decisions so the references don't dangle
> (debt-register D8).

## What it was
The homelab started as a flat `kubernetes/` tree. It was **relocated** (not
bolted on) into the IDP layers via zero-downtime, byte-identical Argo moves,
then formalized. Verified throughout by zero pod restarts.

## Ratified decisions (the ones that shaped the layout)
1. **Cluster instance** — `clusters/instances/homelab/`, env `prod`; the
   media/portal project is `music` in namespace `media`.
2. **CNI** — flannel + **kube-router** (NetworkPolicy IS enforced here —
   empirically verified; the plan's "flannel ignores NP" assumption was wrong).
   No Cilium reinstall.
3. **Secrets** — self-hosted cloud Vaultwarden as the single source of truth,
   reached via ESO + a self-built `bw-serve` bridge. No homelab replica.
4. **VPN workload** — gluetun needs `NET_ADMIN`, incompatible with a blanket
   `restricted` PSS, so it lives in a namespace excluded from the baseline
   policy rather than forcing `restricted` cluster-wide.
5. **Media node** — `k3s-w-1` is `apps` + NVMe/GPU labels with **no taint**
   (avoids the eviction trap).
6. **Observability** — kube-prometheus-stack (+ Loki/Tempo/Alloy).
7. **GitOps** — Argo CD app-of-apps from `platform/services/gitops/registry/`;
   `argocd` namespace kept.
8. **Policy** — Kyverno installed audit-only first; enforce per-namespace only
   after exceptions land.
9. **Storage** — `local-path` default for re-downloadable media; Longhorn
   available for volumes that must survive a node.

## Current state
`docs/cluster-topology.md` — the authoritative namespace-by-namespace reference.
