# platform/services/observability

Logs, metrics, traces, dashboards.

## Default implementation

Four Helm releases (one per signal) wired to a single Grafana:

- **Logs** — Loki + Grafana Alloy (log collector on each node).
- **Metrics** — kube-prometheus-stack (Prometheus + kube-state-metrics +
  node-exporter + Alertmanager).
- **Traces** — Tempo (OTLP ingest).
- **UI** — Grafana with all three wired as datasources on install.

## Fulfills
- `contracts/observability.md` — how apps emit logs/metrics/traces and
  what labels they must carry.

## Dependencies
- `platform/core/storage/` — Loki + Prometheus + Tempo all need PV.
- `platform/core/secrets-operator/` — Alertmanager webhook tokens pulled
  from Bitwarden.
- `platform/core/ingress/` + `platform/core/cert-manager/` — Grafana UI
  behind TLS.

## Status

STUB.

## TODO (when populating)
- Consider splitting into `observability-logs/`, `observability-metrics/`,
  `observability-traces/` as separate Nx projects for independent upgrades.
- Pin chart versions.
- Per-cluster retention and storage class in overlays.
- Alertmanager routing — tailnet-local webhook initially, real channels later.
- ServiceMonitor/PodMonitor labels the chart archetypes emit — document in
  `contracts/observability.md`.
