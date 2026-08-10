# eden-observability

A self-contained observability stack that you can install on **any** Kubernetes
cluster. It gives Kubernetes monitoring with no extra configuration, **and** an
OpenTelemetry endpoint for your apps.

## What it deploys

| Component | Role |
|---|---|
| **Grafana Alloy** — gateway (Deployment) | OTLP receiver (gRPC `:4317` / HTTP `:4318`) → fans out to Prometheus / Loki / Tempo. **This is the endpoint your apps target.** |
| **Grafana Alloy** — logs (DaemonSet) | Tails every pod's logs → Loki |
| **Prometheus** | Scrapes k8s (cAdvisor, kubelet, kube-state-metrics, node-exporter) + accepts remote-write |
| **Loki** | Log store (filesystem or S3) |
| **Tempo** | Trace store (filesystem or S3), HTTP API on **:3200**, OTLP on :4317/:4318 |
| **Grafana** | Dashboards + provisioned datasources (Prometheus/Loki/Tempo). Disable to reuse an existing one. |

Every component is open source. The only proprietary part of Grafana Cloud is its
set of prepared dashboards. This chart ships open equivalents through `gnetId`:
the kube-prometheus views, Node Exporter Full and the Loki logs dashboard.

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

`fullnameOverride` pins the service names, so that the Alloy configuration and
the Grafana datasources use stable DNS names inside the namespace:
`prometheus-server`, `loki:3100`, `tempo:3200/:4317` and
`alloy-gateway:4317/:4318`.

## Send the telemetry of an app (OpenTelemetry)

Point the OTLP exporter of your app at the gateway, in the same namespace:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy-gateway.observability.svc:4318   # HTTP
# or gRPC:                  http://alloy-gateway.observability.svc:4317
OTEL_SERVICE_NAME=my-app
```

The metrics go to Prometheus, the logs go to Loki, and the traces go to Tempo.
All of them are visible in Grafana, and the Tempo datasource links them together
(trace to logs, and trace to metrics).

## Notes

- **Grafana uses an RWO PVC.** The chart sets `deploymentStrategy: Recreate`, so
  an upgrade cannot block on the volume.
- Grafana provisions the datasources at **startup**. A change to a datasource URL
  therefore takes effect only after a restart of the Grafana pod.
- To reuse an existing Grafana or Prometheus, set `grafana.enabled=false` or
  `prometheus.enabled=false`, and wire the datasources and the remote-write to
  the existing services. See the header of `values-cloud.yaml`.
- Verified on the homelab on 2026-06-18: the metrics (43 targets `up`), the logs
  (every pod label), and a live trace that went through the OTLP gateway and
  back. All 3 Grafana datasources were healthy.
