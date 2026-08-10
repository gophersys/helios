# charts — authoring conventions

Every archetype under `charts/` follows these rules. If you break one of them,
the archetype does not move between clusters, or it does not work with the
enforcement in `platform/`.

## 1. Schema first

Every archetype MUST ship `values.schema.json`, and Helm validates it at
`helm install` (Helm 3 validates automatically when a schema is present). The
schema:

- declares `additionalProperties: false` at every object level, so there are no
  hidden values;
- marks `project`, `env`, `app.name`, `image.repository`, `image.tag`,
  `resources.requests` and `resources.limits` as **required**. Helm rejects
  values without them at install time.
- validates `project` as `^[a-z][a-z0-9-]{1,20}$`, and `env` as the enum
  `prod | staging | dev | lab`;
- limits the string lengths (`maxLength`) and the array sizes (`maxItems`) to
  defensive values;
- includes a `description` on every property. The schema IS the reference
  documentation, and `README.md` gives the summary.

The schema fragments that several archetypes share live in
`charts/_common/schema/`. Each archetype schema refers to them with `$ref` and a
relative path.

## 2. The labels are mandatory and canonical

Every rendered object MUST carry the label set that `common.labels` in the
`_common` library chart emits. There is no exception.

The canonical labels, applied to every object:

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

The app lands in the namespace **`<project>-<env>`**. All the apps of a project
for a given env share one namespace. For example, `codectl-prod` holds both
`codectl-api` and `codectl-dashboard`. The release name convention is
`<project>-<app.name>`, for example
`helm install codectl-api ./stateless-app -n codectl-prod`.

`platform/core/policy/` enforces the labels: admission rejects an object that
lacks a canonical label. The composite `<project>-<app>` guarantees that
`app.kubernetes.io/name` is unique across the cluster.

## 3. The security context is non-negotiable

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

An app that must write to the root filesystem declares a `volumeMounts.tmpfs:`
entry in its values, and the archetype emits an `emptyDir{medium: Memory}`
volume. Kyverno and the schema both reject
`securityContext.privileged: true`.

## 4. Resource requests and limits are required

The schema enforces `resources.requests.cpu`, `resources.requests.memory`,
`resources.limits.cpu` and `resources.limits.memory` on every container,
including every sidecar.

The memory limit MUST equal the memory request, so that memory is not burstable
and an OOM is predictable. The CPU limit MAY be higher than the CPU request,
because burstable CPU is acceptable.

The defaults for each archetype are in that archetype's `values.yaml`.

## 5. Probes are required

The schema requires `startupProbe`, `readinessProbe` and `livenessProbe` for a
long-running workload: stateless-app, stateful-app, worker and ingress-app. The
`values.yaml` of the archetype supplies sensible defaults, keyed off the shape of
`values.app.probe.{http,tcp,exec}`.

A job and a cronjob have no probes, because they run to completion.

## 6. A NetworkPolicy is emitted by default

`templates/networkpolicy.yaml` always renders. The baseline (deny all, plus DNS,
plus the same namespace, plus the metrics scrape) comes from
`common.networkPolicy.baseline`. Add more allowances with
`values.networkPolicy.allowIngressFrom[]` and `allowEgressTo[]`.

An app cannot opt out. If traffic is blocked, add the rule to the values. The
platform observability logs a policy violation loudly.

## 7. Secrets come through ESO only

The policy rejects a direct `Secret` reference in an env var. An app lists its
Bitwarden items in `values.secrets[]`. The archetype emits one `ExternalSecret`
per entry and wires the resulting Kubernetes Secret into `envFrom` or
`volumeMounts`.

Schema:

```yaml
secrets:
  - key: DATABASE_PASSWORD        # env var name / file name
    bwItem: codectl-db            # Bitwarden item (<project>-<purpose>)
    bwProperty: password          # defaults to "password"
    mode: env                      # env | file (file mounts under /var/run/secrets/<key>)
    optional: false                # if true, missing BW item is not fatal
```

The Bitwarden item naming convention:
- `<project>-<purpose>` — an item for the whole project, shared by the apps of
  that project, for example `codectl-db` and `fintel-openai`.
- `<project>-<app>-<purpose>` — an item for one app, for example
  `codectl-api-internal-token` and `fintel-grader-nats-creds`.

## 8. Observability is emitted, not opt-in

Every long-running archetype does all of the following:

- It emits a `ServiceMonitor` (or a `PodMonitor`) when
  `observability.metrics.enabled` is true. The default is true.
- It sets the pod annotation `observability.gophersys/logs=scrape` for log
  collection.
- It injects the env vars `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` and
  `OTEL_RESOURCE_ATTRIBUTES`. An app that emits no traces is not harmed by the
  initialization of the SDK.

A job and a cronjob do the same, for the duration of their run.

## 9. SLOs are declared, and the rules are emitted

If an archetype supports SLOs, the chart emits Prometheus recording rules from
`values.slo`:

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

The recording rules produce the time series `slo:availability:<app>` and
`slo:latency:p95:<app>`. The Grafana dashboards consume them —
`platform/services/observability/` provisions those dashboards automatically —
and so do the `Alertmanager` routes.

## 10. Hooks for progressive delivery

Today the archetypes emit a `Deployment` or a `StatefulSet` directly. When
`platform/services/progressive-delivery/` lands (Flagger or Argo Rollouts), an
archetype will emit a `Canary` or a `Rollout` resource instead, when
`values.rollout.strategy` is `canary`. No app will need a change.

## 11. PDBs are generated, not opt-in

Every long-running archetype emits a `PodDisruptionBudget`:

- 1 replica: `minAvailable: 1`. This blocks a voluntary eviction, so an operator
  must drain the node explicitly, with the override annotation from
  `platform/core/policy/`.
- 2 or more replicas: `maxUnavailable: 25%`, rounded down.

## 12. One ServiceAccount per release, with minimal RBAC

The archetype always creates a dedicated `ServiceAccount`. The policy bans use of
the ambient `default` SA. RBAC is opt-in through `values.rbac.rules[]`, and it is
empty by default.

## 13. The rollout strategy is encoded

These are the defaults for each archetype, in its `values.yaml`. You can override
all of them:

- `stateless-app`, `ingress-app` and `worker`: `strategy: RollingUpdate` with
  `maxSurge: 1, maxUnavailable: 0`.
- `stateful-app`: `strategy: RollingUpdate` with `partition: 0` and
  `podManagementPolicy: OrderedReady`.
- `job` and `cronjob`: not applicable.

## 14. Chart testing

Every archetype has golden-file tests under `tests/`. `helm-unittest` runs on
every CI build:

- `basic.yaml` — the minimal valid values, and the expected rendered Deployment.
- `secrets.yaml` — `secrets[]` populated, and the expected ExternalSecrets.
- `slo.yaml` — `slo` populated, and the expected recording rules.
- `networkpolicy.yaml` — `allowIngressFrom` populated, and the expected policy.

A change to the rendered output with no matching change to the values fails CI.

## 15. Version pinning

`Chart.yaml:version` follows semver. A minor bump may change the default values,
and it stays backward-compatible. A major bump needs a migration note in the
README of the archetype. An app pins `dependencies[].version` to one specific
chart version.

The shared `_common` library has its own semver. An archetype pins against
`_common` in the same way that an app pins against an archetype.
