---
contract: observability
version: 0.1.0-draft
fulfilled_by: platform/services/observability/
---

# observability

## Abstract

The platform collects the **logs**, the **metrics** and the **traces** of every
app automatically. An app does not run its own Prometheus or Loki. It emits data
in a standard format (OTLP, OpenMetrics or structured logs), and the platform
routes it, stores it and shows it in Grafana.

## Interface (TBD)

### Logs
- Write structured JSON to stdout and stderr. Required fields (TBD): `ts`,
  `level`, `msg`, `service`, `env`, and `trace_id` (optional).
- The platform's log collector scrapes the container logs. The app runs no
  daemon.

### Metrics
- Expose a Prometheus-compatible `/metrics` endpoint on a port (TBD; the default
  is 9090).
- Declare a `ServiceMonitor`, or annotate the Service with the label
  `app.platform/scrape=true`.
- These label keys are reserved: `app`, `component`, `env` and `tenant`. The app
  supplies them, and the platform adds `cluster` and `namespace`.

### Traces
- Emit OTLP over HTTP or gRPC to the endpoint that the platform injects as
  `$OTEL_EXPORTER_OTLP_ENDPOINT`.
- Resource attributes: `service.name`, `service.version` and
  `deployment.environment`.

## Guarantees (TBD)

- Retention defaults: 7 days for logs, 15 days for metrics and 3 days for traces.
  A cluster can override each value.
- Grafana access at `https://grafana.<cluster-domain>/`, with SSO once
  `identity-sso` lands, and with basic auth before that.

## Caveats (TBD)

- A label with high cardinality can break the storage, so the platform enforces a
  cap.
- The platform uses tail sampling for traces, so it does not keep every span.

## Example (TBD)

A minimal working snippet, once the contract is final.
