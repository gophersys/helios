# platform/services/observability

Logs, metrics, traces, dashboards.

## Default implementation

**One** Helm chart, `chart/` (`eden-observability`), which vendors the upstream
subcharts and wires them together. It is one release, not four, so a datasource
URL and the service name it points at cannot drift apart:

- **Logs** — Loki (SingleBinary) + Grafana Alloy as a log-tailing DaemonSet.
- **Metrics** — the `prometheus` community chart (Prometheus server +
  kube-state-metrics + node-exporter). Alertmanager is off today.
- **Traces** — Tempo (monolithic, OTLP ingest).
- **OTLP gateway** — a second Grafana Alloy, as a Deployment. This is the
  endpoint apps target: `alloy-gateway.observability.svc:4317` / `:4318`.
- **UI** — Grafana, with all three wired as datasources on install.

Service names are pinned with `fullnameOverride`, so the Alloy river config and
the Grafana datasources address stable in-namespace DNS.

## Fulfills
- `contracts/observability.md` — how apps emit logs/metrics/traces and
  what labels they must carry.

## Dependencies
- `platform/core/storage/` — Loki + Prometheus + Tempo + Grafana all need a PV.
  On the homelab that is `local-path`: node-local, not replicated (decided
  2026-08-19).
- **MetalLB** — the Grafana LoadBalancer VIP `10.168.0.241`, pinned by the chart
  with `metallb.io/loadBalancerIPs` against the pool in
  `platform/core/edge/loadbalancer/metallb/`. There is no Ingress and no
  hostname on the homelab today; see the header of `chart/values-homelab.yaml`.
- **Not** `platform/core/secrets-operator/`. The one credential this stack needs,
  `grafana-admin`, is imperative — see `docs/runtime-secrets.md` for the two
  reasons and what would change them.

## Status

**Live on the homelab**, as the Argo Application `observability`
(`platform/services/gitops/registry/app-observability.yaml`), release `obs`,
namespace `observability`. Removed on 2026-08-09 while it was an unowned hand-run
helm release; reinstalled on 2026-08-19 under Argo, which is the whole difference.

Chart versions are pinned in `chart/Chart.yaml` and `chart/Chart.lock`. The
per-cluster values are `chart/values-homelab.yaml` and `chart/values-cloud.yaml`.

## TODO
- **Alertmanager is disabled.** Turning it on is what the lost-runner alerting
  work needs, together with routing by `platform.gophersys/slo-tier`
  (`.claude/rules/50-cluster-architecture.md` §8).
- Restore the Grafana hostname: explicit A record, then the Ingress, then the
  `contracts/exposure.yaml` declaration, in that order and in one PR — the
  header of `chart/values-homelab.yaml` says why the order matters.
- ServiceMonitor/PodMonitor labels the chart archetypes emit — document in
  `contracts/observability.md`.
- Nothing validates the chart's RENDERED output in CI; `scripts/lint-manifests.sh`
  skips Helm chart directories by design and says so.
