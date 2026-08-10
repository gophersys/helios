# infrastructure — cluster & apps architecture

Authoritative reference for the vocabulary of clusters, nodes, apps,
namespaces, policies, and charts that sits on top of the IDP foundation.
Load this rule whenever you touch `clusters/`, `charts/`, `platform/`,
or write/modify an app consumer.

Detailed reference docs live with each layer — this rule is the **map**.

## 1. Node taxonomy (authoritative)

Every cluster node declares `kubernetes.cluster_role` in its
identity.yaml. Valid values — **these are the only ones**:

| Role      | Label `role=` | Taint                               | Purpose                                           |
|-----------|---------------|-------------------------------------|---------------------------------------------------|
| `apps`    | `apps`        | (none; default schedulable)         | Stateless APIs, frontends, workers — everything that doesn't need isolation |
| `data`    | `data`        | `data=true:NoSchedule`              | Databases, NATS, object stores                    |
| `devops`  | `devops`      | `devops=true:PreferNoSchedule`      | Platform components (observability, ingress, cert-manager) |
| `build`   | `build`       | `build=true:NoSchedule`             | CI runners / build farms                          |
| `batch`   | `batch`       | `batch=true:PreferNoSchedule`       | Jobs on preemptible/spot compute                  |

Claude: before proposing a new node role, push back — the five above
are designed to cover a broad SaaS stack. Specialization goes via
**labels added to an existing role** (e.g., `role=ml,gpu=a100`), not a
new top-level role.

See `clusters/CONVENTIONS.md` for the full taxonomy with examples.

## 2. App archetype taxonomy (authoritative)

Every Helm chart an app uses is one of six archetypes:

| Archetype        | Use when                                            | Chart dir                          |
|------------------|------------------------------------------------------|------------------------------------|
| `stateless-app`  | HTTP service, no local state                        | `charts/stateless-app/`            |
| `stateful-app`   | Stable identity + per-replica PV needed             | `charts/stateful-app/`             |
| `worker`         | Queue/stream consumer, no HTTP                      | `charts/worker/`                   |
| `cronjob`        | Scheduled                                           | `charts/cronjob/`                  |
| `job`            | One-shot run-to-completion                          | `charts/job/`                      |
| `ingress-app`    | Public stateless-app with mandatory TLS ingress     | `charts/ingress-app/`              |

Every archetype ships `values.schema.json` — the enforced app-to-chart
contract. See `charts/README.md` decision tree + `charts/CONVENTIONS.md`
authoring rules (15 rules covering schema, labels, security, resources,
probes, network policy, secrets, observability, SLOs, rollout, PDBs,
ServiceAccount, and testing).

## 3. Namespace strategy (authoritative)

**One namespace per project-env pair.** A project's apps for a given
environment all share one namespace. This supports both the one-cluster-
per-project and one-cluster-for-many-projects topologies transparently.

| Pattern                | Example                       | Scope                                    |
|------------------------|-------------------------------|------------------------------------------|
| `<project>-<env>`      | `codectl-prod`, `fintel-staging`, `finances-production` | All apps of that project in that env     |
| `platform-<component>` | `platform-ingress`, `platform-monitoring`               | One platform component installation      |
| `kube-*`               | `kube-system`                 | Kubernetes reserved                      |

**`<project>`:** kebab-case, 1–20 chars, `^[a-z][a-z0-9-]{1,20}$`. MUST
match a project declared in the cluster's `projects_hosted:` list.
Canonical project names today: `codectl`, `fintel`, `finances`,
`intelligence`, `music`.

**`<env>`:** enum `prod | staging | dev | lab`. Apps outside the enum
are rejected by schema.

**`<project>-<env>` namespaces auto-provision** via
`platform/core/namespace-provisioner/`:
- Default-deny NetworkPolicy baseline.
- `ResourceQuota` (tier: small | medium | large — applies to the whole
  project-env, shared by all apps within).
- `LimitRange` with sane defaults.
- `pod-security.kubernetes.io/enforce=restricted`.
- Generated only if `<project>` is declared in the cluster's
  `projects_hosted:`. Typo-protection by construction.

**Cross-project traffic** is explicit. Apps in `codectl-prod` can talk
freely to each other (same namespace) but not to `fintel-prod` without a
declared `networkPolicy.allowEgressTo` entry on the source pod.

Tier escalation (`small` → `medium` → `large`) requires a platform PR.
Quota applies at the project-env level, so the whole project shares.

## 3b. Release & label conventions

Every Helm release in a `<project>-<env>` namespace uses the name
`<project>-<app>` (e.g., `codectl-api`), deployed to `-n <project>-<env>`.

Canonical labels on every object rendered by a chart archetype:

```yaml
app.kubernetes.io/name:        <project>-<app>       # e.g. codectl-api — unique per app per cluster
app.kubernetes.io/instance:    <release>              # usually == app.kubernetes.io/name
app.kubernetes.io/version:     <image.tag>
app.kubernetes.io/component:   <archetype>            # stateless-app | worker | etc.
app.kubernetes.io/part-of:     <project>              # codectl — matches the project
app.kubernetes.io/managed-by:  Helm

platform.gophersys/project:    <project>              # codectl
platform.gophersys/app:        <app.name>             # api — sub-app within the project
platform.gophersys/env:        <env>                  # prod | staging | dev | lab
platform.gophersys/tenant:     <tenant>               # gophersys (org-level)
platform.gophersys/archetype:  <archetype>
platform.gophersys/node-role:  <apps | data | devops | build | batch>
platform.gophersys/data-class: <public | internal | confidential | pii>
platform.gophersys/slo-tier:   <critical | high | standard | best-effort>
```

## 4. Policy model — REMOVED

**Kyverno was removed on 2026-08-09.** It had run `audit-only` since installation
with a single `pod-security-baseline` ClusterPolicy that excluded eight
namespaces, so it enforced nothing while costing four controller pods and a
permanent OutOfSync line in Argo.

Admission policy is not a solved problem here, it is a **deliberately unsolved**
one: with a single operator and everything reconciled from git, code review is
the guardrail. Re-introduce an admission controller when more than one person
deploys to these clusters, and when you can name two policies you would actually
enforce rather than audit. See debt-register D21.

Pod-level hardening (non-root, read-only rootfs, dropped caps, seccomp) is still
applied **per workload in manifests** — it simply is not enforced at admission.

## 5. Observability contract (brief, cross-ref)

Apps emit:
- JSON stdout logs — scraped by the platform's log collector.
- `/metrics` on port 9090 with `ServiceMonitor` auto-emitted by the chart.
- OTLP traces via `$OTEL_EXPORTER_OTLP_ENDPOINT` injected by the chart.
- SLO recording rules emitted from `values.slo` in the chart.

Full detail: `contracts/observability.md`.

## 6. Change management (enterprise baseline)

Today: commits directly to `infrastructure/main` after local validate
and drift-auditor pre-commit hook. PR-style review for cross-cutting
changes (new policies, new platform/core component, breaking contract
changes).

Future (when `platform/services/gitops/` lands): Flux / Argo CD
reconciles cluster state from git; direct `kubectl apply` is banned
outside break-glass procedures.

Break-glass override procedure (future): annotate with
`platform.gophersys/gitops-bypass: "<reason>"`, TTL 24h, alert fires.

## 7. Security posture (baseline)

- **Pod-level:** non-root, read-only root FS, dropped caps, seccomp
  `RuntimeDefault`. This is the target enforced-at-admission (restricted PSS)
  posture; **today** it is applied per-workload in manifests, with no admission
  enforcement at all (see §4).
- **Network:** default-deny NetworkPolicy everywhere. Egress to DNS +
  same-namespace + metrics scrape by default. Additional allows per
  app.
- **Secrets:** Bitwarden is the only source. ESO materializes K8s
  Secrets. Direct Secret creation bypasses policy (loud audit log).
- **Identity:** every app has a dedicated `ServiceAccount`; RBAC is
  empty by default, opt-in per permission.
- **Images:** allowlisted registries only (ghcr.io/gophersys/*,
  ghcr.io/mateosegura/*, registry.k8s.io/*, official upstreams). Cosign
  signature verification lands when CI signs images.

## 8. SLO framework

Every app declares SLOs in chart values:

```yaml
slo:
  tier: critical | high | standard | best-effort
  availability: { target: 99.9, window: 30d }
  latency:      { target_ms: 300, window: 7d, percentile: 95 }
  errorBudget:  { burnRateFast: 14.4, burnRateSlow: 6 }
```

Chart emits Prometheus recording rules. Alertmanager routes by
`platform.gophersys/slo-tier`:
- `critical`: page immediately.
- `high`: page during business hours, ticket overnight.
- `standard`: ticket, no page.
- `best-effort`: dashboard-only.

## 9. Cost governance

Every cluster has `cost_envelope:` in identity.yaml (target + ceiling).
`platform/services/cost/` (OpenCost) reports per-namespace, per-tenant,
per-cluster spend. Alertmanager fires when ceiling approaches.

Every app namespace has a `ResourceQuota`; tier escalation requires a
PR.

## 10. Evolution path

Today: foundation. Every layer has skeletons + docs + schemas; three
leaves have real content (arm-builder, prod cluster declaration,
contracts drafts).

Tomorrow (per cluster bring-up):
1. Populate `providers/oracle/modules/compute` + `providers/aws/` with
   real Terraform.
2. Populate `clusters/instances/prod/nodes/*/` with the real fleet.
3. Implement `platform/core/*` — Cilium, Traefik, cert-manager, ESO,
   Kyverno, namespace-provisioner.
4. Implement `platform/services/observability` — the first platform
   service.
5. Implement `charts/stateless-app/templates/*` — the first chart
   archetype.
6. Migrate first app (codectl-api) onto the archetype + cluster.

Next-year (enterprise-ready):
- `platform/services/gitops/` (Flux/Argo CD) — cluster state
  reconciled from git; manual kubectl banned.
- `platform/services/identity-sso/` — every UI behind SSO.
- `platform/services/progressive-delivery/` (Flagger) — canary rollouts.
- Multi-cluster federation (lab cluster for CI, staging cluster for
  pre-prod).
- Image signature verification (Cosign + sigstore).
- Service mesh (Cilium Service Mesh or Linkerd) when mutual TLS
  between services becomes load-bearing.

## Where detailed docs live

| Topic                          | Detail doc                                              |
|--------------------------------|---------------------------------------------------------|
| Layer map + cross-layer rules  | `.claude/rules/20-layering.md`                          |
| Onboarding procedures          | `.claude/rules/30-onboarding.md`                        |
| Platform & contracts rules     | `.claude/rules/40-platform-contracts.md`                |
| This rule (cluster arch map)   | `.claude/rules/50-cluster-architecture.md`              |
| Cluster-level conventions      | `clusters/CONVENTIONS.md`                               |
| Chart authoring conventions    | `charts/CONVENTIONS.md`                                 |
| Policy catalog                 | `platform/core/policy/CATALOG.md`                       |
| Namespace provisioning         | `platform/core/namespace-provisioner/README.md`         |
| App-platform contracts         | `contracts/README.md` + `contracts/<name>.md`           |
| Per-archetype knobs            | `charts/<archetype>/README.md`                          |
| Per-archetype schema (enforced)| `charts/<archetype>/values.schema.json`                 |
