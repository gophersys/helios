# infrastructure — cluster and apps architecture

The authoritative reference for the vocabulary of clusters, nodes, apps,
namespaces, policies and charts that sits on top of the IDP foundation. Load this
rule whenever you touch `clusters/`, `charts/` or `platform/`, or when you write
or modify an app consumer.

The detailed reference documents live with each layer. This rule is the **map**.

## 1. Node taxonomy (authoritative)

Every cluster node declares `kubernetes.cluster_role` in its identity.yaml. These
are the only valid values:

| Role      | Label `role=` | Taint                               | Purpose                                           |
|-----------|---------------|-------------------------------------|---------------------------------------------------|
| `apps`    | `apps`        | (none; default schedulable)         | Stateless APIs, frontends, workers — everything that doesn't need isolation |
| `data`    | `data`        | `data=true:NoSchedule`              | Databases, NATS, object stores                    |
| `devops`  | `devops`      | `devops=true:PreferNoSchedule`      | Platform components (observability, ingress, cert-manager) |
| `build`   | `build`       | `build=true:NoSchedule`             | CI runners / build farms                          |
| `batch`   | `batch`       | `batch=true:PreferNoSchedule`       | Jobs on preemptible/spot compute                  |

Do not propose a new node role. The 5 roles above are designed to cover a wide
SaaS stack. Add specialization with **labels on an existing role**, for example
`role=ml,gpu=a100`. Do not add a new top-level role.

See `clusters/CONVENTIONS.md` for the full taxonomy with examples.

## 2. App archetype taxonomy (authoritative)

Every Helm chart that an app uses is one of 6 archetypes:

| Archetype        | Use when                                            | Chart dir                          |
|------------------|------------------------------------------------------|------------------------------------|
| `stateless-app`  | HTTP service, no local state                        | `charts/stateless-app/`            |
| `stateful-app`   | Stable identity + per-replica PV needed             | `charts/stateful-app/`             |
| `worker`         | Queue/stream consumer, no HTTP                      | `charts/worker/`                   |
| `cronjob`        | Scheduled                                           | `charts/cronjob/`                  |
| `job`            | One-shot run-to-completion                          | `charts/job/`                      |
| `ingress-app`    | Public stateless-app with mandatory TLS ingress     | `charts/ingress-app/`              |

Every archetype ships `values.schema.json`, which is the enforced contract
between the app and the chart. See the decision tree in `charts/README.md` and
the authoring rules in `charts/CONVENTIONS.md` (15 rules that cover the schema,
labels, security, resources, probes, network policy, secrets, observability,
SLOs, rollout, PDBs, ServiceAccount and testing).

## 3. Namespace strategy (authoritative)

**One namespace per project-env pair.** All the apps of a project for a given
environment share one namespace. This supports both topologies without a change:
one cluster per project, and one cluster for many projects.

| Pattern                | Example                       | Scope                                    |
|------------------------|-------------------------------|------------------------------------------|
| `<project>-<env>`      | `codectl-prod`, `fintel-staging`, `finances-production` | All apps of that project in that env     |
| `platform-<component>` | `platform-ingress`, `platform-monitoring`               | One platform component installation      |
| `kube-*`               | `kube-system`                 | Kubernetes reserved                      |

**`<project>`:** kebab-case, 1 to 20 characters, `^[a-z][a-z0-9-]{1,20}$`. It
MUST match a project declared in the cluster's `projects_hosted:` list. The
canonical project names today are `codectl`, `fintel`, `finances`,
`intelligence` and `music`.

**`<env>`:** the enum `prod | staging | dev | lab`. The schema rejects an app
outside the enum.

**A `<project>-<env>` namespace is provisioned automatically** by
`platform/core/namespace-provisioner/`, with:
- a default-deny NetworkPolicy baseline;
- a `ResourceQuota` (tier: small, medium or large — it applies to the whole
  project-env, and all the apps inside share it);
- a `LimitRange` with sensible defaults;
- `pod-security.kubernetes.io/enforce=restricted`.

The provisioner generates a namespace only if `<project>` is declared in the
cluster's `projects_hosted:`. That structure prevents a typo.

**Traffic between projects is explicit.** The apps in `codectl-prod` can talk
freely to each other, because they share a namespace. They cannot talk to
`fintel-prod` without a declared `networkPolicy.allowEgressTo` entry on the
source pod.

A tier escalation (`small` → `medium` → `large`) needs a platform PR. The quota
applies at the project-env level, so the whole project shares it.

## 3b. Release and label conventions

Every Helm release in a `<project>-<env>` namespace uses the name
`<project>-<app>`, for example `codectl-api`, and is deployed to
`-n <project>-<env>`.

These are the canonical labels on every object that a chart archetype renders:

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

**Kyverno was removed on 2026-08-09.** It had run `audit-only` since its
installation, with a single `pod-security-baseline` ClusterPolicy that excluded 8
namespaces. It therefore enforced nothing, while it cost 4 controller pods and a
permanent OutOfSync line in Argo.

Admission policy is not solved here. It is **deliberately not solved**: there is
1 operator, everything is reconciled from git, and code review is the control.
Introduce an admission controller again when more than 1 person deploys to these
clusters, and when you can name 2 policies that you would enforce rather than
audit. See debt-register D21.

Pod-level hardening (non-root, read-only root filesystem, dropped capabilities,
seccomp) is still applied **per workload in the manifests**. It is simply not
enforced at admission.

## 5. Observability contract (short, with a cross-reference)

An app emits:
- JSON logs on stdout, which the platform's log collector scrapes;
- `/metrics` on port 9090, with a `ServiceMonitor` that the chart emits
  automatically;
- OTLP traces to `$OTEL_EXPORTER_OTLP_ENDPOINT`, which the chart injects;
- SLO recording rules, which the chart emits from `values.slo`.

Full detail: `contracts/observability.md`.

## 6. Change management (enterprise baseline)

Today: a commit goes directly to `infrastructure/main` after a local validate and
the pre-commit hook of the drift auditor. A cross-cutting change uses PR-style
review: a new policy, a new `platform/core` component, or a breaking contract
change.

Future, when `platform/services/gitops/` lands: Flux or Argo CD reconciles the
cluster state from git, and a direct `kubectl apply` is banned outside a
break-glass procedure.

The future break-glass override procedure: annotate the object with
`platform.gophersys/gitops-bypass: "<reason>"`, with a TTL of 24 hours. An alert
fires.

## 7. Security posture (baseline)

- **Pod level:** non-root, read-only root filesystem, dropped capabilities, and
  seccomp `RuntimeDefault`. That is the target posture, enforced at admission
  under restricted PSS. **Today** it is applied per workload in the manifests,
  with no enforcement at admission at all. See §4.
- **Network:** default-deny NetworkPolicy everywhere. By default, egress is
  allowed to DNS, to the same namespace, and for the metrics scrape. Add more
  allowances per app.
- **Secrets:** Bitwarden is the only source. ESO materializes the Kubernetes
  Secrets. Direct creation of a Secret bypasses the policy and writes a loud
  audit log entry.
- **Identity:** every app has a dedicated `ServiceAccount`. RBAC is empty by
  default, and each permission is opt-in.
- **Images:** allowlisted registries only (ghcr.io/gophersys/*,
  ghcr.io/mateosegura/*, registry.k8s.io/*, and the official upstreams).
  Verification of the Cosign signature lands when CI signs the images.

## 8. SLO framework

Every app declares its SLOs in the chart values:

```yaml
slo:
  tier: critical | high | standard | best-effort
  availability: { target: 99.9, window: 30d }
  latency:      { target_ms: 300, window: 7d, percentile: 95 }
  errorBudget:  { burnRateFast: 14.4, burnRateSlow: 6 }
```

The chart emits Prometheus recording rules. Alertmanager routes by
`platform.gophersys/slo-tier`:
- `critical`: page immediately.
- `high`: page during business hours, ticket overnight.
- `standard`: ticket, no page.
- `best-effort`: dashboard only.

## 9. Cost governance

Every cluster has `cost_envelope:` in its identity.yaml, with a target and a
ceiling. `platform/services/cost/` (OpenCost) reports the spend per namespace,
per tenant and per cluster. Alertmanager fires when the spend approaches the
ceiling.

Every app namespace has a `ResourceQuota`. A tier escalation needs a PR.

## 10. Evolution path

Today: the foundation. Every layer has skeletons, docs and schemas. 3 leaves have
real content: arm-builder, the prod cluster declaration, and the contract drafts.

Next, as each cluster is brought up:
1. Populate `providers/oracle/modules/compute` and `providers/aws/` with real
   Terraform.
2. Populate `clusters/instances/prod/nodes/*/` with the real nodes.
3. Implement `platform/core/*` — Cilium, Traefik, cert-manager, ESO, Kyverno,
   namespace-provisioner.
4. Implement `platform/services/observability` — the first platform service.
5. Implement `charts/stateless-app/templates/*` — the first chart archetype.
6. Migrate the first app (codectl-api) onto the archetype and the cluster.

Next year (enterprise-ready):
- `platform/services/gitops/` (Flux or Argo CD) — the cluster state is
  reconciled from git, and manual kubectl is banned.
- `platform/services/identity-sso/` — every UI is behind SSO.
- `platform/services/progressive-delivery/` (Flagger) — canary rollouts.
- Multi-cluster federation (a lab cluster for CI, a staging cluster for
  pre-production).
- Verification of image signatures (Cosign + sigstore).
- A service mesh (Cilium Service Mesh or Linkerd), when mutual TLS between
  services becomes necessary.

## Where the detailed docs live

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
