# charts

Blessed Helm chart archetypes. An "application" in any consuming monorepo
should never hand-write a Deployment / Service / Ingress — it should
depend on one of these and supply values only.

| Chart              | Shape                                             |
|--------------------|---------------------------------------------------|
| `stateless-app/`   | Deployment + Service + optional Ingress + HPA     |
| `stateful-app/`    | StatefulSet + Service + PVC + optional Ingress    |
| `job/`             | Job (one-shot)                                    |
| `cronjob/`         | CronJob (scheduled)                               |
| `ingress-app/`     | Stateless-app + always-on Ingress + cert-manager  |

All charts consume the cluster's platform services transparently:
- Cert-manager for TLS (via Ingress annotations).
- External Secrets Operator (via `externalSecrets:` values).
- Prometheus ServiceMonitor discovery (via `metrics.enabled` values).

Status: stubs. Each chart's README describes intended values schema; the
actual chart templates land when the first app consumes them.
