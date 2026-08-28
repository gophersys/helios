# platform/services/admin-dashboard

Single pane of glass across the fleet. The "one URL you open when something
looks off" — surfaces cluster health, app deployments, secrets status,
recent alerts, cost.

## Default implementation

Candidates (TBD when first populated):
- **Headlamp** — lightweight, plugin-friendly, self-hosted.
- **Rancher UI** — heavier, but great for multi-cluster.
- A custom dashboard that aggregates from:
  - Grafana (observability)
  - Argo CD / Flux (GitOps state)
  - cert-manager (cert expiry)
  - Velero (backup status)
  - OpenCost (cost)

Leaning toward **Headlamp + custom overview page** for fleet-of-one UX.

## Fulfills
- No app-facing contract — operator surface only.

## Dependencies
- `platform/core/ingress/` + `cert-manager/` — UI behind TLS.
- `platform/services/identity-sso/` (future) — UI gated by SSO.

## Status

STUB. Populate once the first cluster has the full `core/` + `services/`
stack running and there's actually a reason to want a unified view.
