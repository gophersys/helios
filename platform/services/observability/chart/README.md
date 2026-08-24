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
| **Alertmanager** (subchart of prometheus, v0.33.0) | Alert routing + delivery. Off in the base values; the homelab enables it with a Discord receiver (`webhook_url_file` from an ESO-materialized Secret) and the incident-derived rules in `serverFiles.alerting_rules.yml` — see `values-homelab.yaml`. No UI exposure; port-forward `svc/alertmanager :9093`. |
| **Loki** | Log store (filesystem or S3) |
| **Tempo** | Trace store (filesystem or S3), HTTP API on **:3200**, OTLP on :4317/:4318 |
| **Grafana** | Dashboards + provisioned datasources (Prometheus/Loki/Tempo). Disable to reuse an existing one. |

Every component is open source. The only proprietary part of Grafana Cloud is its
set of prepared dashboards. This chart ships open equivalents through `gnetId`:
the kube-prometheus views, Node Exporter Full and the Loki logs dashboard.

## Install

**On the homelab, Argo owns this chart.** Do not run helm by hand there. The
Application is `platform/services/gitops/registry/app-observability.yaml`
(release `obs`, namespace `observability`, values `values-homelab.yaml`); it is
automated with `selfHeal`, so a hand-run `helm upgrade` is drift that Argo
reverts with no message. That is exactly how the previous install died: it sat in
`failed` helm state at revision 8 from 2026-06-18 until it was uninstalled on
2026-08-09, and nothing reconciled it because nothing owned it.

**One imperative step first, on any cluster.** The chart reads
`admin.existingSecret=grafana-admin`, and there is no ExternalSecret for it: no
vault item exists, and the `vaultwarden` ClusterSecretStore returns only an
item's `notes` field, which does not fit a 2-key login. Grafana sits in
`CreateContainerConfigError` until the Secret exists — visible, not silent.

```bash
kubectl create namespace observability
kubectl -n observability create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$(openssl rand -base64 18)"
```

The password is generated here and nowhere else. Read it back with:

```bash
kubectl -n observability get secret grafana-admin \
  -o jsonpath='{.data.admin-password}' | base64 -d
```

Direct helm, for a cluster Argo does not manage (and for authoring):

```bash
helm dependency build

# Homelab shape (local-path PVCs, Grafana on a MetalLB LoadBalancer, no Ingress —
# read the values-homelab.yaml header for why the hostname is off and how to restore it):
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

- **Storage on the homelab is `local-path`** (decided 2026-08-19; the 5 pins are
  in `values-homelab.yaml`, and its header carries the durability trade). The
  volumes are node-local and not replicated, and `local-path` is
  WaitForFirstConsumer, so each PVC binds on the node its pod first lands on and
  the pod is pinned there afterwards.
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
