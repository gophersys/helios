# policy — catalog

Every policy the platform enforces. Promoted to `Enforce` only after
7 days clean in `Audit`.

## Labels + metadata

### `canonical-labels`
**Mode:** mutate + validate — mutates (adds) missing labels; validates
presence on upgrade.
**Checks:** every Pod-controller (Deployment, StatefulSet, DaemonSet,
Job, CronJob) has `app.kubernetes.io/{name, instance, version,
component, managed-by}` AND `platform.gophersys/{archetype, tenant,
env, node-role, data-class, slo-tier}`.
**Rationale:** dashboards, policy routing, and cost allocation depend on
labels. Missing labels = invisible cost + noise in observability.
**Override:** none — labels are cheap; fix at source.

### `slo-tier-required`
**Mode:** validate.
**Checks:** `platform.gophersys/slo-tier` is present and one of
`critical | high | standard | best-effort`.
**Rationale:** Alertmanager routes by SLO tier; unlabeled workloads
default to "standard" silently and miss alerts.
**Override:** `slo-tier-required:<reason>` — TTL 14 days.

### `data-class-required`
**Mode:** validate.
**Checks:** `platform.gophersys/data-class` is present and one of
`public | internal | confidential | pii`.
**Rationale:** PII workloads require stricter egress controls, audit
logging, encryption-at-rest verification. Labels drive those.

## Pod security

### `restricted-pss`
**Mode:** enforce at namespace level via PodSecurityStandards
admission (baked into k8s ≥1.25). Kyverno's role: ensure every
namespace is labeled `pod-security.kubernetes.io/enforce=restricted`.
**Override:** namespace annotation
`pod-security.kubernetes.io/enforce=baseline` — TTL 30 days; requires
security review.

### `no-privileged`
**Mode:** validate.
**Checks:** no container has `securityContext.privileged: true`.
**Override:** `no-privileged:<reason>` — 7 days; rare and loud.

### `drop-capabilities`
**Mode:** validate + mutate.
**Checks:** every container has `securityContext.capabilities.drop: [ALL]`.
Mutates to add if missing (when admission arrives from a chart upgrade).

### `readonly-root-filesystem`
**Mode:** validate.
**Checks:** `securityContext.readOnlyRootFilesystem: true`.
**Override:** apps needing writable root must declare `tmpfs` volumes
via the chart — the chart emits `emptyDir{medium: Memory}` mounts.

### `run-as-nonroot`
**Mode:** validate.
**Checks:** `securityContext.runAsNonRoot: true` AND `runAsUser != 0`.

## Resource hygiene

### `resources-required`
**Mode:** validate.
**Checks:** every container (including sidecars, initContainers) has
`resources.requests.{cpu,memory}` + `resources.limits.{cpu,memory}`.
Memory limits MUST equal memory requests (no burstable memory).

### `pdb-required`
**Mode:** validate.
**Checks:** every Deployment / StatefulSet with `replicas >= 2` has a
matching `PodDisruptionBudget`.
**Override:** `pdb-required:<reason>` — single-replica exemption handled
by annotation.

### `probes-required`
**Mode:** validate.
**Checks:** every long-running Pod has `readinessProbe` + `livenessProbe`.
Jobs/CronJobs exempt.

## Secrets

### `external-secret-only`
**Mode:** validate.
**Checks:** no `Secret` object in `env.valueFrom.secretKeyRef` unless
the referenced Secret carries label `external-secrets.io/managed=true`
(emitted by ESO). Same for `envFrom.secretRef`.
**Rationale:** prevents manually-crafted Secrets carrying credentials
that aren't in Bitwarden. Every app secret goes through ESO.
**Override:** `external-secret-only:<reason>` — 7 days; covers platform
bootstrap secrets that can't yet be ESO-materialized.

### `no-hardcoded-bw-tokens`
**Mode:** validate.
**Checks:** no env var or ConfigMap key contains patterns matching
Bitwarden tokens (regex for BW session tokens, access tokens).
**Rationale:** accidental paste from clipboard into values.yaml.

## Networking

### `network-policy-required`
**Mode:** validate (generate on namespace create).
**Checks:** every `<project>-<env>` and `platform-*` namespace has at
least one NetworkPolicy (typically emitted by the app's chart; baseline
emitted by `platform/core/network-policies/`).
**Rationale:** a namespace without a NetworkPolicy accepts all traffic
— the opposite of default-deny.

### `no-hostnetwork`
**Mode:** validate.
**Checks:** `hostNetwork: true` is not set on any Pod.
**Override:** `no-hostnetwork:<reason>` — 30 days; rare (mostly for
CNI/ingress pods in kube-system).

## Volume protection

### `pvc-retain-protection`
**Mode:** validate (on DELETE).
**Checks:** a DELETE request for a PVC carrying label
`platform.gophersys/retain=true` is rejected unless the DELETE request
carries annotation
`platform.gophersys/allow-delete: "<non-empty-reason>"`.
**Rationale:** prevent `kubectl delete pvc --all` from nuking production
data.
**Override:** supply the annotation on the PVC (patched first) or on the
namespace (for bulk delete during cluster teardown).

### `no-hostpath`
**Mode:** validate.
**Checks:** no Pod declares `volumes[].hostPath`.
**Rationale:** hostPath volumes break pod mobility and escape namespace
isolation.
**Override:** platform-level exceptions only (node-exporter, csi-driver
pods in kube-system).

## Namespace

### `namespace-delete-protection`
**Mode:** validate (on DELETE).
**Checks:** a DELETE request for a namespace matching
`<project>-<env>` or `platform-*` is rejected unless the namespace
carries annotation `platform.gophersys/allow-delete: "<reason>"`.
**Rationale:** namespaces carry PVCs, Secrets, and ExternalSecrets.
`kubectl delete namespace` cascades; a wrong one is catastrophic.
**Override:** patch the namespace with the annotation before delete.

### `namespace-naming-enforced`
**Mode:** validate (on CREATE).
**Checks:** every namespace created outside `kube-*` MUST match either
`<project>-<env>` where `<project>` is listed in the cluster's
`projects_hosted:` registry (loaded via ConfigMap `platform-registry`)
and `<env>` is one of `prod | staging | dev | lab`, OR
`platform-<component>` where `<component>` is a known platform piece.
**Rationale:** typo protection + project-registry enforcement. An app
that tries to create `marketting-prod` on a cluster that doesn't host
`marketting` is caught at admission.
**Override:** none for the naming pattern; adding a project requires
updating the cluster's `projects_hosted:` list and refreshing the
ConfigMap.

### `project-label-required`
**Mode:** validate.
**Checks:** every Pod-controller and its Pods carry
`platform.gophersys/project` + `platform.gophersys/app` +
`platform.gophersys/env` labels, and `platform.gophersys/project`
matches the project prefix of the namespace it lives in.
**Rationale:** prevents apps from lying about their project and cross-
polluting dashboards / cost allocation / policy routing.
**Override:** none; labels are mandatory.

## Images

### `registry-allowlist`
**Mode:** validate.
**Checks:** image refs must match one of the allowed prefixes:
- `ghcr.io/gophersys/*`
- `ghcr.io/mateosegura/*`
- `registry.k8s.io/*`
- `docker.io/library/*` (official only)
- `quay.io/prometheus/*`, `quay.io/jetstack/*`, etc. (explicit upstream)

Full list pinned in the policy YAML; additions require a platform PR.

### `image-signature-verify` (FUTURE)
**Mode:** verifyImages.
**Checks:** all images in the `ghcr.io/gophersys/*` prefix have a
Cosign signature chained to a trusted key.
**Rationale:** supply-chain attestation. Kicks in after we wire CI-side
signing.

## Scheduling

### `noderole-toleration-required`
**Mode:** validate.
**Checks:** any Pod with `nodeSelector.role=<X>` where `<X>` is tainted
(`data`, `build`, `batch`) MUST declare the matching toleration.
**Rationale:** prevents "this pod will never schedule" footguns.

### `topology-spread-recommend`
**Mode:** validate (warn, not enforce — audit only).
**Checks:** Deployments with `replicas >= 3` have a
`topologySpreadConstraint`.
**Rationale:** single-node-of-failure avoidance. Warn because strict
enforcement would require every manifest author to reason about spread;
the archetypes emit spread automatically.

## Removal / retirement

Removing a policy is rare and gated:
1. Change it to `Audit` mode first.
2. Observe for 14 days.
3. Document the removal rationale in CATALOG.md.
4. Submit a platform PR removing the policy YAML.

## Status

STUB. Every policy listed here is a planned `ClusterPolicy` — none are
implemented yet. Implementation order matches the cluster bring-up
sequence: security first (PSS, no-privileged, drop-capabilities),
then resource hygiene, then labels, then networking, then volume
protection, then images.
