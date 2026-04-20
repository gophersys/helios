# platform/core/policy

Admission-control policies enforced on every cluster. Kyverno-based (YAML
native, cluster-scoped controller, no dedicated policy DSL). Non-negotiable
— every cluster installs this.

## Why it's in core, not services

Policies are security + correctness rails. A cluster without them is a
cluster where:
- A misconfigured Helm install lands privileged pods.
- An engineer accidentally creates a namespace that bypasses the
  default-deny NetworkPolicy.
- A PV holding production data is deleted by a typo.
- An image from an untrusted registry runs as a side effect of a test
  pull.
- A Deployment without resource limits starves everything else on its node.

None of that is acceptable in a production cluster, and opting a cluster
out of policies means opting it out of being a production cluster. So
policies live in core.

## Default implementation

**Kyverno** (Helm chart: `kyverno/kyverno`) — chosen over OPA/Gatekeeper
because:
- Policies are plain YAML CRs (no Rego), readable by every engineer.
- `generate` / `mutate` / `validate` / `verifyImages` are first-class —
  single tool covers all admission needs.
- Policy reports (`PolicyReport` CR) make violations visible to Grafana
  without any exporter.
- Fails closed by default; explicit `failurePolicy: Ignore` for warn-only.

## Two modes per policy

Every policy operates in one of two modes, declared in its spec:

- `validationFailureAction: Enforce` — violations are **rejected** at
  admission. Use for security + correctness invariants.
- `validationFailureAction: Audit` — violations are **logged** to a
  PolicyReport but not rejected. Use during rollout or for soft
  conventions.

Policies start in `Audit` when first deployed; promoted to `Enforce`
after a 7-day observation window with zero unexpected violations.

## Policy catalog

See `CATALOG.md` for the full list. Summary:

| Category          | # policies | Representative                                          |
|-------------------|-----------|---------------------------------------------------------|
| Labels + metadata | 3          | canonical-labels (all objects), slo-tier-required       |
| Pod security      | 5          | restricted-pss, no-privileged, drop-capabilities        |
| Resource hygiene  | 3          | resources-required, pdb-required, probes-required       |
| Secrets           | 2          | external-secret-only, no-hardcoded-bw-tokens            |
| Networking        | 2          | network-policy-required, no-hostnetwork                 |
| Volume protection | 2          | pvc-retain-protection, no-hostpath                      |
| Namespace         | 1          | namespace-delete-protection                             |
| Images            | 2          | registry-allowlist, image-signature-verify (future)     |
| Scheduling        | 2          | noderole-toleration-required, topology-spread-recommend |

## Override mechanism

A policy rejection can be overridden **only** by adding an explicit
annotation to the object or namespace:

```yaml
annotations:
  platform.gophersys/policy-override: "<policy-name>:<reason>"
```

Kyverno's `match` clause excludes objects carrying a valid override
annotation. Every override is logged to the audit trail and surfaces in
the Grafana compliance dashboard. Overrides have a TTL enforced by a
watchdog CronJob — an override older than 14 days without renewal is an
alert.

## Directory layout (when populated)

```
platform/core/policy/
├── README.md                  # this file
├── CATALOG.md                 # full policy list with rationale + owner
├── Chart.yaml                 # Helm chart wrapping Kyverno install + policy YAMLs
├── values.yaml                # Kyverno knobs (replicas, failure policy defaults)
├── templates/
│   ├── kyverno-install.yaml   # Kyverno operator install
│   ├── clusterpolicy-*.yaml   # one file per cluster-scoped policy
│   └── policy-*.yaml          # namespace-scoped policies (future)
└── policies/
    ├── canonical-labels/      # per-policy sub-dir with README, manifest, tests
    │   ├── README.md
    │   ├── policy.yaml        # the Kyverno ClusterPolicy CR
    │   └── tests/             # kyverno-cli test cases
    └── ...
```

## Dependencies

- `platform/core/cni/` — policies often reference NetworkPolicy
  resources; the CNI plugin enforces them.
- `platform/core/metrics-server/` — Kyverno's own HPA (if enabled) uses
  metrics.
- `platform/core/secrets-operator/` — some policies validate that
  referenced `ExternalSecret` CRs exist before the pod is admitted.

## Evolution path

Today: skeleton + README + CATALOG.
Next passes (when app-prod actually installs policies):
1. Commit the Helm wrapper + `kyverno-install.yaml`.
2. Commit each policy one by one in `Audit` mode.
3. Watch `PolicyReport`s for 7 days.
4. Promote to `Enforce`.
5. Build Grafana "compliance" dashboard from PolicyReport metrics.
6. Wire Alertmanager routes for `Enforce`-mode rejections + expired
   overrides.

## Status

STUB. README + CATALOG only. Kyverno install + policy manifests land as
`app-prod` moves from "declared" to "bootstrapped."
