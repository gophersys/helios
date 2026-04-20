# platform/observability

Logs, metrics, traces. Default stack:

- `loki` + `promtail`/`alloy` — logs.
- `prometheus` + `kube-state-metrics` + `node-exporter` — metrics.
- `tempo` — traces.
- `grafana` — single pane of glass (datasources wired automatically).

Uses the kube-prometheus-stack chart for everything under `metrics`, and
grafana/loki-stack for logs. Tempo is its own chart.

Status: stub. Each component is a separate Helm release; likely split into
`platform/observability-metrics/`, `platform/observability-logs/`,
`platform/observability-traces/` when implemented — one Nx project per
release for clean caching and upgrades.

TODO:
- Pin chart versions.
- Define retention and storage class per cluster.
- Decide where alertmanager routes (likely a tailnet-local webhook for
  now, real email/chat later).
