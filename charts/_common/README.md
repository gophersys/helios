# _common

A Helm **library chart**. It supplies the template helpers that every archetype
under `charts/` reuses. You cannot install it on its own.

## Why a library chart

Every archetype — `stateless-app`, `stateful-app`, `worker` and the others —
needs the same canonical labels, the same security context, the same pattern to
emit an ExternalSecret, and the same baseline NetworkPolicy. A library chart is
the method that Helm supplies to share a template. It also stops the copies from
drifting apart.

## Helpers

### `common.labels`
The canonical labels, applied to every rendered object. `charts/CONVENTIONS.md`
§2 holds the full list. The composite identifier `<project>-<app.name>` becomes
`app.kubernetes.io/name`. Use it as follows:

```yaml
metadata:
  labels:
    {{- include "common.labels" . | nindent 4 }}
```

### `common.selectorLabels`
A subset of `common.labels` for the selectors of a Deployment, a StatefulSet or a
Service. The labels are immutable and carry no version.

### `common.fullname`
Returns `<project>-<app.name>`, the canonical identifier of the app, for example
`codectl-api`. Use it as the default Helm release name, and as the base of every
rendered resource name: the Deployment, the Service, the PDB and the others.

### `common.namespace`
Returns `<project>-<env>`, the expected namespace of this app, for example
`codectl-prod`. A template may render an optional check that fails hard if
`.Release.Namespace` does not match. The `namespace-naming-enforced` policy of
the platform enforces the same rule across the cluster in any case.

### `common.podSecurityContext` / `common.containerSecurityContext`
They emit the restricted PSS security contexts from `charts/CONVENTIONS.md` §3.
The values can override them through `values.securityContext.{pod,container}`,
but the `values.schema.json` of the archetype rejects anything weaker than
restricted.

### `common.externalSecret`
Called once for each entry in `values.secrets[]`. It emits 1 `ExternalSecret`
that links a Bitwarden item to a Kubernetes Secret, and it wires the pod's
`envFrom` (mode=env) or `volumeMounts` (mode=file).

### `common.networkPolicy.baseline`
Emits the 4 baseline NetworkPolicy resources from `charts/CONVENTIONS.md` §6:
deny-all, allow-dns-egress, allow-same-namespace and allow-metrics-scrape. It
also emits the extra NetworkPolicy resources from `values.networkPolicy.allow*`.

### `common.serviceMonitor`
Emits a `ServiceMonitor` (a Prometheus Operator CRD) from the shape of
`values.observability.metrics`.

### `common.slo.recordingRules`
Emits a `PrometheusRule` with the availability and latency recording rules from
`values.slo`. The dashboards of `platform/services/observability/` consume them.

### `common.pdb`
Emits a `PodDisruptionBudget` with defaults that depend on the archetype. A
long-running archetype calls it.

## Versioning

The library chart has its own semver. A bump of `_common` is a breaking change
for every archetype. Do it only with a coordinated version bump across every
consumer.

Pinned in each archetype's `Chart.yaml`:

```yaml
dependencies:
  - name: _common
    version: 0.1.0
    repository: file://../_common
```

## Status

The helpers are **stubs** today. `templates/_helpers.tpl` holds the function
signatures with `TODO:` bodies. They are populated as the first archetype is
implemented end to end.
