# eden-observability

A replicable, self-contained observability stack for **any** Kubernetes cluster —
out-of-the-box k8s monitoring **and** an OpenTelemetry endpoint for your apps.

## What it deploys

| Component | Role |
|---|---|
| **Grafana Alloy** — gateway (Deployment) | OTLP receiver (gRPC `:4317` / HTTP `:4318`) → fans out to Prometheus / Loki / Tempo. **This is the endpoint your apps target.** |
| **Grafana Alloy** — logs (DaemonSet) | Tails every pod's logs → Loki |
| **Prometheus** | Scrapes k8s (cAdvisor, kubelet, kube-state-metrics, node-exporter) + accepts remote-write |
| **Loki** | Log store (filesystem or S3) |
| **Tempo** | Trace store (filesystem or S3), HTTP API on **:3200**, OTLP on :4317/:4318 |
| **Grafana** | Dashboards + provisioned datasources (Prometheus/Loki/Tempo). Disable to reuse an existing one. |

Everything OSS. The proprietary part of Grafana Cloud is only the curated dashboards —
this ships open equivalents (kube-prometheus views, Node Exporter Full, Loki logs) via `gnetId`.

## Install

```bash
helm dependency build
kubectl create namespace observability

# Grafana admin secret (the chart reads admin.existingSecret=grafana-admin)
kubectl -n observability create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$(openssl rand -base64 18)"

# Homelab (Longhorn storage, Grafana on a MetalLB LoadBalancer):
helm upgrade --install obs . -f values.yaml -f values-homelab.yaml -n observability

# Cloud (S3-backed Loki/Tempo — see values-cloud.yaml header for the obs-s3 secret + bucket):
helm upgrade --install obs . -f values.yaml -f values-cloud.yaml -n observability
```

Service names are pinned via `fullnameOverride` so the Alloy config + Grafana datasources
use stable in-namespace DNS (`prometheus-server`, `loki:3100`, `tempo:3200/:4317`,
`alloy-gateway:4317/:4318`).

## Send app telemetry (OpenTelemetry)

Point your app's OTLP exporter at the gateway (same namespace):

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy-gateway.observability.svc:4318   # HTTP
# or gRPC:                  http://alloy-gateway.observability.svc:4317
OTEL_SERVICE_NAME=my-app
```

Metrics → Prometheus, logs → Loki, traces → Tempo — all visible in Grafana, cross-linked
(trace→logs, trace→metrics) via the Tempo datasource.

## Notes

- **Grafana uses an RWO PVC** → `deploymentStrategy: Recreate` (set) avoids upgrade deadlocks.
- Datasources are provisioned at Grafana **startup**; a datasource URL change needs a
  Grafana pod restart to take effect.
- To reuse an existing Grafana/Prometheus, set `grafana.enabled=false` / `prometheus.enabled=false`
  and wire datasources/remote-write to the existing services (see `values-cloud.yaml` header).
- Verified on homelab 2026-06-18: metrics (43 `up`), logs (all pod labels), and a live
  trace round-tripped through the OTLP gateway; all 3 Grafana datasources healthy.
