# Homelab → IDP migration (historical)

> **Status: COMPLETE.** Several READMEs and
> `clusters/instances/homelab/identity.yaml` reference this document. The
> migration it describes — the move of the ad-hoc homelab manifests into the
> 7-layer IDP structure — finished in 2026-07. The cluster now lives entirely
> under `clusters/`, `platform/` and `apps/`. For the current state read
> `docs/cluster-topology.md`. This file stays as the record of the ratified
> decisions, so that the references resolve (debt-register D8).

## What it was
The homelab started as a flat `kubernetes/` tree. It was **relocated** into the
IDP layers, not added on top of them. The moves were byte-identical Argo moves
with no downtime, and the structure was formalized afterwards. Zero pod restarts
verified the result at every step.

## Ratified decisions (the ones that shaped the layout)
1. **Cluster instance** — `clusters/instances/homelab/`, env `prod`. The media
   and portal project is `music`, in namespace `media`.
2. **CNI** — flannel plus **kube-router**. NetworkPolicy IS enforced here, and we
   verified that empirically. The plan's assumption that "flannel ignores
   NetworkPolicy" was wrong. There is no Cilium reinstall.
3. **Secrets** — the self-hosted cloud Vaultwarden is the single source of truth,
   reached through ESO and a `bw-serve` bridge that we built. There is no homelab
   replica.
4. **VPN workload** — gluetun needs `NET_ADMIN`, which is incompatible with a
   blanket `restricted` PSS. It therefore lives in a namespace that the baseline
   policy excludes, instead of a cluster-wide change to `restricted`.
5. **Media node** — `k3s-w-1` is `apps` plus the NVMe and GPU labels, with **no
   taint**. That avoids the eviction trap.
6. **Observability** — kube-prometheus-stack, plus Loki, Tempo and Alloy.
7. **GitOps** — an Argo CD app-of-apps from
   `platform/services/gitops/registry/`. The `argocd` namespace is kept.
8. **Policy** — Kyverno is installed audit-only first. Enforce per namespace only
   after the exceptions land.
   > **Superseded 2026-08-19 (this document is a historical record; decision 8 as
   > ratified is left as written).** Kyverno never left audit-only and was removed
   > on 2026-08-09. What enforces today is `platform/core/policy/`: 2 in-tree
   > `ValidatingAdmissionPolicy` objects with `validationActions: [Deny]`, guarding
   > deletion of protected PVCs and namespaces. No engine, no audit-only stage.
   > See `.claude/rules/50-cluster-architecture.md` §4.
9. **Storage** — `local-path` is the default for media that can be downloaded
   again. Longhorn is available for a volume that must survive a node.

## Current state
`docs/cluster-topology.md` is the authoritative reference, namespace by namespace.
