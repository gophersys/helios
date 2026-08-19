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

The pattern is INTENDED to enforce the **project taxonomy by construction**: a
namespace would be created only for a project that the cluster lists explicitly
in `projects_hosted:`, so a typo like "marketting-prod" and a leak across tenants
are both rejected. **None of that is enforced today** — this component is a stub,
and no admission policy checks a namespace name. See Status.

## Default implementation — UNDECIDED

The original design was **Kyverno `generate` policies**. Kyverno was removed on
2026-08-09 and is not coming back, so that mechanism is gone and this component
has no implementation at all.

**There is no in-tree replacement for the generate half.** `platform/core/policy/`
holds `ValidatingAdmissionPolicy` objects, and a VAP can only accept or refuse a
request — it cannot create another object. `MutatingAdmissionPolicy` is not served
on this cluster (k3s 1.35 ships it beta and off), and even when it lands it
mutates the object under admission; it does not generate siblings. So the honest
shapes are: (a) keep writing the per-namespace manifests in git, which is what
`apps/*/00-namespace.yaml` does today, or (b) write a small controller. Neither is
chosen.

What a provisioned `<project>-<env>` namespace is SUPPOSED to receive, whatever
mechanism eventually does it:

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

Nothing rejects a name outside these patterns today, and nothing is scheduled to.
The companion policy `namespace-naming-enforced` was part of the Kyverno design
and died with it. `platform/core/policy/` exists again, but it holds exactly 2
policies and both guard **deletion**; neither looks at a name. Writing a
name-checking VAP is possible and unbuilt. See
`.claude/rules/50-cluster-architecture.md` §4.

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
values. There is no `resources-required` admission policy — that named a Kyverno
policy that never existed. Required resources are `enforced-at-render` by
`charts/<archetype>/values.schema.json`. The LimitRange would be the protection
for anyone who forgets, once this component exists.

## Lifecycle

- **Create** a namespace that matches `<project>-<env>` on a cluster that lists
  `<project>` in `projects_hosted:` → the generator starts asynchronously, and
  the baseline resources appear within seconds.
- **Create** a namespace that matches the pattern, but with a `<project>` that is
  not in the cluster's list → **nothing rejects it today.** The design says a
  validating policy would.  Unbuilt.
- **Update** the labels or annotations of a namespace → the generator reconciles
  the quota tier if `platform.gophersys/quota-tier` changed.
- **Delete** a namespace → this one IS enforced, and by a different artifact than
  the name above: `platform/core/policy/`'s `namespace-delete-guard` refuses the
  request when the namespace carries `platform.gophersys/protected=true`, unless
  it is annotated `platform.gophersys/allow-delete`. That guard is live and needs
  nothing from this component.

## Observability

**None of this exists.** It describes what the dashboard would show once a
mechanism emits a `NamespaceProvisioned` event; the original design took that
event from the Kyverno generator, which is gone. Kept as the requirement, not as a
description of anything running:

- the count of namespaces per project and per env;
- the namespaces that are missing a generated resource. This count should always
  be 0.
- the quota use per `<project>-<env>`, as a heatmap;
- the rejected attempts to create a namespace, by reason.

## Dependencies

- `platform/core/policy/` — **not a dependency any more.** It installs nothing
  and holds 2 deletion guards, one of which (`namespace-delete-guard`) already
  covers the Delete lifecycle above on its own. A future
  `namespace-naming-enforced` VAP would live there.
- `platform/core/network-policies/` — the baseline NetworkPolicy templates that
  the generator references.
- `identity.yaml:projects_hosted` of the cluster — the source of truth for which
  projects are valid on that cluster.

## Status

**STUB, and now without a chosen mechanism.** This README is the only content. The
generator half lost its engine when Kyverno was removed, and no in-tree object can
replace it (see Default implementation). Read every requirement above as a
specification, never as a description of the running cluster: today each namespace
is written by hand in `apps/*/00-namespace.yaml`.
