# platform/services/cost

Cost visibility and alerting. Surfaces per-namespace / per-app spend so a
runaway workload is caught before the bill arrives.

## Default implementation

**OpenCost** (Helm chart: `opencost/opencost`). Works across clouds with a
consistent labeling model; integrates with our Prometheus for allocation
and Grafana for dashboards.

Also: **KubeCost Community** as an alternative when a richer UI is worth it.

## Fulfills
- No direct app contract. Operator-facing.

## Dependencies
- `platform/services/observability/` — Prometheus for metrics; Grafana for
  dashboards.
- Cloud-provider pricing data — fetched via OpenCost's built-in API with
  fallbacks to the cloud's billing API where wired.

## Status

STUB. Low priority until cloud spend is non-trivial (today: ~$14/mo OCI +
~$4/mo AWS EBS — below visibility threshold).
