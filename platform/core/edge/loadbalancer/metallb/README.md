# platform/core/edge/loadbalancer/metallb

MetalLB provides `type: LoadBalancer` IPs on bare-metal / homelab clusters that
have no cloud load balancer. On the homelab it hands out LAN IPs from the pool
`10.168.0.240–250` (ingress-nginx = `.240`).

> **Migration status (Phase 1 — DORMANT).** `pool.yaml` is the live
> `IPAddressPool` + `L2Advertisement`, relocated byte-identical from
> `homelab/kubernetes/metallb/`. Not yet Argo-managed. New leaf per decision 5
> (the template had no loadbalancer/ home). See `docs/migration-homelab-to-idp.md`.

## Policy note
MetalLB's speaker needs `hostNetwork` + `NET_RAW`, which restricted PodSecurity
rejects. There is no PolicyException to write and no engine to write it for:
Kyverno is gone for good (`.claude/rules/50-cluster-architecture.md` §4), and the
2 policies in `platform/core/policy/` guard deletion only — they never look at a
pod. The in-tree mechanism is a PodSecurity label on the namespace, and
`metallb-system` already carries
`pod-security.kubernetes.io/enforce=privileged` on the live cluster. **That is
also why the cluster cannot move to `restricted` wholesale**: this namespace is
the exception that forces per-namespace levels.
