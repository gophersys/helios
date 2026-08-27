# platform/core/edge/loadbalancer/metallb

MetalLB provides `type: LoadBalancer` IPs on bare-metal / homelab clusters that
have no cloud load balancer. On the homelab it hands out LAN IPs from the pool
`10.168.0.240–250` (`pool.yaml`).

## Address allocation

| Address | Service | Pinned? |
|---|---|---|
| `10.168.0.240` | `ingress-nginx/ingress-nginx-controller` | **no — allocated, see below** |
| `10.168.0.241` | `observability/grafana` | yes — `metallb.io/loadBalancerIPs` in `platform/services/observability/chart/values-homelab.yaml` |
| `.242`–`.250` | free | — |

**Pin the address of any Service whose address is written down anywhere.**
MetalLB assigns the lowest free address in the pool, so an unpinned address is
an artifact of creation order, not a property of the service. Use the annotation
form and the `metallb.io/` key:

```yaml
metadata:
  annotations:
    metallb.io/loadBalancerIPs: "10.168.0.241"
```

Not `metallb.universe.tf/loadBalancerIPs`: it still works on the MetalLB running
here (v0.16.1) but raises a `deprecatedAnnotation` warning Event on every such
Service. Not `spec.loadBalancerIP` either — Kubernetes deprecated that field in
1.24. Both statements were verified on the live cluster with throwaway Services,
2026-08-19.

> **FOLLOW-UP, not fixed here: `ingress-nginx` holds `.240` unpinned.** Its
> Service carries no `loadBalancerIPs` annotation and no `loadBalancerIP`; it
> holds `.240` because it was the first LoadBalancer Service to exist. That
> address is load-bearing in far more places than Grafana's — `contracts/`
> `exposure.yaml` (`homelab_vip`), `contracts/ingress.md`, every tailnet A
> record, and several app ingress headers. It predates this note and pinning it
> touches the live ingress path, so it is recorded rather than changed in
> passing. Pin it in its own change, where the blast radius gets its own
> attention.

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
