---
contract: observability
version: 0.1.0-draft
fulfilled_by: platform/services/observability/
---

# observability

## Abstract

The platform collects **logs**, **metrics**, and **traces** from every app
automatically. Apps don't run their own Prometheus or Loki — they emit in
standard formats (OTLP / OpenMetrics / structured logs) and the platform
routes, stores, and surfaces the data in Grafana.

## Interface (TBD)

### Logs
- Write structured JSON to stdout/stderr. Required fields (TBD):
  - `ts`, `level`, `msg`, `service`, `env`, `trace_id` (optional).
- The platform's log collector scrapes container logs; no app-side daemon.

### Metrics
- Expose Prometheus-compatible `/metrics` on port TBD (default 9090).
- Declare a `ServiceMonitor` (or annotate the Service) with label
  `app.platform/scrape=true`.
- Reserved label keys: `app`, `component`, `env`, `tenant`. Apps supply
  these; the platform adds `cluster` and `namespace`.

### Traces
- Emit OTLP over HTTP/gRPC to endpoint injected as `$OTEL_EXPORTER_OTLP_ENDPOINT`.
- Resource attributes: `service.name`, `service.version`, `deployment.environment`.

## Guarantees (TBD)

- 7-day retention for logs, 15-day for metrics, 3-day for traces (defaults,
  per-cluster overridable).
- Grafana access at `https://grafana.<cluster-domain>/` with SSO (once
  `identity-sso` lands) or basic auth before.

## Caveats (TBD)

- High-cardinality labels can break storage; the platform enforces a cap.
- Tail sampling for traces; not every span persists.

## Example (TBD)

Minimal working snippet once the contract is finalized.
