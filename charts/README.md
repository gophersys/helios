# charts

Opinionated Helm archetypes that encode the platform's conventions so every
app ships with enterprise-grade defaults by construction: PodSecurity
`restricted`, default-deny NetworkPolicy, ExternalSecret integration for
Bitwarden, ServiceMonitor for Prometheus, RED-metrics + OTLP traces
plumbing, HPA, PodDisruptionBudget, and a resource profile appropriate to
the app's shape.

An app adopts an archetype by depending on it (`Chart.yaml`) or by copying
it as a starting point at scaffold time. Either way, the archetype's
`values.schema.json` is the contract; Helm rejects values that don't
conform.

## Archetype catalog

Pick the archetype that matches the **shape** of the workload, not what it
does. A data-ingestion service could be `worker` (queue consumer), `job`
(one-shot backfill), or `stateless-app` (HTTP endpoint) depending on its
shape.

| Archetype        | Use when the app…                                  | Runs as             | Typical node role |
|------------------|----------------------------------------------------|---------------------|-------------------|
| `stateless-app`  | Has no persistent local state; replicas fungible   | `Deployment`        | `apps`            |
| `stateful-app`   | Needs stable identity + per-replica PersistentVolume | `StatefulSet`     | `data`            |
| `worker`         | Consumes a queue/stream; no inbound HTTP           | `Deployment` no Svc | `apps` or `batch` |
| `cronjob`        | Runs on a schedule                                 | `CronJob`           | `apps` or `batch` |
| `job`            | Runs once to completion (migrations, one-offs)     | `Job`               | `apps` or `batch` |
| `ingress-app`    | `stateless-app` + opinionated public ingress       | `Deployment`        | `apps`            |

Future (reserved, not yet stubbed): `ml-inference` (GPU), `static-site`
(CDN-cached), `pipeline` (multi-stage DAG, likely via Argo Workflows).

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

## Common chart skeleton

Every archetype has the same shape so apps migrate between them cheaply:

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

`charts/_common/` is a Helm **library chart** (not installable on its own).
It centralizes the template helpers that every archetype reuses:

- `common.labels`, `common.selectorLabels`, `common.annotations`
- `common.podSecurityContext`, `common.containerSecurityContext` (restricted PSS)
- `common.externalSecret` — emits an ExternalSecret per `values.secrets[]` entry
- `common.networkPolicy.baseline` — deny-all + DNS + same-namespace + metrics-scrape
- `common.serviceMonitor` — emits `ServiceMonitor` from `values.observability.metrics`
- `common.slo.recordingRules` — emits Prometheus recording rules from `values.slo`
- `common.pdb` — `PodDisruptionBudget` with archetype-aware defaults
- `common.resources.validated` — enforces requests+limits present

Every archetype `Chart.yaml` includes:

```yaml
dependencies:
  - name: _common
    version: 0.1.0
    repository: file://../_common
```

## Contract integrations

Apps don't write Prometheus/ExternalSecret/NetworkPolicy manifests by hand.
The archetype emits them from declarative values, fulfilling the contracts
in `infrastructure/contracts/`:

| Contract           | Populated from                                | Emits                                           |
|--------------------|-----------------------------------------------|-------------------------------------------------|
| `observability.md` | `values.observability.{logs,metrics,traces}`  | `ServiceMonitor`, pod-log scrape labels, OTLP env vars |
| `secrets.md`       | `values.secrets[]` (each is a BW item ref)    | `ExternalSecret` per item; env-from `Secret`    |
| `ingress.md`       | `values.ingress.{enabled,host,tls}`           | `Ingress` + cert-manager annotation             |
| `databases.md`     | `values.database.{kind,name}`                 | `Database` CR (cnpg) or `Cache` CR + env refs   |
| `identity.md`      | `values.sso.enabled`                          | Ingress middleware annotations                  |
| `messaging.md`     | `values.nats.enabled`                         | `NatsAccount` CR + env refs to emitted creds    |

## Enterprise defaults, by construction

Every chart bakes in:

- **Security.** Non-root, read-only root filesystem, dropped capabilities,
  seccomp profile `RuntimeDefault`. `restricted` PodSecurityStandard is
  admission-enforced at the namespace level.
- **Isolation.** Default-deny NetworkPolicy baseline; egress to DNS +
  same-namespace + metrics scrape only. App-specific allows are values.
- **Reliability.** RollingUpdate strategy (`maxSurge: 1, maxUnavailable: 0`)
  by default; `minReadySeconds: 10`; startup + readiness + liveness probes
  required by values.schema.json; PodDisruptionBudget generated from
  archetype defaults.
- **Cost.** `resources.requests` + `resources.limits` are REQUIRED by
  schema — no "unlimited" pods on shared clusters. Cluster-level
  `ResourceQuota` enforces per-namespace caps.
- **SLO.** Every archetype emits Prometheus recording rules from
  `values.slo` so alerts and dashboards share one definition.
- **Observability.** `ServiceMonitor` auto-emitted when metrics.enabled;
  structured JSON logs expected on stdout; OTLP endpoint injected from
  cluster-level env.
- **Node placement.** `nodeSelector` + `tolerations` populated from
  `values.nodeRole`; prevents accidental cross-role scheduling.

See `charts/CONVENTIONS.md` for authoring rules; per-archetype READMEs
for the archetype-specific knobs.

## Status

Every archetype is a **skeleton** — `Chart.yaml`, `values.yaml`,
`values.schema.json`, and `README.md` are the contract, committed today.
Template files under `templates/` are empty stubs with inline comments
describing what they'll emit once the first real app consumes the
archetype.
