# platform/core/namespace-provisioner

Automated namespace lifecycle — when a new namespace matching
`<project>-<env>` or `platform-<component>` is created, the provisioner
applies the standard baseline (labels, NetworkPolicies, ResourceQuota,
LimitRange, ServiceAccount conventions). When a namespace is deleted,
the delete-protection policy gates the request.

## Why

A namespace without a NetworkPolicy accepts all traffic. A namespace
without a ResourceQuota can starve the cluster. A namespace without a
LimitRange lets pods declare whatever resources they want. Every new
namespace must get all of these — manually applying them is error-prone.

Beyond that, the pattern enforces **project taxonomy by construction**:
namespaces are created only for projects explicitly listed in the
cluster's `projects_hosted:`. Typos ("marketting-prod") and cross-
tenant leakage are rejected at admission.

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
4. `NetworkPolicy/allow-same-namespace` (apps in `codectl-prod` talk to
   each other freely; apps in `fintel-prod` cannot reach `codectl-prod`
   without explicit egress rules)
5. `NetworkPolicy/allow-metrics-scrape` (platform-monitoring →
   app pods on metrics port)
6. `ResourceQuota/baseline` — CPU, memory, pod count, PVC count (see
   tier table below)
7. `LimitRange/baseline` — default requests/limits per container
8. Labels applied to the namespace itself:
   - `pod-security.kubernetes.io/enforce=restricted`
   - `pod-security.kubernetes.io/audit=restricted`
   - `pod-security.kubernetes.io/warn=restricted`
   - `platform.gophersys/project=<project>` (parsed from namespace name)
   - `platform.gophersys/env=<env>` (parsed from namespace name)
   - `platform.gophersys/tenant=<derived — gophersys today>`

## Naming conventions enforced

| Pattern                  | Example                                     | What's checked                                                          |
|--------------------------|---------------------------------------------|-------------------------------------------------------------------------|
| `<project>-<env>`        | `codectl-prod`, `fintel-staging`            | `<project>` listed in cluster's `projects_hosted:`; `<env>` ∈ `{prod, staging, dev, lab}` |
| `platform-<component>`   | `platform-ingress`, `platform-monitoring`   | `<component>` matches a known platform component                        |
| `kube-*`                 | `kube-system`                               | Skipped by the generator (Kubernetes reserved)                          |

Names outside these patterns are rejected by the companion validating
policy `namespace-naming-enforced` (see
`platform/core/policy/CATALOG.md`).

## How the project registry works

Each cluster's `identity.yaml` declares which projects it hosts:

```yaml
# clusters/instances/prod/identity.yaml
projects_hosted:
  - codectl
  - fintel
  - finances
```

The generator reads this list (injected via a ConfigMap
`platform-registry` in the `platform-secrets` namespace, synced from the
repo at bootstrap time) and permits namespace creation only for those
projects. Attempting to create `marketing-prod` on a cluster that
doesn't list `marketing` fails with a clear error.

Adding a new project to a cluster = append to `projects_hosted:` in the
cluster identity + commit + re-apply namespace-provisioner (ConfigMap
refresh).

## Quota tiers

The baseline ResourceQuota is a starting point, not a ceiling. Quota is
per project-env (so `codectl-prod` has ONE quota shared by api +
dashboard + any other codectl-prod apps).

Projects with larger footprints declare a quota override in the
namespace's annotations picked up by the generator:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: codectl-prod
  annotations:
    platform.gophersys/quota-tier: medium          # small | medium | large | custom
    platform.gophersys/quota-reason: "dashboard handles SSE connections for all users"
```

Tier → resources:
- `small`:  4 CPU / 8 GiB / 20 pods / 10 PVC     — default for staging/dev/lab
- `medium`: 8 CPU / 16 GiB / 40 pods / 20 PVC    — default for prod
- `large`:  16 CPU / 32 GiB / 80 pods / 40 PVC   — explicit opt-in
- `custom`: requires a `ResourceQuota` object created by hand in the
  namespace BEFORE the generator runs (detection stops the generator)

Escalating from `small` → `medium` → `large` requires a platform PR
updating the cluster's `namespace_provisioning.quota_overrides:` map.

## LimitRange baseline

```yaml
limits:
  - type: Container
    default:         { cpu: 500m,  memory: 512Mi }
    defaultRequest:  { cpu: 50m,   memory: 64Mi  }
    min:             { cpu: 10m,   memory: 16Mi  }
    max:             { cpu: 4000m, memory: 8Gi   }
  - type: PersistentVolumeClaim
    min: { storage: 1Gi }
    max: { storage: 200Gi }
```

Apps override via explicit `resources` in their chart values (see
`platform/core/policy/` → `resources-required`). LimitRange is the
safety net for anyone who forgets.

## Lifecycle

- **Create** a namespace matching `<project>-<env>` on a cluster that
  lists `<project>` in `projects_hosted:` → generator kicks in
  asynchronously; baseline resources appear within seconds.
- **Create** matching the pattern but `<project>` not in the cluster's
  list → rejected by the validating policy, no namespace created.
- **Update** namespace labels/annotations → generator reconciles quota
  tier if `platform.gophersys/quota-tier` changed.
- **Delete** namespace → `platform/core/policy/namespace-delete-protection`
  validates. Generator removes any lingering non-namespaced resources
  it owned (nothing today; hook reserved for future cluster-scoped refs).

## Observability

Every provisioning action emits a `NamespaceProvisioned` event (Kyverno
generator event) scraped by the observability stack. Grafana "platform
compliance" dashboard shows:

- Count of namespaces per project per env.
- Namespaces missing generated resources (should always be 0).
- Quota utilization per `<project>-<env>` (heatmap).
- Rejected namespace creation attempts (by reason).

## Dependencies

- `platform/core/policy/` — the Kyverno install itself + the companion
  validating policies (`namespace-naming-enforced`,
  `namespace-delete-protection`).
- `platform/core/network-policies/` — baseline NetworkPolicy templates
  referenced by the generator.
- Cluster's `identity.yaml:projects_hosted` — source of truth for which
  projects are valid on this cluster.

## Status

STUB. README only. The Kyverno generator policies land together with
the `platform/core/policy/` rollout, since they share the Kyverno
install.
