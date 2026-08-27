# infrastructure — cluster and apps architecture

The authoritative reference for the vocabulary of clusters, nodes, apps,
namespaces, policies and charts that sits on top of the IDP foundation. Load this
rule whenever you touch `clusters/`, `charts/` or `platform/`, or when you write
or modify an app consumer.

The detailed reference documents live with each layer. This rule is the **map**.

## 1. Node taxonomy (authoritative)

Every cluster node declares `kubernetes.cluster_role` in its identity.yaml.
Valid values — **these are the only ones**:

| Role      | Label `role=` | Taint                               | Purpose                                           |
|-----------|---------------|-------------------------------------|---------------------------------------------------|
| `apps`    | `apps`        | (none; default schedulable)         | Stateless APIs, frontends, workers — everything that doesn't need isolation |
| `data`    | `data`        | `data=true:NoSchedule`              | Databases, NATS, object stores                    |
| `devops`  | `devops`      | `devops=true:PreferNoSchedule`      | Platform components (observability, ingress, cert-manager) |
| `build`   | `build`       | `build=true:NoSchedule`             | CI runners / build farms                          |
| `batch`   | `batch`       | `batch=true:PreferNoSchedule`       | Jobs on preemptible/spot compute                  |

Before you propose a new node role, push back. The 5 roles above are designed to
cover a wide SaaS stack. Add specialization with **labels on an existing role**,
for example `role=ml,gpu=a100`. Do not add a new top-level role.

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

**A `<project>-<env>` namespace is SUPPOSED to be provisioned automatically** by
`platform/core/namespace-provisioner/`. That component is a STUB and lost its
mechanism with Kyverno, so today every namespace is written by hand in
`apps/*/00-namespace.yaml`. The specification, unimplemented:
- a default-deny NetworkPolicy baseline;
- a `ResourceQuota` (tier: small, medium or large — it applies to the whole
  project-env, and all the apps inside share it);
- a `LimitRange` with sensible defaults;
- `pod-security.kubernetes.io/enforce=restricted`.

The provisioner would generate a namespace only if `<project>` is declared in the
cluster's `projects_hosted:`, and that structure would prevent a typo. Nothing
checks it today.

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

## 4. Policy model — 2 in-tree policies, no engine (2026-08-19)

**Kyverno was removed on 2026-08-09**, and it is not coming back. It had run
`audit-only` since its installation, with a single `pod-security-baseline`
ClusterPolicy that excluded 8 namespaces. It therefore enforced nothing, while it
cost 4 controller pods and a permanent OutOfSync line in Argo on 4 CRDs.

**What replaced it is not a smaller engine. It is no engine at all.**
`platform/core/policy/` holds 2 hand-written `ValidatingAdmissionPolicy` objects
that the apiserver's own in-tree plugin evaluates: **0 pods, 0 CRDs, 0 OutOfSync
lines**. Both bind with `validationActions: [Deny]` and both set
`failurePolicy: Fail`.

| Policy | Refuses | Gated on |
|---|---|---|
| `storage-delete-guard` | `DELETE persistentvolumeclaims` | namespace label `platform.gophersys/protected-storage=true`, or PVC label `platform.gophersys/retain=true` |
| `namespace-delete-guard` | `DELETE namespaces` | namespace label `platform.gophersys/protected=true` |

Break glass on either with the annotation
`platform.gophersys/allow-delete: "<reason>"` on the object. That annotation has
**no TTL** — see §6.

### Why this clears the bar the previous version of this section set

The old text said: reintroduce an admission controller only when more than 1
person deploys here, **and** when you can name 2 policies you would enforce
rather than audit.

The second condition is met, and by a measured threat rather than an aspiration.
`local-path` is the only StorageClass, it is the default, its reclaim policy is
`Delete`, and its teardown script is `rm -rf`. The `eden` namespace holds Vault —
the root of trust — plus Postgres and the NATS JetStream store, and it has **no
backup**: `apps/music/config-backup` covers media only, and Longhorn was removed
on 2026-08-19. `apps/eden/06-nats.yaml` declares a bare PVC inside an Argo
Application with `prune: true` and `selfHeal: true`, so deleting or renaming that
one file in a **merged** pull request destroys the store with no human in the
loop. That is one armed path and one cascade — 2 policies, one family,
irreversible deletion.

**The first condition is not met, and this section does not claim it is.** There
is still 1 operator. The argument is that the condition encodes the wrong threat
model for *this* invariant: the deleters here are Argo's prune and one operator's
own `kubectl`, and both exist with a team of one. The CI gate cannot cover it,
because **a deletion is not a manifest** — kubeconform validates what you add,
and Argo's prune runs after merge.

**And the cost premise of the old text is simply zero here.** It banned an
admission *controller* — a deployed engine with pods, CRDs and a webhook that can
be down. A `ValidatingAdmissionPolicy` is an in-tree API object. The ban belongs
on the first, not the second, and this section now says so explicitly. Nothing in
`platform/core/policy/` can be uninstalled, because nothing was installed.

**Consequence for future work:** never adopt a generator that emits these
policies. Kyverno can produce `ValidatingAdmissionPolicy` objects from a
`ClusterPolicy`, and the generated object carries an `ownerReference` back to the
Kyverno policy — so removing Kyverno garbage-collects the enforcement on the way
out. There is also no export path back (`kyverno migrate` migrates resource
versions; it is not a policy converter). Hand-written is a requirement, not a
style.

### What is still NOT enforced at admission

Everything else. Each claim in this repo now carries exactly one bucket, and each
bucket names the artifact that backs it:

| Bucket | Means | Verified by |
|---|---|---|
| `enforced-at-admission` | a Binding with `validationActions: [Deny]`, or a PodSecurity namespace label | `kubectl get validatingadmissionpolicybinding` · `kubectl get ns --show-labels` |
| `enforced-at-render` | a Helm `values.schema.json` constraint. The opt-out is named and falsifiable: Argo's `spec.source.helm.skipSchemaValidation` / Helm's `--helm-skip-schema-validation`, default `false` | read the schema, then grep for the opt-out |
| `enforced-at-PR-gate` | a named script step in `.github/workflows/validate.yml` | read the workflow |
| `applied-per-workload-unenforced` | the manifest renders it and nothing checks it — the sentence must say **"unenforced"** | read the manifest |
| `historical-record` | a dated audit or migration record; do not rewrite | the file's own date header |

**A claim with no artifact is deleted, not softened.**

Specifically still unenforced at admission: the registry allowlist (§7 — the
documented list was fiction and the honest one belongs at the PR gate), and the
pod-security posture (§7 — that wants in-tree PodSecurity namespace labels, not a
policy engine, and `restricted` cannot hold today because metallb needs
`hostNetwork` + `NET_RAW`). Pod-level hardening is still applied **per workload
in the manifests, unenforced**.

See `platform/core/policy/README.md` for the CEL, the limits and the primary
sources; `docs/debt-register.md` D21 (closed) and D46 (the successor entry).

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
`platform.gophersys/gitops-bypass: "<reason>"`, with a TTL of 24 hours and an
alert. **Nothing implements that TTL or that alert today** — it is a design note,
not a control. The one break-glass annotation that IS live,
`platform.gophersys/allow-delete` (§4), deliberately has **no** TTL: a
ValidatingAdmissionPolicy cannot expire an annotation, and claiming a TTL that
nothing enforces is the exact defect §4 exists to end. It expires when a human
removes it.

## 7. Security posture (baseline)

- **Pod level:** non-root, read-only root filesystem, dropped capabilities, and
  seccomp `RuntimeDefault`. That is the **target** posture. **Today** it is
  `applied-per-workload-unenforced`: the manifests render it and nothing checks
  it. Admission enforcement here needs no policy engine — in-tree PodSecurity is
  default-on and wants 3 namespace labels — but `restricted` cannot hold yet
  (metallb needs `hostNetwork` + `NET_RAW`, and only `metallb-system` carries PSA
  labels today). Honest per-namespace labels are a separate work item. See §4.
- **Network:** default-deny NetworkPolicy everywhere. By default, egress is
  allowed to DNS, to the same namespace, and for the metrics scrape. Add more
  allowances per app.
- **Secrets:** Bitwarden is the only source. ESO materializes the Kubernetes
  Secrets. Direct creation of a Secret bypasses the policy and writes a loud
  audit log entry.
- **Identity:** every app has a dedicated `ServiceAccount`. RBAC is empty by
  default, and each permission is opt-in.
- **Images:** **no registry allowlist is enforced anywhere today.** The list that
  stood here — `ghcr.io/gophersys/*`, `ghcr.io/mateosegura/*`, `registry.k8s.io/*`
  "and the official upstreams" — was fiction: the running estate also pulls from
  `lscr.io`, `docker.io`, `qmcgaw`, `hashicorp`, `openresty` and `filebrowser`,
  and "the official upstreams" is unfalsifiable, so nothing could ever check it.
  When this is enforced it belongs at the PR gate, with an explicit list derived
  from what actually runs, and this bullet gets the artifact's name. Verification
  of the Cosign signature lands when CI signs the images.

## 8. SLO framework

Every app declares its SLOs in the chart values:

```yaml
slo:
  tier: critical | high | standard | best-effort
  availability: { target: 99.9, window: 30d }
  latency:      { target_ms: 300, window: 7d, percentile: 95 }
  errorBudget:  { burnRateFast: 14.4, burnRateSlow: 6 }
```

The chart emits Prometheus recording rules. The TARGET routing model is by
`platform.gophersys/slo-tier`:
- `critical`: page immediately.
- `high`: page during business hours, ticket overnight.
- `standard`: ticket, no page.
- `best-effort`: dashboard only.

**Today (2026-08-24):** the homelab Alertmanager exists (enabled with the
Discord delivery in `platform/services/observability`) and routes EVERYTHING
through one flat Discord receiver. The tier-aware tree above is not built —
that gap is the first TODO in `platform/services/observability/README.md`.
Before this date the sentence above was vacuous (no Alertmanager ran anywhere);
now it would be false without this paragraph.

## 9. Cost governance

Every cluster has `cost_envelope:` in its identity.yaml, with a target and a
ceiling. `platform/services/cost/` (OpenCost) reports the spend per namespace,
per tenant and per cluster. Alertmanager fires when the spend approaches the
ceiling.

Every app namespace has a `ResourceQuota`. A tier escalation needs a PR.

## 10. Evolution path

Today: the foundation. Every layer has skeletons, docs and schemas. 3 leaves have
real content: the prod cluster declaration and the contract drafts.

Next, as each cluster is brought up:
1. Populate `providers/oracle/modules/compute` and `providers/aws/` with real
   Terraform.
2. Populate `clusters/instances/prod/nodes/*/` with the real nodes.
3. Implement `platform/core/*` — Cilium, Traefik, cert-manager, ESO,
   namespace-provisioner. (`policy/` is done: 2 in-tree ValidatingAdmissionPolicies,
   no engine — see §4.)
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
| Policy model (2 in-tree VAPs)  | §4 + `platform/core/policy/README.md` + debt-register D46 |
| Namespace provisioning         | `platform/core/namespace-provisioner/README.md`         |
| App-platform contracts         | `contracts/README.md` + `contracts/<name>.md`           |
| Per-archetype knobs            | `charts/<archetype>/README.md`                          |
| Per-archetype schema (enforced)| `charts/<archetype>/values.schema.json`                 |
