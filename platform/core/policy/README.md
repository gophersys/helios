# platform/core/policy

Admission policy for every cluster. **No controller, no pod, no CRD.**

Two `ValidatingAdmissionPolicy` objects, hand-written, applied by Argo, evaluated
by the apiserver's own in-tree plugin. They refuse one thing: the **irreversible
deletion of storage**.

| | |
|---|---|
| Pods | 0 |
| CRDs | 0 |
| Argo `OutOfSync` lines | 0 |
| API objects | 2 `ValidatingAdmissionPolicy` + 2 `ValidatingAdmissionPolicyBinding` |
| Mode | `validationActions: [Deny]` — enforce, never audit |
| `failurePolicy` | `Fail` — fail-closed on both |

This replaces the Kyverno install that was removed on 2026-08-09. It is not a
smaller policy engine; it is **no engine at all**. `ValidatingAdmissionPolicy` is
GA at `admissionregistration.k8s.io/v1` since Kubernetes 1.30, its admission
plugin is in the default-enabled set, and `admissionregistration.k8s.io/v1` is in
the stable API groups enabled by default — so it needs no flag, no
`--runtime-config` and nothing installed. Verified on this cluster
(k3s v1.35.5+k3s1) by `kubectl api-resources --api-group=admissionregistration.k8s.io`,
which serves `validatingadmissionpolicies` at `v1`.

## What it enforces

| Policy | Matches | Denies when | Escape hatch |
|---|---|---|---|
| `storage-delete-guard` | `DELETE persistentvolumeclaims` (all namespaces) | the PVC's namespace carries `platform.gophersys/protected-storage: "true"`, **or** the PVC carries `platform.gophersys/retain: "true"` | annotate the PVC `platform.gophersys/allow-delete: "<reason>"` |
| `namespace-delete-guard` | `DELETE namespaces` | the namespace carries `platform.gophersys/protected: "true"` | annotate the namespace `platform.gophersys/allow-delete: "<reason>"` |

Labelled today (`apps/eden/00-namespace.yaml`): **`eden`**, which holds
`data-vault-0` (the root of trust), `data-eden-postgres-0` and `eden-nats-data`.

`media` and `minio` are deliberately **not** labelled in this component's first
landing: `minio` has no PVC at all, and the three `media` PVCs are configuration
covered by `apps/music/config-backup`. Protecting either one later is a single
label in git — the bindings are cluster-wide and the policies are label-gated, so
no change is needed here.

## What it deliberately does NOT enforce

A claim with no artifact is deleted, not softened. These were all claimed
somewhere in this repo against a policy engine, and none of them is enforced at
admission now:

- **Registry allowlist.** The documented list was fiction — the live estate pulls
  from `lscr.io`, `docker.io`, `qmcgaw`, `hashicorp`, `openresty` and
  `filebrowser`, and "and the official upstreams" is unfalsifiable. It belongs at
  the PR gate with an explicit, true list. Not built yet.
- **Pod-security posture.** This needs no policy engine: `PodSecurity` is in-tree
  and default-on and wants three namespace labels. It cannot be set to
  `restricted` today (metallb needs `hostNetwork` + `NET_RAW`), so honest
  per-namespace labels are a separate work item. Only `metallb-system` is
  labelled today.
- **Canonical-label enforcement, required resources, PDB overrides.** Manifest
  shape. The PR gate is the right place; the schema in
  `charts/<archetype>/values.schema.json` already carries part of it.

## The claim taxonomy

Every enforcement sentence in this repo belongs to exactly one bucket, and each
bucket must name the artifact that backs it.

| Bucket | Means | Verified by |
|---|---|---|
| `enforced-at-admission` | a `ValidatingAdmissionPolicyBinding` with `validationActions: [Deny]`, or a PodSecurity namespace label | `kubectl get validatingadmissionpolicybinding` · `kubectl get ns --show-labels` |
| `enforced-at-render` | a Helm `values.schema.json` constraint; `helm template` refuses the render. The opt-out is real, named and falsifiable: Argo's `spec.source.helm.skipSchemaValidation` and Helm's `--helm-skip-schema-validation`, **default `false`** — `grep -rn skipSchemaValidation` returns nothing in this repo | read the schema, then grep for the opt-out |
| `enforced-at-PR-gate` | a named script step in `.github/workflows/validate.yml` | read the workflow |
| `applied-per-workload-unenforced` | the manifest renders it and nothing checks it — the sentence MUST contain the word "unenforced" | read the manifest |
| `historical-record` | a dated audit or migration record; do not rewrite it | the file's own date header |

A sixth outcome is `removed`: no artifact will ever back the claim, so the
sentence is deleted.

## Rules for changing this component

**Hand-write every policy here. Never let a generator emit them.** Kyverno can
emit `ValidatingAdmissionPolicy` objects from a `ClusterPolicy`, and it is a trap
in both directions: the generated VAP carries an `ownerReference` back to the
Kyverno policy, so *uninstalling Kyverno garbage-collects the enforcement on the
way out* — the guard disappears with the engine that was supposed to be optional.
There is also no export path back: `kyverno migrate` migrates resource versions,
it is not a policy converter. The 2 files in `manifests/` are the source; they
depend on nothing that can be uninstalled.

**Enforce or delete.** A policy that lands with `validationActions: [Audit]` or
`[Warn]` recreates the exact defect that got Kyverno removed: 4 pods of
enforcement theatre. If a rule is not worth denying, it belongs at the PR gate.

**Do not promise a TTL this component cannot keep.** A VAP cannot expire an
annotation. `.claude/rules/50-cluster-architecture.md` §6 describes a 24-hour TTL
on a break-glass annotation; that TTL is **not** enforced for
`platform.gophersys/allow-delete`, and restating it here would recreate the
unbacked-claim bug this component exists to end. It expires when a human removes
it.

## Known limits, stated so they are not discovered later

- **No cross-object reads.** A VAP cannot fetch the PV or the StorageClass, so it
  cannot condition on `reclaimPolicy`. It cannot reach it through `paramRef`
  either: `paramRef` binds one fixed name or a selector, and with a selector every
  matched param is evaluated as a separate `(policy, binding, param)` combination
  that must all pass — there is no way to select the param matching the incoming
  PVC's `storageClassName`. KEP-3488 names requests to external systems a
  permanent non-goal. **The label carrying the intent is therefore the only
  in-tree shape, not a shortcut.**
- **`MutatingAdmissionPolicy` is not served on this cluster.** Verified:
  `kubectl get mutatingadmissionpolicies` → *"the server doesn't have a resource
  type"*. On 1.35 it is beta, `v1beta1`, off, and needs both a feature gate and
  `--runtime-config`. So the protection labels cannot be injected at admission —
  the manifests and the charts must emit them. It goes GA and default-on in 1.36;
  revisit auto-labelling on the k3s 1.36 line, not before.
- **A VAP does not protect itself.** VAP resources are exempt from VAP
  evaluation, so an operator with `kubectl` can delete the guard. The mitigation
  today is Argo: `app-policy` runs `selfHeal: true, prune: false`, so a deleted
  policy is recreated on the next reconcile and a removed manifest file cannot
  prune the live object. The eventual answer is manifest-based admission policies
  loaded from disk before the apiserver serves — alpha in 1.36 (KEP-5793).
- **The expressions must never error.** With `failurePolicy: Fail`, a CEL runtime
  error denies the request, so an erroring guard would lock out every PVC delete
  in the cluster. Every lookup uses CEL optional chaining
  (`x.?labels['k'].orValue('')`), which returns the default for *both* an absent
  `labels` map and an absent key. This was proven by execution against `cel-go`
  over all four cases (labels absent / key absent / `"true"` / `"false"`) before
  the expressions were written into these files.
- **`object` is null on DELETE.** Both policies read `oldObject`. Both facts are
  quoted in the ValidatingAdmissionPolicy v1 API reference.

## Verify

```
bash ctl.sh verify-vap-policies      # CI, manifest shape: Deny binding, Fail policy,
                                     # labels present, retention pinned
bash ctl.sh test-vap-guard           # LOCAL-ONLY, live: both directions via
                                     # kubectl --dry-run=server
```

`test-vap-guard` is local-only for the same reason as `verify-access` and
`verify-vault-refs`: it needs a real apiserver with the policies already synced.
A CI runner has no such cluster, and a check that fails for the environment
rather than for the property always ends in a skip. It **fails loudly** when the
policies are not installed — it never reports a pass it did not measure.

## Dependencies

None. The apiserver serves this; nothing must be installed first. It is last in
the `platform/core` install order only so that a Deny policy cannot refuse part
of a bring-up that is still in progress.

## Evidence

| Claim | Source |
|---|---|
| VAP is GA at `admissionregistration.k8s.io/v1` since 1.30 | <https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/> |
| `ValidatingAdmissionPolicy` and `PodSecurity` are default-enabled admission plugins; `MutatingAdmissionPolicy` is not | <https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/> |
| `object` is null for DELETE; `oldObject` is the existing object; `namespaceObject` is populated for namespaced resources | <https://kubernetes.io/docs/reference/kubernetes-api/policy-resources/validating-admission-policy-v1/> |
| CEL optional types (`?field`, `.orValue()`) available since 1.29 | <https://kubernetes.io/docs/reference/using-api/cel/> |
| External lookups are a permanent non-goal | [KEP-3488](https://github.com/kubernetes/enhancements/blob/master/keps/sig-api-machinery/3488-cel-admission-control/README.md) |
| k3s adds `enable-admission-plugins=NodeRestriction`, which is additive to the defaults, so VAP stays on | [k3s v1.35.5+k3s1 `server.go` L265](https://github.com/k3s-io/k3s/blob/v1.35.5%2Bk3s1/pkg/daemons/control/server.go#L265) |
| StatefulSet-created PVCs go through ordinary admission (a future CREATE-time policy could cover them) | [`stateful_pod_control.go` L100](https://github.com/kubernetes/kubernetes/blob/release-1.35/pkg/controller/statefulset/stateful_pod_control.go#L100-L103) |
| `persistentVolumeClaimRetentionPolicy` is GA since 1.32, default `Retain`, implemented with an ownerRef on the PVCs when set to `Delete` | <https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#persistentvolumeclaim-retention> |

The full decision record — the live probes, the weighted option comparison and
the counter-argument against this component — is `docs/debt-register.md` D21 and
D46, and `.claude/rules/50-cluster-architecture.md` §4.

## Status

**Live.** 2 policies, 2 bindings, applied by `app-policy` in the Argo app-of-apps.
