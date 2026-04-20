# platform/core/namespace-provisioner

Automated namespace lifecycle — when a new namespace is created matching
`app-*` or `platform-*`, provision it with the standard baseline
(labels, NetworkPolicies, ResourceQuota, LimitRange, ServiceAccount
conventions). When deleted, verify protection rules pass.

## Why

A namespace without a NetworkPolicy accepts all traffic. A namespace
without a ResourceQuota can starve the cluster. A namespace without a
LimitRange lets pods declare whatever resources they want. Every new
namespace must get all of these — manually applying them is error-prone.

## Default implementation

**Kyverno `generate` policies** — mechanism already present (see
`platform/core/policy/`). Implementing namespace-provisioner is a set of
generate-policies living here rather than in the policy catalog, because
they're about **creation side-effects** rather than admission control.

The policies watch for new namespaces matching the naming pattern and
generate the required resources into the new namespace:

1. `NetworkPolicy/default-deny-ingress`
2. `NetworkPolicy/default-deny-egress`
3. `NetworkPolicy/allow-dns`
4. `NetworkPolicy/allow-same-namespace`
5. `NetworkPolicy/allow-metrics-scrape`
6. `ResourceQuota/baseline` — CPU, memory, pod count, PVC count
7. `LimitRange/baseline` — default requests/limits per container
8. Labels applied to the namespace itself:
   - `pod-security.kubernetes.io/enforce=restricted`
   - `pod-security.kubernetes.io/audit=restricted`
   - `pod-security.kubernetes.io/warn=restricted`
   - `platform.gophersys/tenant=<derived from namespace prefix>`

## Naming conventions enforced

| Pattern            | Tenant                  | Default quota           |
|--------------------|-------------------------|-------------------------|
| `app-<name>`       | derived from prefix     | small (CPU 4, mem 8Gi, 20 pods) |
| `platform-<comp>`  | `platform`              | medium (CPU 8, mem 16Gi, 40 pods) |
| `kube-*`           | skipped (platform skips kube-system, kube-public, kube-node-lease) | n/a |

Names outside these patterns are rejected (see
`platform/core/policy/CATALOG.md` → namespace validation, when added).

## Quota tiers

The baseline ResourceQuota is a starting point, not a ceiling. Apps with
larger footprints declare a quota override in the namespace's
`provisioning.yaml` (future CR/annotation) picked up by the generator:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: app-codectl
  annotations:
    platform.gophersys/quota-tier: medium          # small | medium | large | custom
    platform.gophersys/quota-reason: "dashboard handles SSE connections for all users"
```

Tier → resources:
- `small`: 4 CPU / 8 GiB / 20 pods / 10 PVC
- `medium`: 8 CPU / 16 GiB / 40 pods / 20 PVC
- `large`: 16 CPU / 32 GiB / 80 pods / 40 PVC
- `custom`: requires a `ResourceQuota` object created by hand in the
  namespace BEFORE the generator runs (detection stops the generator).

Escalating from `small` → `medium` requires a platform PR.

## LimitRange baseline

```yaml
limits:
  - type: Container
    default:
      cpu: 500m
      memory: 512Mi
    defaultRequest:
      cpu: 50m
      memory: 64Mi
    min:
      cpu: 10m
      memory: 16Mi
    max:
      cpu: 4000m
      memory: 8Gi
  - type: PersistentVolumeClaim
    min: { storage: 1Gi }
    max: { storage: 200Gi }
```

Apps override via explicit `resources` in their chart values (see
`platform/core/policy/` → `resources-required`). LimitRange is the
safety net for anyone who forgets.

## Lifecycle

- **Create** a namespace → generator kicks in asynchronously; baseline
  resources appear within seconds.
- **Update** namespace labels/annotations → generator reconciles quota
  tier if `platform.gophersys/quota-tier` changed.
- **Delete** namespace → `platform/core/policy/namespace-delete-protection`
  validates. Generator removes any lingering non-namespaced resources
  it owned (nothing today; hook reserved for future cluster-scoped refs).

## Observability

Every provisioning action emits a `NamespaceProvisioned` event (Kyverno
generator event) scraped by the observability stack. Grafana "platform
compliance" dashboard shows:

- Count of namespaces per tenant + tier.
- Namespaces missing generated resources (should always be 0).
- Quota utilization per namespace (heatmap).

## Dependencies

- `platform/core/policy/` — the Kyverno install itself.
- `platform/core/network-policies/` — baseline NetworkPolicy templates
  referenced by the generator.

## Status

STUB. README only. The Kyverno generator policies land together with
the `platform/core/policy/` rollout, since they share the Kyverno
install.
