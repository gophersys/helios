# charts

Opinionated Helm archetypes that encode the conventions of the platform, so that
every app ships with enterprise-grade defaults by construction. Those defaults
are: PodSecurity `restricted`, a default-deny NetworkPolicy, ExternalSecret
integration with Bitwarden, a ServiceMonitor for Prometheus, the wiring for RED
metrics and OTLP traces, an HPA, a PodDisruptionBudget, and a resource profile
that suits the shape of the app.

An app adopts an archetype in one of 2 ways: it declares a dependency on the
archetype in `Chart.yaml`, or it copies the archetype as a starting point at
scaffold time. In both cases the `values.schema.json` of the archetype is the
contract, and Helm rejects any values that do not conform to it.

## Archetype catalog

Pick the archetype that matches the **shape** of the workload, not what the
workload does. A data-ingestion service could be a `worker` (a queue consumer), a
`job` (a one-shot backfill) or a `stateless-app` (an HTTP endpoint), depending on
its shape.

| Archetype        | Use when the app…                                  | Runs as             | Typical node role |
|------------------|----------------------------------------------------|---------------------|-------------------|
| `stateless-app`  | Has no persistent local state; replicas fungible   | `Deployment`        | `apps`            |
| `stateful-app`   | Needs stable identity + per-replica PersistentVolume | `StatefulSet`     | `data`            |
| `worker`         | Consumes a queue/stream; no inbound HTTP           | `Deployment` no Svc | `apps` or `batch` |
| `cronjob`        | Runs on a schedule                                 | `CronJob`           | `apps` or `batch` |
| `job`            | Runs once to completion (migrations, one-offs)     | `Job`               | `apps` or `batch` |
| `ingress-app`    | `stateless-app` + opinionated public ingress       | `Deployment`        | `apps`            |

Reserved for the future, and not yet stubbed: `ml-inference` (GPU),
`static-site` (cached on a CDN) and `pipeline` (a multi-stage DAG, probably
through Argo Workflows).

## Decision tree

```
Is there inbound HTTP(S) to users?
├─ Yes
│   ├─ Needs persistent identity / PV? → stateful-app
│   ├─ Needs public DNS + automatic TLS? → ingress-app
│   └─ Otherwise → stateless-app
└─ No
    ├─ Runs on a schedule? → cronjob
    ├─ Runs once then exits? → job
    └─ Long-running consumer of a queue/stream? → worker
```

## The common chart skeleton

Every archetype has the same shape, so that an app can move between archetypes at
a low cost:

```
charts/<archetype>/
├── Chart.yaml              # type: application; depends on charts/_common
├── Chart.lock
├── README.md               # archetype rationale + knobs reference
├── values.yaml             # opinionated defaults
├── values.schema.json      # enterprise contract (validated on install)
├── templates/
│   ├── _helpers.tpl        # archetype-specific helpers (thin — most helpers live in _common)
│   ├── <workload>.yaml     # deployment / statefulset / cronjob / job
│   ├── service.yaml        # (where applicable)
│   ├── ingress.yaml        # (where applicable)
│   ├── hpa.yaml            # (where applicable)
│   ├── pdb.yaml            # (where applicable)
│   ├── networkpolicy.yaml
│   ├── externalsecret.yaml # from values.secrets[]
│   ├── servicemonitor.yaml # if values.observability.metrics.enabled
│   ├── serviceaccount.yaml # always — ambient SA is banned by platform policy
│   ├── rbac.yaml           # minimal, opt-in per permission
│   └── NOTES.txt
└── tests/
    └── *.golden.yaml       # rendered snapshots validated by helm unittest
```

## The `_common` library chart

`charts/_common/` is a Helm **library chart**. You cannot install it on its own.
It holds the template helpers that every archetype reuses:

- `common.labels`, `common.selectorLabels`, `common.annotations`
- `common.podSecurityContext`, `common.containerSecurityContext` (restricted PSS)
- `common.externalSecret` — emits an ExternalSecret per `values.secrets[]` entry
- `common.networkPolicy.baseline` — deny-all + DNS + same-namespace + metrics-scrape
- `common.serviceMonitor` — emits `ServiceMonitor` from `values.observability.metrics`
- `common.slo.recordingRules` — emits Prometheus recording rules from `values.slo`
- `common.pdb` — `PodDisruptionBudget` with archetype-aware defaults
- `common.resources.validated` — enforces requests+limits present

The `Chart.yaml` of every archetype includes:

```yaml
dependencies:
  - name: _common
    version: 0.1.0
    repository: file://../_common
```

## Contract integrations

An app does not write a Prometheus, ExternalSecret or NetworkPolicy manifest by
hand. The archetype emits them from declarative values, and it fulfills the
contracts in `infrastructure/contracts/`:

| Contract           | Populated from                                | Emits                                           |
|--------------------|-----------------------------------------------|-------------------------------------------------|
| `observability.md` | `values.observability.{logs,metrics,traces}`  | `ServiceMonitor`, pod-log scrape labels, OTLP env vars |
| `secrets.md`       | `values.secrets[]` (each is a BW item ref)    | `ExternalSecret` per item; env-from `Secret`    |
| `ingress.md`       | `values.ingress.{enabled,host,tls}`           | `Ingress` + cert-manager annotation             |
| `databases.md`     | `values.database.{kind,name}`                 | `Database` CR (cnpg) or `Cache` CR + env refs   |
| `identity.md`      | `values.sso.enabled`                          | Ingress middleware annotations                  |
| `messaging.md`     | `values.nats.enabled`                         | `NatsAccount` CR + env refs to emitted creds    |

## Enterprise defaults, by construction

Every chart includes all of these:

- **Security.** Non-root, a read-only root filesystem, dropped capabilities, and
  the seccomp profile `RuntimeDefault`. Admission enforces the `restricted`
  PodSecurityStandard at namespace level.
- **Isolation.** A default-deny NetworkPolicy baseline, with egress only to DNS,
  to the same namespace and for the metrics scrape. The allowances specific to an
  app are values.
- **Reliability.** The RollingUpdate strategy (`maxSurge: 1, maxUnavailable: 0`)
  by default; `minReadySeconds: 10`; the startup, readiness and liveness probes
  that `values.schema.json` requires; and a PodDisruptionBudget generated from
  the archetype defaults.
- **Cost.** The schema REQUIRES `resources.requests` and `resources.limits`, so
  there is no pod without a limit on a shared cluster. A cluster-level
  `ResourceQuota` enforces the caps per namespace.
- **SLO.** Every archetype emits Prometheus recording rules from `values.slo`, so
  that the alerts and the dashboards share one definition.
- **Observability.** A `ServiceMonitor` is emitted automatically when
  `metrics.enabled` is true. The app is expected to write structured JSON logs to
  stdout.
  The chart injects the OTLP endpoint from the cluster-level env.
- **Node placement.** `nodeSelector` and `tolerations` are populated from
  `values.nodeRole`, which prevents scheduling onto the wrong role by accident.

See `charts/CONVENTIONS.md` for the authoring rules, and the README of each
archetype for the settings specific to that archetype.

## Status

Every archetype is a **skeleton**. `Chart.yaml`, `values.yaml`,
`values.schema.json` and `README.md` are the contract, and they are committed
today. The template files under `templates/` are empty stubs with inline comments
that describe what they will emit once the first real app consumes the archetype.
