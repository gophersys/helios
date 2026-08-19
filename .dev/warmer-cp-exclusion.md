# warmer-cp-exclusion

phase:    fix
repo:     gophersys/infrastructure
branch:   fix/warmer-cp-exclusion
worktree: ~/code/.worktrees/infrastructure-warmer-cp-exclusion
pr:       -
attempt:  1/2

## Goal
The arc-runners ci-image-warmer DaemonSet pins ~3.86GB of unGCable images (its
initContainers run `true`, holding the images "in use" forever) on all schedulable
nodes INCLUDING the three 38GB etcd control planes. Its comment claims no-tolerations
keeps it off tainted control planes — but zero taints exist cluster-wide (verified
live), so the premise is false. k3s-cp-0 hit 93% used / 2.7GB free at 22:31Z while
running etcd; kubelet image GC could not free enough. When this is done: the warmer
never schedules on k3s-cp-0/1/2, the comment tells the truth, and the fix is proven
IN EFFECT — warmer pods gone from the CPs after Argo syncs, image GC reclaims the
cloud images there, df on all three CPs below the 85% GC high-threshold, with numbers.

## Plan
plan: SELF-APPROVED (--auto), FULL scope (pool files included — the minimal version
trades the pin for 2.2GB cold-pulls onto etcd nodes, the planner's named risk).
Risk weighed: runner-eligible nodes drop 7->4 for arc-org/arc-review at maxRunners 4
— inside the measured contention envelope, stated at merge.
- 42-image-warmer-daemonset.yaml + 43-image-warmer-refresh.yaml + app-arc-runners-
  org.yaml:105 + app-arc-runners-review.yaml:68: NotIn gains k3s-cp-0/1/2 (hostnames,
  NOT role labels — cluster_role devops includes w-0, a runner worker; node-role label
  unobserved and unprecedented in-repo). False comments rewritten (42:35-37, 43:12).
- verify-warmer-pins.sh property 3: DERIVE the server set from clusters/instances/
  homelab/nodes/*/identity.yaml (kubernetes.role: server) and assert every derived
  hostname in the NotIn of all 4 files (yq guarded exit-127 for identities; TEXT read
  for the helm values: | blocks); accumulate via fail(), never exit mid-loop (-e absent).
- scripts/test-verify-warmer-pins.sh: NEW fixture suite, 5 cases (CP-EXCLUDED,
  DERIVED-NOT-HARDCODED, ZERO-SERVERS-IS-NOT-A-PASS, REFRESH-COVERED, POOLS-COVERED),
  real script via symlinked ROOT per test-verify-buildx-key.sh convention.
- validate.yml: run the suite in `manifests`, no continue-on-error.
- docs/debt-register.md D45 🟠: declared devops labels/taints exist in git, zero
  applied live, cluster-node-labels Ansible role pending; affinity governs instead.
- VERDICT KEPT: imagePullPolicy Always stays (IfNotPresent freezes :latest; the daily
  refresh exists solely to re-resolve it; superseded digests are GC-able post-change).
- In-effect proof (post-merge): DS desiredNumberScheduled 7->4; zero warmer pods on
  k3s-cp*; crictl shows cloud images with NO holding container (reclaimable); one-time
  `crictl rmi --prune` per CP (NOT during an Argo sync), df before/after recorded —
  GC alone will NOT fire at 57% usage; done-condition = reclaimable + reclaimed once.
  Sync confirmed from DS generation + pod set, never from Application status (D44).
- Out of scope: CP taints (D45 records), LimitRange, Longhorn, journald, base-runner
  layer removal, Ansible label role, arc-build (already pinned In workers).

## Proven
- Diagnosis (agent, 2026-08-18 22:38Z, read-only, raw captures in session scratchpad
  out/*.txt): cp-0 93%→57% after kubelet GC self-rescue at 22:31Z; warmer initContainers
  pin ghcr.io/gophersys/cloud@sha256:9a15... 2.06GB + :latest 1.65GB + dind 0.15GB on
  7/8 nodes; zero taints cluster-wide (kubectl get nodes jsonpath); containerd is
  84-90% of used disk on every node; log rotation healthy; crictl understates real
  image disk ~3.7x.

## Blocked
-

## Phase evidence (F5 correction — this file lagged two phases; orchestrator's fault)
- RED (83c52a1): fixture suite cases=6 assertion-failures=18 rc=1 against the real
  verifier; 5 cases fail exactly on the missing property; control green; missing-tool
  guard exit 127; fixture-defect guard proven on a scratch break.
- GREEN (c0f24fb): suite cases=6 failures=0 rc=0; real-tree verifier rc=0 with the new
  "3 control-plane node(s) excluded" line; ctl.sh validate rc=0; lint-manifests 134
  resources 0 invalid; lint-shell 33 scripts rc=0; kubeconform valid; both pools'
  values re-parsed to the 4-host list.
- VERIFY round 1 (REFUTED — fix round 1 open): F1 HIGH pool text-read passes on soft
  (preferred) affinity AND on commented-out exclusion blocks; the "structural read
  impossible" premise is FALSE — two-stage yq parses the helm values string (proven).
  F2 block-style values fires FALSE red. F3 nodeSelectorTerms OR-semantics ignored —
  a second term reopens all CPs, gate says OK. F4 D45: roles count is 10 not 8; only
  4/8 nodes declare taints. F6 CONVENTIONS.md:131,193 need D45 cross-refs.
  CORRECTIONS: no ≤72-char subject rule exists in THIS repo (that is libs' rule);
  diff = 8 planned files, no drift. Verifier re-proved: defect live (warmer on all 3
  CPs now), cp-0 57%, cp-1 73% (closest to GC threshold — leads the reclaim step).

## Fix round 1 — landed
- RED (test author, 7ba5294): 4 new cases red for the right reasons (3 false-pass +
  1 FALSE RED with 6 wrong failure lines shown verbatim); fixture parse + NotIn-intact
  guards proven; suite premise comment corrected.
- GREEN (implementer, 1f8a825): notin_from_text DELETED with its false premise; pools
  read two-stage yq (scalar parsed AS document); per-nodeSelectorTerm judgement for
  warmer files too; preferred never read; zero-terms gets its own loud line; failure
  lines carry file+node+term index. Suite 10/10 rc=0; real-tree verifier rc=0; ctl.sh
  validate rc=0 (after fixing an SC2004 its own first pass caught — fixed, not
  silenced); lint-shell 33 rc=0; lint-manifests 134/0 rc=0; D45 numbers MEASURED
  (10 roles; labels 8/8, taints 4/8); CONVENTIONS.md :131/:193 cross-referenced.
- Honest bounds stated in code: In-lists not read as exclusions (false-red risk named);
  matchFields/other-key NotIn count as not-ruling-out (loud direction).

## Next
Verify round 2, then PR. In-effect proof (7->4, crictl prune, df numbers) post-merge.
