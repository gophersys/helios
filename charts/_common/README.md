# _common

Helm **library chart** — provides template helpers reused by every
archetype under `charts/`. Not installable on its own.

## Why a library chart

Every archetype (`stateless-app`, `stateful-app`, `worker`, etc.) needs
the same canonical labels, the same security context, the same
ExternalSecret emission pattern, and the same baseline NetworkPolicy. A
library chart is the Helm-native way to share templates without
copy-paste drift.

## Helpers

### `common.labels`
Canonical labels applied to every rendered object. See
`charts/CONVENTIONS.md` §2 for the full list. The composite identifier
`<project>-<app.name>` is `app.kubernetes.io/name`. Consume like:

```yaml
metadata:
  labels:
    {{- include "common.labels" . | nindent 4 }}
```

### `common.selectorLabels`
Subset of `common.labels` suitable for Deployment/StatefulSet/Service
selectors (immutable, no version).

### `common.fullname`
Returns `<project>-<app.name>` — the canonical identifier for the app
(e.g. `codectl-api`). Use as the default Helm release name and as the
base for all rendered resource names (Deployment, Service, PDB, etc.).

### `common.namespace`
Returns `<project>-<env>` — the expected namespace for this app
(e.g. `codectl-prod`). Templates may optionally render a hard-fail
check that `.Release.Namespace` matches this; the platform's
`namespace-naming-enforced` policy enforces it cluster-wide anyway.

### `common.podSecurityContext` / `common.containerSecurityContext`
Emit the restricted PSS security contexts from
`charts/CONVENTIONS.md` §3. Values can override via
`values.securityContext.{pod,container}` but the archetype's
`values.schema.json` rejects anything weaker than restricted.

### `common.externalSecret`
Invoked per entry in `values.secrets[]`. Emits one `ExternalSecret`
linking a Bitwarden item to a Kubernetes Secret and wires the pod's
`envFrom` (mode=env) or `volumeMounts` (mode=file).

### `common.networkPolicy.baseline`
Emits the four baseline NetworkPolicy resources per
`charts/CONVENTIONS.md` §6: deny-all, allow-dns-egress,
allow-same-namespace, allow-metrics-scrape. Extension
NetworkPolicy resources (from `values.networkPolicy.allow*`) are emitted
alongside.

### `common.serviceMonitor`
Emits a `ServiceMonitor` (Prometheus Operator CRD) from
`values.observability.metrics` shape.

### `common.slo.recordingRules`
Emits a `PrometheusRule` with availability + latency recording rules
from `values.slo`. Consumed by `platform/services/observability/`
dashboards.

### `common.pdb`
Emits a `PodDisruptionBudget` with archetype-aware defaults. Invoked
by long-running archetypes.

## Versioning

Library chart follows its own semver. Bumping `_common` is a breaking
change for every archetype; do so only with coordinated version bumps
across all consumers.

Pinned in each archetype's `Chart.yaml`:

```yaml
dependencies:
  - name: _common
    version: 0.1.0
    repository: file://../_common
```

## Status

Helpers are **stubbed** today — `templates/_helpers.tpl` contains the
function signatures with `TODO:` bodies. Populated as the first archetype
is implemented end-to-end.
