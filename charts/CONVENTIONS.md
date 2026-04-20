# charts — authoring conventions

Rules every archetype under `charts/` follows. Breaking any of these makes
the archetype non-portable across clusters or incompatible with
`platform/` enforcement.

## 1. Schema-first

Every archetype MUST ship `values.schema.json` validated at `helm install`
(Helm 3 validates automatically when schema is present). The schema:

- Declares `additionalProperties: false` at every object level. No hidden
  values.
- Marks `project`, `env`, `app.name`, `image.repository`, `image.tag`,
  `resources.requests`, `resources.limits` as **required**. Values without
  them are rejected at install time.
- `project` validated as `^[a-z][a-z0-9-]{1,20}$`, `env` as enum
  `prod | staging | dev | lab`.
- Caps string lengths (`maxLength`) and array sizes (`maxItems`) to
  defensive limits.
- Includes `description` on every property. The schema IS the reference
  docs; `README.md` summarizes.

Schema fragments shared across archetypes live in
`charts/_common/schema/` and are `$ref`'d (via relative path) from each
archetype's schema.

## 2. Labels are mandatory and canonical

Every rendered object MUST carry the label set emitted by
`common.labels` in the `_common` library chart. No exceptions.

Canonical labels (applied to every object):

```yaml
app.kubernetes.io/name:        <values.project>-<values.app.name>   # e.g., codectl-api
app.kubernetes.io/instance:    <release>                             # usually == app.kubernetes.io/name
app.kubernetes.io/version:     <values.image.tag>
app.kubernetes.io/component:   <archetype>                           # stateless-app | worker | etc.
app.kubernetes.io/part-of:     <values.project>                      # codectl
app.kubernetes.io/managed-by:  Helm

platform.gophersys/project:    <values.project>                      # codectl | fintel | finances | ...
platform.gophersys/app:        <values.app.name>                     # api | dashboard | grader
platform.gophersys/env:        <values.env>                          # prod | staging | dev | lab
platform.gophersys/tenant:     <values.tenant | default "gophersys">
platform.gophersys/archetype:  <archetype>
platform.gophersys/node-role:  <values.nodeRole>                     # apps | data | devops | build | batch
platform.gophersys/data-class: <values.dataClassification>           # public | internal | confidential | pii
platform.gophersys/slo-tier:   <values.slo.tier>                     # critical | high | standard | best-effort
```

The namespace the app lands in is **`<project>-<env>`** — all apps of a
project for a given env share one namespace (e.g., `codectl-prod` holds
both `codectl-api` and `codectl-dashboard`). Release name convention:
`<project>-<app.name>` (e.g., `helm install codectl-api ./stateless-app
-n codectl-prod`).

Labels are enforced by `platform/core/policy/` — objects missing canonical
labels are rejected at admission. `app.kubernetes.io/name` uniqueness
across the cluster is guaranteed by the `<project>-<app>` composite.

## 3. Security context is non-negotiable

Every Pod MUST render with:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001               # overridable, but non-root always
  runAsGroup: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
```

Every container MUST render with:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities: { drop: [ALL] }
```

Apps that need writes to the root filesystem declare a `volumeMounts.tmpfs:`
entry in values; the archetype emits an `emptyDir{medium: Memory}` volume.
Declaring `securityContext.privileged: true` is rejected by Kyverno and by
schema.

## 4. Resource requests + limits required

The schema enforces `resources.requests.cpu/memory` and
`resources.limits.cpu/memory` on every container. Sidecars too.

Memory limits MUST equal requests (no burstable memory — OOMs are
predictable). CPU limits MAY exceed requests (burstable CPU is fine).

Defaults per archetype are in the archetype's `values.yaml`.

## 5. Probes required

`startupProbe`, `readinessProbe`, `livenessProbe` are required by schema
for long-running workloads (stateless-app, stateful-app, worker,
ingress-app). The archetype's `values.yaml` provides reasonable defaults
keyed off `values.app.probe.{http,tcp,exec}` shape.

Jobs and cronjobs have no probes (they run to completion).

## 6. NetworkPolicy emitted by default

`templates/networkpolicy.yaml` always renders. Baseline (deny-all +
DNS + same-ns + metrics scrape) comes from `common.networkPolicy.baseline`.
Additional allows are `values.networkPolicy.allowIngressFrom[]` +
`allowEgressTo[]`.

An app opt-out is NOT supported. If traffic is blocked, add the rule to
values. Policy violations are loudly logged by platform observability.

## 7. Secrets through ESO only

Direct `Secret` references in env are rejected by policy. Apps list
Bitwarden items in `values.secrets[]`; the archetype emits an
`ExternalSecret` per entry and wires the resulting Kubernetes Secret into
`envFrom` / `volumeMounts`.

Schema:

```yaml
secrets:
  - key: DATABASE_PASSWORD        # env var name / file name
    bwItem: codectl-db            # Bitwarden item (<project>-<purpose>)
    bwProperty: password          # defaults to "password"
    mode: env                      # env | file (file mounts under /var/run/secrets/<key>)
    optional: false                # if true, missing BW item is not fatal
```

Bitwarden item naming convention:
- `<project>-<purpose>` — project-wide items shared across the project's
  apps (e.g., `codectl-db`, `fintel-openai`).
- `<project>-<app>-<purpose>` — app-specific items
  (e.g., `codectl-api-internal-token`, `fintel-grader-nats-creds`).

## 8. Observability emitted, not opt-in

Every long-running archetype:

- Emits `ServiceMonitor` (or `PodMonitor`) when `observability.metrics.enabled`
  — default true.
- Sets pod annotations `observability.gophersys/logs=scrape` for log
  collection.
- Injects `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`,
  `OTEL_RESOURCE_ATTRIBUTES` env vars. Apps that don't emit traces still
  benefit from SDK init harmlessness.

Jobs/cronjobs: same, scoped to their run duration.

## 9. SLOs declared, rules emitted

If an archetype supports SLOs, the chart emits Prometheus recording rules
from `values.slo`:

```yaml
slo:
  tier: high                      # critical|high|standard|best-effort
  availability:
    target: 99.9                  # percent
    window: 30d
  latency:
    target_ms: 300                # p95 target
    window: 7d
  errorBudget:
    burnRateFast: 14.4            # 2% budget in 1 hour
    burnRateSlow: 6               # 10% budget in 6 hours
```

Recording rules materialize as `slo:availability:<app>` and
`slo:latency:p95:<app>` time-series, consumed by Grafana dashboards
(auto-provisioned by `platform/services/observability/`) and
`Alertmanager` routes.

## 10. Progressive delivery hooks (future-friendly)

The archetypes emit `Deployment` / `StatefulSet` directly today. When
`platform/services/progressive-delivery/` lands (Flagger or Argo Rollouts),
the archetype will emit a `Canary` / `Rollout` resource instead when
`values.rollout.strategy: canary` — no app changes required.

## 11. PDBs generated, not opt-in

Every long-running archetype emits a `PodDisruptionBudget`:

- 1 replica: `minAvailable: 1` (voluntary evictions blocked; ops must
  drain explicitly via `platform/core/policy/` override annotation).
- 2+ replicas: `maxUnavailable: 25%` (rounded down).

## 12. ServiceAccount per release, minimal RBAC

The archetype always creates a dedicated `ServiceAccount`. Ambient
`default` SA is banned by policy. RBAC is opt-in via
`values.rbac.rules[]`; empty by default.

## 13. Rollout strategy encoded

Defaults per archetype (in `values.yaml`), all overridable:

- `stateless-app`, `ingress-app`, `worker`:
  `strategy: RollingUpdate` with `maxSurge: 1, maxUnavailable: 0`.
- `stateful-app`: `strategy: RollingUpdate` with `partition: 0` and
  `podManagementPolicy: OrderedReady`.
- `job`, `cronjob`: n/a.

## 14. Chart testing

Every archetype has golden-file tests under `tests/`. `helm-unittest` runs
on every CI build:

- `basic.yaml` — minimal valid values, expected rendered Deployment.
- `secrets.yaml` — secrets[] populated; expected ExternalSecrets.
- `slo.yaml` — slo populated; expected recording rules.
- `networkpolicy.yaml` — allowIngressFrom populated; expected policy.

Drift in the rendered output without a corresponding values change fails CI.

## 15. Version pinning

`Chart.yaml:version` follows semver. A minor bump may change default values
(backwards-compatible). A major bump requires a migration note in the
archetype README. Apps pin `dependencies[].version` to a specific chart
version.

The shared `_common` library has its own semver. Archetypes pin against
`_common` the same way apps pin against archetypes.
