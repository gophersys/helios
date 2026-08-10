# platform/core/namespace-provisioner

An automated namespace lifecycle. When somebody creates a namespace that matches
`<project>-<env>` or `platform-<component>`, the provisioner applies the standard
baseline: the labels, the NetworkPolicies, the ResourceQuota, the LimitRange and
the ServiceAccount conventions. When somebody deletes a namespace, the
delete-protection policy gates the request.

## Why

A namespace without a NetworkPolicy accepts all traffic. A namespace without a
ResourceQuota can starve the cluster. A namespace without a LimitRange lets a pod
declare any resources it wants. Every new namespace must get all 3, and a manual
application of them causes errors.

The pattern also enforces the **project taxonomy by construction**. A namespace
is created only for a project that the cluster lists explicitly in
`projects_hosted:`. Admission rejects a typo, for example "marketting-prod", and
it rejects a leak across tenants.

## Default implementation

**Kyverno `generate` policies.** The mechanism already exists; see
`platform/core/policy/`. The namespace-provisioner is a set of generate policies,
and they live here rather than in the policy catalog, because they cover the
**side effects of a creation** rather than admission control.

The policies watch for a new namespace that matches the naming pattern, and they
generate the required resources into that namespace:

1. `NetworkPolicy/default-deny-ingress`
2. `NetworkPolicy/default-deny-egress`
3. `NetworkPolicy/allow-dns`
4. `NetworkPolicy/allow-same-namespace`. The apps in `codectl-prod` talk to each
   other freely. The apps in `fintel-prod` cannot reach `codectl-prod` without
   explicit egress rules.
5. `NetworkPolicy/allow-metrics-scrape`, for platform-monitoring to the app pods
   on the metrics port.
6. `ResourceQuota/baseline` — CPU, memory, pod count and PVC count. See the tier
   table below.
7. `LimitRange/baseline` — the default requests and limits per container.
8. These labels on the namespace itself:
   - `pod-security.kubernetes.io/enforce=restricted`
   - `pod-security.kubernetes.io/audit=restricted`
   - `pod-security.kubernetes.io/warn=restricted`
   - `platform.gophersys/project=<project>`, parsed from the namespace name
   - `platform.gophersys/env=<env>`, parsed from the namespace name
   - `platform.gophersys/tenant=<derived — gophersys today>`

## The naming conventions that are enforced

| Pattern                  | Example                                     | What's checked                                                          |
|--------------------------|---------------------------------------------|-------------------------------------------------------------------------|
| `<project>-<env>`        | `codectl-prod`, `fintel-staging`            | `<project>` listed in cluster's `projects_hosted:`; `<env>` ∈ `{prod, staging, dev, lab}` |
| `platform-<component>`   | `platform-ingress`, `platform-monitoring`   | `<component>` matches a known platform component                        |
| `kube-*`                 | `kube-system`                               | Skipped by the generator (Kubernetes reserved)                          |

The companion validating policy `namespace-naming-enforced` rejects a name
outside these patterns. See `platform/core/policy/CATALOG.md`.

## How the project registry works

The `identity.yaml` of each cluster declares which projects that cluster hosts:

```yaml
# clusters/instances/prod/identity.yaml
projects_hosted:
  - codectl
  - fintel
  - finances
```

The generator reads this list and permits namespace creation for those projects
only. The list arrives through the ConfigMap `platform-registry` in the
`platform-secrets` namespace, which is synced from the repo at bootstrap time. An
attempt to create `marketing-prod` on a cluster that does not list `marketing`
fails with a clear error.

To add a new project to a cluster: append it to `projects_hosted:` in the cluster
identity, commit, and apply the namespace-provisioner again so that the ConfigMap
refreshes.

## Quota tiers

The baseline ResourceQuota is a starting point, not a ceiling. The quota applies
per project-env, so `codectl-prod` has ONE quota, and api, dashboard and every
other codectl-prod app share it.

A project with a larger footprint declares a quota override in the annotations of
the namespace, and the generator reads it:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: codectl-prod
  annotations:
    platform.gophersys/quota-tier: medium          # small | medium | large | custom
    platform.gophersys/quota-reason: "dashboard handles SSE connections for all users"
```

Tier to resources:
- `small`:  4 CPU / 8 GiB / 20 pods / 10 PVC — the default for staging, dev and
  lab.
- `medium`: 8 CPU / 16 GiB / 40 pods / 20 PVC — the default for prod.
- `large`:  16 CPU / 32 GiB / 80 pods / 40 PVC — an explicit opt-in.
- `custom`: you must create a `ResourceQuota` object by hand in the namespace
  BEFORE the generator runs. The generator stops when it detects one.

An escalation from `small` to `medium` to `large` needs a platform PR that
updates the `namespace_provisioning.quota_overrides:` map of the cluster.

## The LimitRange baseline

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

An app overrides these values with an explicit `resources` block in its chart
values. See `platform/core/policy/` → `resources-required`. The LimitRange is the
protection for anyone who forgets.

## Lifecycle

- **Create** a namespace that matches `<project>-<env>` on a cluster that lists
  `<project>` in `projects_hosted:` → the generator starts asynchronously, and
  the baseline resources appear within seconds.
- **Create** a namespace that matches the pattern, but with a `<project>` that is
  not in the cluster's list → the validating policy rejects it, and no namespace
  is created.
- **Update** the labels or annotations of a namespace → the generator reconciles
  the quota tier if `platform.gophersys/quota-tier` changed.
- **Delete** a namespace → `platform/core/policy/namespace-delete-protection`
  validates the request. The generator removes any resource that it owned and
  that is not namespaced. There is none today; the hook is reserved for future
  cluster-scoped references.

## Observability

Every provisioning action emits a `NamespaceProvisioned` event, which is a
Kyverno generator event, and the observability stack scrapes it. The Grafana
"platform compliance" dashboard shows:

- the count of namespaces per project and per env;
- the namespaces that are missing a generated resource. This count must always be
  0.
- the quota use per `<project>-<env>`, as a heatmap;
- the rejected attempts to create a namespace, by reason.

## Dependencies

- `platform/core/policy/` — the Kyverno install itself, plus the companion
  validating policies `namespace-naming-enforced` and
  `namespace-delete-protection`.
- `platform/core/network-policies/` — the baseline NetworkPolicy templates that
  the generator references.
- `identity.yaml:projects_hosted` of the cluster — the source of truth for which
  projects are valid on that cluster.

## Status

STUB. This README is the only content. The Kyverno generator policies land with
the rollout of `platform/core/policy/`, because they share the Kyverno install.
